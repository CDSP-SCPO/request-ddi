import csv
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.shortcuts import render
from .forms import CSVUploadForm
from .models import Survey, RepresentedVariable, ConceptualVariable, Category, BindingSurveyRepresentedVariable, \
    Concept, BindingConcept


class CSVUploadView(FormView):
    template_name = 'upload_csv.html'  # Template pour le formulaire
    form_class = CSVUploadForm
    success_url = reverse_lazy('upload_success')  # URL de redirection après succès
    required_columns = ['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label']

    def form_valid(self, form):
        csv_file = form.cleaned_data['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        sample = '\n'.join(decoded_file[:2])
        sniffer = csv.Sniffer()
        has_header = sniffer.has_header(sample)
        delimiter = sniffer.sniff(sample).delimiter
        reader = csv.DictReader(decoded_file, delimiter=delimiter)
        missing_columns = [col for col in self.required_columns if col not in reader.fieldnames]
        if missing_columns:
            return render(self.request, self.template_name, {
                'form': form,
                'missing_columns': missing_columns,
            })

        for row in reader:
            # Exemple d'insertion des données dans les modèles
            survey, _ = Survey.objects.get_or_create(
                external_ref=row['ddi'],
                name=row['title']
            )
            name_question = row['question_text']

            var_represented = RepresentedVariable.objects.filter(question_text=name_question).first()
            if var_represented != None and name_question == var_represented.question_text:
                if check_category(row['category_label'], var_represented.categories):
                    BindingSurveyRepresentedVariable.objects.get_or_create(survey=survey, variable=var_represented,
                                                                           variable_name=row['variable_name'])
                else:
                    new_categories = create_new_categories(row['category_label'])

                    new_represented_var, _ = RepresentedVariable.objects.get_or_create(
                        conceptual_var=var_represented.conceptual_var, question_text=name_question)
                    for i in range(len(new_categories)):
                        new_represented_var.categories.add(new_categories[i])

                    BindingSurveyRepresentedVariable.objects.get_or_create(survey=survey, variable=new_represented_var,
                                                                           variable_name=row['variable_name'])
            else:

                new_conceptual_var = ConceptualVariable.objects.create()
                new_represented = RepresentedVariable.objects.create(conceptual_var=new_conceptual_var,
                                                                     question_text=name_question)
                new_categories = create_new_categories(row['category_label'])
                for i in range(len(new_categories)):
                    new_represented.categories.add(new_categories[i])
                BindingSurveyRepresentedVariable.objects.get_or_create(survey=survey, variable=new_represented,
                                                                       variable_name=row['variable_name'])
        return super().form_valid(form)


def parse_categories(csv_category_string):
    categories = []
    csv_category_pairs = csv_category_string.split(" | ")
    for pair in csv_category_pairs:
        code, label = pair.split(",", 1)
        categories.append((code.strip(), label.strip()))

    return categories


def check_category(csv_category_string, existing_categories):
    csv_categories = []
    if csv_category_string != "":
        csv_categories = parse_categories(csv_category_string)

    existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]

    return set(csv_categories) == set(existing_categories_list)


def create_new_categories(csv_category_string):
    new_categories = []
    if csv_category_string != "":

        csv_categories = parse_categories(csv_category_string)

        for code, label in csv_categories:
            category, created = Category.objects.get_or_create(
                code=code,
                category_label=label,
                type='code'  # Ajuster si besoin
            )
            new_categories.append(category)

    return new_categories
