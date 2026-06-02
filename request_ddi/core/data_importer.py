# -- STDLIB
import logging
import time

from django.conf import settings
from django.db.models import Value
from django.db.models.functions import Collate
from django.tasks import task

from request_ddi.utils.normalize_string import (
    normalize_string_for_database,
)

# -- REQUEST_DDI (LOCAL)
from .documents import BindingSurveyDocument
from .models import (
    BindingSurveyRepresentedVariable,
    BindingVariableCategoryStat,
    Category,
    ConceptualVariable,
    RepresentedVariable,
    Survey,
)

logger = logging.getLogger("performance")


@task(takes_context=True)
def import_data(context, survey_data):
    num_questions = len(survey_data["variables"])
    doi = survey_data["doi"]
    start_time = time.time()
    try:
        # Get survey model from DB
        survey = Survey.objects.get(external_ref=doi)
        num_new_variables, num_new_bindings = import_survey_variables(
            survey, survey_data["variables"]
        )
    except Survey.DoesNotExist as err:
        msg = f"DOI '{doi}' non trouvé dans la base de données."
        raise ValueError(msg) from err
    except ValueError as ve:
        msg = f"DOI '{doi}': Erreur de valeur : {ve}"
        raise ValueError(msg) from ve
    except Exception as e:
        msg = f"DOI '{doi}': Erreur inattendue : {e!s}"
        raise ValueError(msg) from e
    finally:
        duration = time.time() - start_time
        logger.debug(
            "⏱ Temps d'import — Survey '%s', DOI '%s', %d Variables : Total %.2f s, Temps per question %.2f s",
            survey,
            doi,
            num_questions,
            duration,
            duration / num_questions,
        )

    return {
        "num_records": num_questions,
        "num_new_variables": num_new_variables,
        "num_new_bindings": num_new_bindings,
    }


def import_survey_variables(survey, questions):
    batch_size = 200
    num_new_variables = 0
    num_new_bindings = 0
    bindings_to_index = []
    for question in questions:
        variable_name = question["name"]
        variable_label = question["label"]
        question_text = question["text"]
        categories = question["categories"]
        universe = question["universe"]
        notes = question["notes"]

        # Always create categories as it is the most primitive model
        categories, stats = get_or_create_categories(categories)

        # Get or create RepresentedVariable which is second most primitive model
        represented_variable, represented_variable_created = get_or_create_represented_variable(
            question_text, variable_name, variable_label, categories
        )

        # If no represented variable created, ignore
        if not represented_variable:
            continue

        # If a new represented variable created, increase the counter
        if represented_variable_created:
            num_new_variables += 1

        # Now get or create BindingSurveyVariable which depends on RepresentedVariable
        binding_survey_variable, binding_created = get_or_create_binding_survey_variable(
            survey, variable_name, universe, notes, represented_variable
        )

        # If a new binding variable created, increase the counter
        if binding_created:
            num_new_bindings += 1

        # Finally once we have BindingSurveyVariable variable, get or create BindingVariableCategoryStat for each
        # category
        get_or_create_binding_variable_category_stat(categories, stats, binding_survey_variable)

        # Index to elastic search for a given batch size so we avoid making
        # round trips for each variable
        bindings_to_index.append(binding_survey_variable)

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


def get_or_create_represented_variable(question_text, variable_name, variable_label, categories):
    # Get normalized question text and variable label
    name_question_normalized = normalize_string_for_database(question_text)
    variable_label_normalized = normalize_string_for_database(variable_label)

    # Get list of categories IDs
    category_ids = [c.id for c in categories]

    # Assemble query variables
    # ALWAYS use the custom case accent insensitive collation that we defined
    # in the DB for variable_label, question_text and category labels.

    # We don't use the internal label nor the variable name to determine whether two variables
    # are similar or identical. We have to stick with the question text and the categories only.
    # if variable_label_normalized:
    #     print("test variable_label_normalized")
    #     query.update(
    #         {
    #             "internal_label": Collate(
    #                 Value(variable_label_normalized),
    #                 settings.DB_COLLATION,
    #             )
    #         }
    #     )

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
        similar_represented_variables = RepresentedVariable.objects.filter(
            question_text=Collate(
                Value(name_question_normalized),
                settings.DB_COLLATION,
            )
        )
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
    represented_variable = RepresentedVariable.objects.create(
        conceptual_var=conceptual_var,
        question_text=name_question_normalized,
        internal_label=variable_label_normalized,
        is_unique=not bool(name_question_normalized),
    )

    # Update the categories of the existant or created represented variable
    represented_variable.categories.set(categories)
    return represented_variable, True


def get_or_create_binding_survey_variable(
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
        binding.save()
    else:
        binding = BindingSurveyRepresentedVariable.objects.create(
            survey=survey,
            variable=represented_variable,
            variable_name=variable_name,
            universe=universe,
            notes=notes,
        )
        binding_created = True
    return binding, binding_created


def get_or_create_binding_variable_category_stat(categories, stats, binding):
    for category, stat in zip(categories, stats):
        binding_stat, _ = BindingVariableCategoryStat.objects.get_or_create(
            binding=binding, category=category
        )
        binding_stat.stat = stat
        binding_stat.save()
