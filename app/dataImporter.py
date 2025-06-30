from .documents import BindingSurveyDocument
from .models import Survey, BindingSurveyRepresentedVariable, RepresentedVariable, ConceptualVariable, Category
from .utils.normalize_string import (
    normalize_string_for_comparison, normalize_string_for_database,
)
import time
class DataImporter:
    def __init__(self):
        self.errors = []

    def import_data(self, question_datas):
        num_records = 0
        num_new_surveys = 0
        num_new_variables = 0
        num_new_bindings = 0

        data_by_doi = {}
        for question_data in question_datas:
            doi = question_data[0]
            data_by_doi.setdefault(doi, []).append(question_data)

        bindings_to_index = []

        for doi, questions in data_by_doi.items():
            start_time = time.time()
            try:
                survey = Survey.objects.get(external_ref=doi)
                for question_data in questions:
                    variable_name, variable_label, question_text, category_label, universe, notes = question_data[1:]

                    represented_variable, created_variable = self.get_or_create_represented_variable(
                        variable_name, question_text, category_label, variable_label
                    )

                    if created_variable:
                        num_new_variables += 1

                    binding, created_binding = self.get_or_create_binding(
                        survey, represented_variable, variable_name, universe, notes
                    )

                    if created_binding:
                        num_new_bindings += 1
                        bindings_to_index.append(binding)

                    num_records += 1

            except Survey.DoesNotExist:
                self.errors.append(f"DOI '{doi}' non trouvé dans la base de données.")
            except ValueError as ve:
                self.errors.append(f"DOI '{doi}': Erreur de valeur : {ve}")
            except Exception as e:
                self.errors.append(f"DOI '{doi}': Erreur inattendue : {str(e)}")
            finally:
                duration = time.time() - start_time
                print(f"⏱ Traitement du DOI '{doi}' : {duration:.2f} secondes")

        if self.errors:
            error_summary = "<br/>".join(self.errors)
            raise ValueError(f"Erreurs rencontrées :<br/> {error_summary}")

        start_update_time = time.time()
        for binding in bindings_to_index:
            BindingSurveyDocument().update(binding)
        update_duration = time.time() - start_update_time
        print(f"⏱ Indexation des bindings : {update_duration:.2f} secondes")

        return num_records, num_new_surveys, num_new_variables, num_new_bindings

    def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes):
        try:
            binding, created = BindingSurveyRepresentedVariable.objects.get_or_create(
                variable_name=variable_name,
                survey=survey,
                variable=represented_variable,
                defaults={
                    'survey': survey,
                    'variable': represented_variable,
                    'universe': universe,
                    'notes': notes,
                }
            )
        except BindingSurveyRepresentedVariable.MultipleObjectsReturned:
            bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name)
            if all(binding.variable == represented_variable for binding in bindings):
                binding = bindings.first()
                created = False
            else:
                raise ValueError(
                    "Multiple bindings found with the same variable_name but different represented_variable.")

        if not created:
            binding.survey = survey
            binding.variable = represented_variable
            binding.universe = universe
            binding.notes = notes
            binding.save()

        return binding, created

    def check_category(self, category_string, existing_categories):
        csv_categories = [(code, normalize_string_for_comparison(normalize_string_for_database(label))) for code, label
                          in self.parse_categories(category_string)] if category_string else []
        existing_categories_list = [(category.code, normalize_string_for_comparison(category.category_label)) for
                                    category in existing_categories.all()]

        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories

    def create_new_categories(self, category_string):
        categories = []
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(code=code,
                                                             category_label=normalize_string_for_database(label))
                categories.append(category)
        return categories

    def create_new_represented_variable(self, conceptual_var, name_question_normalized, category_label,
                                        variable_label, is_unique: bool = False):
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=name_question_normalized,
            internal_label=variable_label,
            is_unique=is_unique,
        )
        new_categories = self.create_new_categories(category_label)
        new_represented_var.categories.set(new_categories)
        return new_represented_var

    def get_or_create_represented_variable(self, variable_name, question_text, category_label, variable_label):
        name_question_for_database = normalize_string_for_database(question_text)
        name_question_for_comparison = normalize_string_for_comparison(name_question_for_database)

        cleaned_questions = RepresentedVariable.get_cleaned_question_texts()

        if name_question_for_comparison:
            if name_question_for_comparison in cleaned_questions:
                var_represented = RepresentedVariable.objects.filter(
                    question_text=cleaned_questions[name_question_for_comparison].question_text,
                )
                for var in var_represented:
                    if self.check_category(category_label, var.categories):
                        return var, False
                return self.create_new_represented_variable(var_represented[0].conceptual_var,
                                                            name_question_for_database, category_label,
                                                            variable_label), True
            else:
                conceptual_var = ConceptualVariable.objects.create()
                return self.create_new_represented_variable(conceptual_var, name_question_for_database,
                                                            category_label,
                                                            variable_label), True
        else:
            conceptual_var = ConceptualVariable.objects.create(is_unique=True)
            return self.create_new_represented_variable(conceptual_var, name_question_for_database,
                                                        category_label,
                                                        variable_label), True
