# -- STDLIB
import logging
import time

from django.conf import settings
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Collate
from django.tasks import task

from request_ddi.utils.datetime import (
    parse_date,
)
from request_ddi.utils.normalize_string import (
    normalize_string_for_database,
)

from .documents import BindingSurveyDocument
from .exceptions import DataValidationError
from .models import (
    BindingSurveyRepresentedVariable,
    BindingVariableCategoryStat,
    Category,
    Collection,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
    UploadedDDICFile,
)

# -- REQUEST_DDI (LOCAL)
from .parser import fetch_and_parse_xml

logger = logging.getLogger("performance")


IMPORT_FORMAT_DDIC = "ddic"


@task(takes_context=True)
def import_data(context, survey, import_format):
    # If import_format is ddic, fetch XML and parse it
    if import_format == IMPORT_FORMAT_DDIC:
        survey_data = fetch_and_parse_xml(survey)

    # Conversion de survey_start_date en objet date (année uniquement)
    for d in ("start_date", "date_last_version"):
        if survey_data[d]:
            survey_data[d] = parse_date(survey_data[d], survey_data["doi"])
        else:
            survey_data[d] = None

    num_questions = len(survey_data["variables"])
    doi = survey_data["doi"]
    start_time = time.time()
    try:
        # Validate survey_data
        validate_unique_variable_names(survey_data["variables"])

        # We use update_or_create here as during the force update, we should update all
        # the objects
        with transaction.atomic():
            distributor_name = survey_data["distributor"]
            distributor, _ = Distributor.objects.update_or_create(name=distributor_name)

            collection_name = survey_data["collection"]
            collection, _ = Collection.objects.update_or_create(
                name=collection_name, distributor=distributor
            )

            subcollection_name = survey_data["sub_collection"]
            subcollection, _ = Subcollection.objects.update_or_create(
                name=subcollection_name, collection=collection
            )

            survey, _ = Survey.objects.update_or_create(
                external_ref=doi,
                defaults={
                    "name": survey_data["title"],
                    "subcollection": subcollection,
                    "language": survey_data["lang"],
                    "author": survey_data["authors"],
                    "producer": survey_data["producer"],
                    "start_date": survey_data["start_date"],
                    "geographic_coverage": survey_data["geographic_coverage"],
                    "geographic_unit": survey_data["geographic_unit"],
                    "unit_of_analysis": survey_data["unit_of_analysis"],
                    "contact": survey_data["contact"],
                    "date_last_version": survey_data["date_last_version"],
                },
            )

            # Import variables once Survey object has been created
            num_new_variables, num_new_bindings = import_survey_variables(
                survey, survey_data["variables"]
            )
    except Exception as e:
        msg = f"DOI '{doi}': Erreur inattendue : {e!s}"
        raise ValueError(msg) from e
    finally:
        duration = time.time() - start_time
        duration_per_question = duration / num_questions
        logger.debug(
            "⏱ Temps d'import — Survey '%s', DOI '%s', %d Variables : Total %.2f s, Temps per question %.2f s",
            survey,
            doi,
            num_questions,
            duration,
            duration_per_question,
        )

    # If the survey had no URL, the XML came from the volume: delete it now that the
    # whole import (including the DB transaction) has succeeded. A later force_import
    # on this DOI will require a fresh upload, exactly as if none had ever been made.
    if import_format == IMPORT_FORMAT_DDIC and not survey_data.get("url", "").strip():
        UploadedDDICFile.objects.filter(doi=doi).delete()

    return {
        "num_records": num_questions,
        "num_new_variables": num_new_variables,
        "num_new_bindings": num_new_bindings,
    }


def validate_unique_variable_names(questions):
    """BindingSurveyRepresentedVariable has a unique constraint on (survey,
    variable_name): two questions in the same survey can never share the same
    variable_name. A poorly documented DDI-C file (typically a grid-type question)
    can produce this case. We detect it here, before any write, instead of letting
    the database raise an IntegrityError mid-save and leaving the survey half
    imported.
    """
    seen = {}
    for question in questions:
        name = question["name"]
        if name in seen:
            msg = (
                f"Le variable_name '{name}' apparaît plusieurs fois dans cette enquête "
                f"(questions en conflit : {seen[name]!r} / {question['text']!r}). "
                "Vérifiez la documentation DDI-C de cette enquête."
            )
            raise DataValidationError(msg)
        seen[name] = question["text"]


def import_survey_variables(survey, questions):
    batch_size = 200
    num_new_variables = 0
    num_new_bindings = 0
    represented_variables_to_save = []
    bindings_to_save = []
    for question in questions:
        variable_name = question["name"]
        variable_label = question["label"]
        question_text = question["text"]
        categories = question["categories"]
        universe = question["universe"]
        notes = question["notes"]

        # Always create categories as it is the most primitive model. Within the same
        # survey we can have duplicated categories and hence, we should save the models
        # to catch those duplicates
        categories, stats = get_or_create_categories(categories)

        # Get or make RepresentedVariable which is second most primitive model. Do not
        # "create" the variable ie do not save it. Save only at the end.
        # This avoids creating duplicates within the same survey which does not make
        # sense. However, it can happen in practice if DDI-C XML is not well documented
        # for grid type questions.
        represented_variable, represented_variable_created = get_or_make_represented_variable(
            question_text, variable_name, variable_label, categories
        )

        # If no represented variable created, ignore
        if not represented_variable:
            continue

        # If a new represented variable created, increase the counter and add model to
        # array so that we can save models later.
        if represented_variable_created:
            # We need to save both categories and variable as we need to first save
            # variable before we can set categories to the variable. Constraint due to
            # ManyToMany relation.
            represented_variables_to_save.append(
                {"categories": categories, "variable": represented_variable}
            )
            num_new_variables += 1

        # Now get or make BindingSurveyVariable model which depends on RepresentedVariable
        binding_survey_variable, binding_created = get_or_make_binding_survey_variable(
            survey, variable_name, universe, notes, represented_variable
        )

        # If a new binding variable created, increase the counter
        if binding_created:
            num_new_bindings += 1

        # Finally save binding_survey_variable and its corresponding categories and stats
        # in a list to create later
        bindings_to_save.append(
            {"binding": binding_survey_variable, "categories": categories, "stats": stats}
        )

    # First save the represented variable and then set categories
    for rv in represented_variables_to_save:
        rv["variable"].save()
        rv["variable"].categories.set(rv["categories"])

    # Index to elastic search for a given batch size so we avoid making
    # round trips for each variable
    bindings_to_index = []
    for b in bindings_to_save:
        # First save binding
        b["binding"].save()
        bindings_to_index.append(b["binding"])
        # Now get or create BindingVariableCategoryStat
        for category, stat in zip(b["categories"], b["stats"]):
            binding_stat, _ = BindingVariableCategoryStat.objects.get_or_create(
                binding=b["binding"], category=category
            )
            binding_stat.stat = stat
            binding_stat.save()

    # Index on ES at the end of each survey
    BindingSurveyDocument().update(bindings_to_index, batch_size)
    BindingSurveyRepresentedVariable.objects.filter(
        pk__in=[b.pk for b in bindings_to_index]
    ).update(is_indexed=True)
    BindingSurveyDocument._index.refresh()

    return num_new_variables, num_new_bindings


def get_or_create_categories(categories):
    category_objs = []
    stats = []
    for c in categories:
        category, _ = Category.objects.get_or_create(
            code=c["code"],
            category_label=Collate(
                Value(normalize_string_for_database(c["label"])),
                settings.DB_COLLATION,
            ),
        )
        if category.missing != c["missing"]:
            category.missing = c["missing"]
            category.save()
        category_objs.append(category)
        stats.append(c["stat"])
    return category_objs, stats


def get_or_make_represented_variable(question_text, variable_name, variable_label, categories):
    # Get normalized question text and variable label
    name_question_normalized = normalize_string_for_database(question_text)
    variable_label_normalized = normalize_string_for_database(variable_label)

    # Get list of categories IDs
    category_ids = [c.id for c in categories]

    # Assemble query variables
    # ALWAYS use the custom case accent insensitive collation that we defined
    # in the DB for variable_label, question_text and category labels.

    # If there is no question text and categories, ignore that variable
    if not name_question_normalized and not category_ids:
        return None, False

    # Now get all represented variables that have the same question text. The
    # following query will return all the represented variables that have same
    # question text but they might have different categories. These will be treated
    # as similar variables.
    #
    # If there is no question text, check if there are binding variables that have
    # same variable name
    if name_question_normalized:
        similar_represented_variables_qtext = RepresentedVariable.objects.filter(
            question_text=Collate(
                Value(name_question_normalized),
                settings.DB_COLLATION,
            )
        )
        # In case if variable label is not empty, further filter on the found represented
        # variables. If we found at least one result, we use it as found represented variable
        # and if not we use the found represented variables on the question text alone.
        if variable_label_normalized:
            similar_represented_variables_qtext_qlabel = similar_represented_variables_qtext.filter(
                internal_label=Collate(
                    Value(variable_label_normalized),
                    settings.DB_COLLATION,
                )
            )
            if len(similar_represented_variables_qtext_qlabel) > 0:
                similar_represented_variables = similar_represented_variables_qtext_qlabel
            else:
                similar_represented_variables = similar_represented_variables_qtext
        else:
            similar_represented_variables = similar_represented_variables_qtext
    elif variable_name:
        similar_represented_variables = [
            RepresentedVariable.objects.get(id=i)
            for i in BindingSurveyRepresentedVariable.objects.filter(
                variable_name=variable_name
            ).values_list("variable", flat=True)
        ]
    else:
        similar_represented_variables = []

    # Create a set of categories for comparison
    category_ids_set = set(category_ids)

    # Now check if the found similar represented variables have any "exact" match
    # which means comparing categories as well.
    # If found, return there is noting to do.
    for rvar in similar_represented_variables:
        if set(rvar.categories.all().values_list("id", flat=True)) == category_ids_set:
            return rvar, False

    # If no exact represented variable found, create a new one.
    # If there are similar represented variables found, DO NOT CREATE new concept and
    # use the concept of similar represented variables
    if len(similar_represented_variables) > 0:
        conceptual_var = similar_represented_variables[0].conceptual_var
    else:
        conceptual_var = ConceptualVariable.objects.create(
            is_unique=not bool(name_question_normalized)
        )

    # Create new represented variable
    represented_variable = RepresentedVariable(
        conceptual_var=conceptual_var,
        question_text=name_question_normalized,
        internal_label=variable_label_normalized,
        is_unique=not bool(name_question_normalized),
    )
    return represented_variable, True


def get_or_make_binding_survey_variable(
    survey, variable_name, universe, notes, represented_variable
):
    binding_created = False

    # Now attempt to get existant binding variable based on unique fields
    binding = BindingSurveyRepresentedVariable.objects.filter(
        survey=survey, variable_name=variable_name
    ).first()

    # If binding variable exists, update all the relevant fields
    # else create a new one
    if binding:
        binding.variable = represented_variable
        binding.universe = universe
        binding.notes = notes
    else:
        binding = BindingSurveyRepresentedVariable(
            survey=survey,
            variable=represented_variable,
            variable_name=variable_name,
            universe=universe,
            notes=notes,
        )
        binding_created = True
    return binding, binding_created
