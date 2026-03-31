# -- STDLIB
import logging
import time

from django.conf import settings
from django.db.models import Count, Value
from django.db.models.functions import Collate

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


class DataImporter:
    def __init__(self):
        self.errors = []

    def import_data(self, question_datas):
        num_records = 0
        num_new_variables = 0
        num_new_bindings = 0

        data_by_doi = {}
        for question_data in question_datas:
            doi = question_data[0]
            data_by_doi.setdefault(doi, []).append(question_data)

        dois = list(data_by_doi.keys())
        existing_surveys = Survey.objects.filter(external_ref__in=dois)
        surveys_dict = {survey.external_ref: survey for survey in existing_surveys}
        missing_dois = set(dois) - set(surveys_dict.keys())
        for doi, questions in data_by_doi.items():
            num_questions = len(questions)
            start_time = time.time()
            try:
                if doi in missing_dois:
                    msg = f"Survey with DOI {doi} not found"
                    survey = "N/A"
                    raise Survey.DoesNotExist(msg)

                survey = surveys_dict[doi]
                new_represented_vars_survey, new_bindings_survey = self._import_survey_data(
                    survey, questions
                )
                num_new_variables += new_represented_vars_survey
                num_new_bindings += new_bindings_survey
                num_records += num_questions
            except Survey.DoesNotExist:
                self.errors.append(f"DOI '{doi}' non trouvé dans la base de données.")
            except ValueError as ve:
                self.errors.append(f"DOI '{doi}': Erreur de valeur : {ve}")
            except Exception as e:
                self.errors.append(f"DOI '{doi}': Erreur inattendue : {e!s}")
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

        if self.errors:
            error_summary = "<br/>".join(self.errors)
            msg = f"Erreurs rencontrées :<br/> {error_summary}"
            raise ValueError(msg)

        return num_records, num_new_variables, num_new_bindings

    def _import_survey_data(self, survey, questions):
        batch_size = 200
        num_new_variables = 0
        num_new_bindings = 0
        bindings_to_index = []
        for question_data in questions:
            (
                variable_name,
                variable_label,
                question_text,
                category_label,
                universe,
                notes,
            ) = question_data[1:]

            # Always create categories as it is the most primitive model
            categories, stats = self.get_or_create_categories(category_label)

            # Get or create RepresentedVariable which is second most primitive model
            represented_variable, represented_variable_created = (
                self.get_or_create_represented_variable(question_text, variable_label, categories)
            )

            # If no represented variable created, ignore
            if not represented_variable:
                continue

            # If a new represented variable created, increase the counter
            if represented_variable_created:
                num_new_variables += 1

            # Now get or create BindingSurveyVariable which depends on RepresentedVariable
            binding_survey_variable, binding_created = self.get_or_create_binding_survey_variable(
                survey, variable_name, universe, notes, represented_variable
            )

            # If a new binding variable created, increase the counter
            if binding_created:
                num_new_bindings += 1

            # Finally once we have BindingSurveyVariable variable, get or create BindingVariableCategoryStat for each
            # category
            self.get_or_create_binding_variable_category_stat(
                categories, stats, binding_survey_variable
            )

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

    def parse_categories(self, category_string):
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            stat, code, label, miss = pair.split(r" \ ", 3)
            missing = miss == "missing"
            categories.append((code.strip(), label.strip(), stat.strip(), missing))
        return categories

    def get_or_create_categories(self, category_string):
        categories = []
        stats = []
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label, stat, missing in parsed_categories:
                category, _ = Category.objects.get_or_create(
                    code=code,
                    category_label=Collate(
                        Value(normalize_string_for_database(label)),
                        settings.DB_COLLATION,
                    ),
                )
                if category.missing != missing:
                    category.missing = missing
                    category.save()
                categories.append(category)
                stats.append(stat)
        return categories, stats

    def get_or_create_represented_variable(self, question_text, variable_label, categories):
        represented_variable_created = False

        # Get normalized question text and variable label
        name_question_normalized = normalize_string_for_database(question_text)
        variable_label_normalized = normalize_string_for_database(variable_label)

        # Get list of categories IDs
        category_ids = [c.id for c in categories]

        # Initialise query dict
        query = {}

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

        # If question_text is not empty add it to query
        if name_question_normalized:
            query.update(
                {
                    "question_text": Collate(
                        Value(name_question_normalized),
                        settings.DB_COLLATION,
                    )
                }
            )

        # If there are categories, add it to query
        if category_ids:
            query.update({"categories__in": category_ids})

        # If query is empty, ignore this variable
        if not query:
            return None, False

        # Now get a represented variable based on question text, categories and internal_label
        # The following query returns the represented variables with exactly same categories
        # as in category_ids.
        # Without this query, we will get ALL the represented variables where category_ids
        # partially present.
        represented_variables = (
            RepresentedVariable.objects.filter(**query)
            .annotate(num_categories=Count("categories"))
            .filter(num_categories=len(category_ids))
        )

        represented_variable = None
        category_ids_set = set(category_ids)

        # Even after filtering categories based on count, we might end up in a situation
        # where our queried categories are [1, 2] and found represented variable categories
        # are [2, 3]. As the length of categories in both cases is 2, they will be matched
        # and returned. To avoid this case, we finally compare the category IDs of queried
        # variable and found variables and break the loop when IDs are matched.
        for rvar in represented_variables:
            if set(rvar.categories.all().values_list("id", flat=True)) == category_ids_set:
                represented_variable = rvar
                break

        # If no represented variable found, create one
        # Set is_unique based on the existence of question text
        if not represented_variable:
            conceptual_var = ConceptualVariable.objects.create(
                is_unique=not bool(name_question_normalized)
            )
            represented_variable = RepresentedVariable.objects.create(
                conceptual_var=conceptual_var,
                question_text=name_question_normalized,
                internal_label=variable_label_normalized,
                is_unique=not bool(name_question_normalized),
            )
            represented_variable_created = True

        # ALWAYS update the categories of the existant or created represented variable
        represented_variable.categories.set(categories)
        return represented_variable, represented_variable_created

    def get_or_create_binding_survey_variable(
        self, survey, variable_name, universe, notes, represented_variable
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

    def get_or_create_binding_variable_category_stat(self, categories, stats, binding):
        for category, stat in zip(categories, stats):
            binding_stat, _ = BindingVariableCategoryStat.objects.get_or_create(
                binding=binding, category=category
            )
            binding_stat.stat = stat
            binding_stat.save()
