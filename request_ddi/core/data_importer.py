# -- STDLIB
import logging
import time

from request_ddi.utils.normalize_string import (
    normalize_string_for_comparison,
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
batch_size = 50


class DataImporter:
    def __init__(self):
        self.errors = []

    def import_data(self, question_datas):  # noqa: PLR0912, C901, PLR0915
        batch_size = 50
        num_records = 0
        num_new_variables = 0
        num_new_bindings = 0
        bindings_to_index = []

        data_by_doi = {}
        for question_data in question_datas:
            doi = question_data[0]
            data_by_doi.setdefault(doi, []).append(question_data)

        cleaned_questions = RepresentedVariable.get_cleaned_question_texts()
        dois = list(data_by_doi.keys())
        existing_surveys = Survey.objects.filter(external_ref__in=dois)
        surveys_dict = {survey.external_ref: survey for survey in existing_surveys}
        missing_dois = set(dois) - set(surveys_dict.keys())

        for doi, questions in data_by_doi.items():
            start_time = time.time()
            try:
                if doi in missing_dois:
                    msg = f"Survey with DOI {doi} not found"
                    raise Survey.DoesNotExist(msg)

                survey = surveys_dict[doi]
                for question_data in questions:
                    (
                        variable_name,
                        variable_label,
                        question_text,
                        category_label,
                        universe,
                        notes,
                    ) = question_data[1:]
                    placeholder_rv = None
                    binding = BindingSurveyRepresentedVariable.objects.filter(
                        survey=survey, variable_name=variable_name
                    ).first()
                    if not binding:
                        placeholder_rv = self.create_placeholder_rv(variable_label)
                        binding = BindingSurveyRepresentedVariable.objects.create(
                            survey=survey,
                            variable=placeholder_rv,
                            variable_name=variable_name,
                            universe=universe,
                            notes=notes,
                        )
                    represented_variable, created_variable = (
                        self.get_or_create_represented_variable(
                            variable_name,
                            question_text,
                            category_label,
                            variable_label,
                            survey,
                            binding,
                            cleaned_questions,
                        )
                    )
                    binding.variable = represented_variable
                    binding.save()

                    if placeholder_rv:
                        conceptual = placeholder_rv.conceptual_var
                        placeholder_rv.delete()
                        if conceptual.representedvariable_set.count() == 0:
                            conceptual.delete()

                    if created_variable:
                        num_new_variables += 1

                    binding, created_or_changed_binding = self.get_or_create_binding(
                        survey, represented_variable, variable_name, universe, notes
                    )

                    if created_or_changed_binding:
                        num_new_bindings += 1
                        bindings_to_index.append(binding)

                        if len(bindings_to_index) >= batch_size:
                            BindingSurveyDocument().update(bindings_to_index)
                            BindingSurveyRepresentedVariable.objects.filter(
                                pk__in=[b.pk for b in bindings_to_index]
                            ).update(is_indexed=True)
                            bindings_to_index = []

                    num_records += 1

            except Survey.DoesNotExist:
                self.errors.append(f"DOI '{doi}' non trouvé dans la base de données.")
            except ValueError as ve:
                self.errors.append(f"DOI '{doi}': Erreur de valeur : {ve}")
            except Exception as e:
                self.errors.append(f"DOI '{doi}': Erreur inattendue : {e!s}")
            finally:
                duration = time.time() - start_time
                logger.debug(
                    "⏱ Temps d'import — Survey '%s', DOI '%s' : %.2f s",
                    survey,
                    doi,
                    duration,
                )

        if bindings_to_index:
            BindingSurveyDocument().update(bindings_to_index)
            BindingSurveyRepresentedVariable.objects.filter(
                pk__in=[b.pk for b in bindings_to_index]
            ).update(is_indexed=True)

        if self.errors:
            error_summary = "<br/>".join(self.errors)
            msg = f"Erreurs rencontrées :<br/> {error_summary}"
            raise ValueError(msg)

        return num_records, num_new_variables, num_new_bindings

    def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes):
        # Étape 1 : on cherche un binding existant via survey + variable_name
        binding = BindingSurveyRepresentedVariable.objects.filter(
            survey=survey, variable_name=variable_name
        ).first()

        if binding:
            changed = (
                binding.variable != represented_variable
                or binding.universe != universe
                or binding.notes != notes
            )
            if changed:
                binding.variable = represented_variable
                binding.universe = universe
                binding.notes = notes
                binding.save()
        else:
            # Sinon, on le crée
            binding = BindingSurveyRepresentedVariable.objects.create(
                survey=survey,
                variable=represented_variable,
                variable_name=variable_name,
                universe=universe,
                notes=notes,
            )
            changed = True

        return binding, changed

    def check_category(self, category_string, existing_categories):
        csv_categories = (
            [
                (
                    code,
                    normalize_string_for_comparison(normalize_string_for_database(label)),
                )
                for code, label, stat, missing in self.parse_categories(category_string)
            ]
            if category_string
            else []
        )
        existing_categories_list = [
            (category.code, normalize_string_for_comparison(category.category_label))
            for category in existing_categories.all()
        ]

        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            stat, code, label, miss = pair.split(r" \ ", 3)
            missing = miss == "missing"
            categories.append((code.strip(), label.strip(), stat.strip(), missing))
        return categories

    def create_new_categories(self, category_string, binding):
        categories = []
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label, stat, missing in parsed_categories:
                category, _ = Category.objects.get_or_create(
                    code=code,
                    category_label=normalize_string_for_database(label),
                )
                if category.missing != missing:
                    category.missing = missing
                    category.save()
                categories.append(category)
                binding_stat, _ = BindingVariableCategoryStat.objects.get_or_create(
                    binding=binding, category=category
                )
                binding_stat.stat = stat
                binding_stat.save()
        return categories

    def create_new_represented_variable(
        self,
        conceptual_var,
        name_question_normalized,
        category_label,
        variable_label,
        binding,
        is_unique: bool = False,
    ):
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=name_question_normalized,
            internal_label=variable_label,
            is_unique=is_unique,
        )
        new_categories = self.create_new_categories(category_label, binding)
        new_represented_var.categories.set(new_categories)

        return new_represented_var

    def get_or_create_represented_variable(
        self,
        variable_name,
        question_text,
        category_label,
        variable_label,
        survey,
        binding,
        cleaned_questions,
    ):
        name_question_for_database = normalize_string_for_database(question_text)
        name_question_for_comparison = normalize_string_for_comparison(name_question_for_database)

        if not name_question_for_comparison:
            # Cas particulier : pas de texte de question → on regarde si déjà lié par nom
            existing_binding = (
                BindingSurveyRepresentedVariable.objects.filter(
                    variable_name=variable_name, survey=survey
                )
                .exclude(variable__question_text=None)
                .first()
            )
            if existing_binding:
                self.maj_stats_categories(
                    existing_binding, category_label, existing_binding.variable
                )
                return existing_binding.variable, False
            else:
                conceptual_var = ConceptualVariable.objects.create(is_unique=True)
                return self.create_new_represented_variable(
                    conceptual_var,
                    name_question_for_database,
                    category_label,
                    variable_label,
                    binding,
                    is_unique=True,
                ), True

        if name_question_for_comparison in cleaned_questions:
            var_represented_list = cleaned_questions[name_question_for_comparison]

            for var in var_represented_list:
                if self.check_category(category_label, var.categories):
                    self.maj_stats_categories(binding, category_label, var)
                    return var, False  # ✅ Variable existante avec mêmes catégories

            # Aucun match exact sur les catégories → on crée une nouvelle liée à
            # la même conceptuelle
            var = var_represented_list[0]  # Pour attacher à la même conceptuelle et logguer

            return self.create_new_represented_variable(
                var.conceptual_var,
                name_question_for_database,
                category_label,
                variable_label,
                binding,
            ), True

        # ❌ Texte inconnu → nouvelle variable conceptuelle + représentée
        conceptual_var = ConceptualVariable.objects.create()
        return self.create_new_represented_variable(
            conceptual_var, name_question_for_database, category_label, variable_label, binding
        ), True

    def create_placeholder_rv(self, variable_label):
        conceptual = ConceptualVariable.objects.create(is_unique=True)
        return RepresentedVariable.objects.create(
            conceptual_var=conceptual,
            question_text=None,
            internal_label=variable_label,
            type="question",
            type_categories="text",
            is_unique=True,
        )

    def maj_stats_categories(self, binding, category_label, rv=None):
        self.create_new_categories(category_label, binding)
