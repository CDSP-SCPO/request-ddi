import csv
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib import messages
from .forms import CSVUploadForm
from django.views.generic import ListView
from django.db.models import Q
from .models import Survey, RepresentedVariable, ConceptualVariable, Category, BindingSurveyRepresentedVariable, \
    Concept, BindingConcept

from django.http import JsonResponse


class CSVUploadView(FormView):
    template_name = 'upload_csv.html'
    form_class = CSVUploadForm
    success_url = reverse_lazy('app:upload_success')
    required_columns = ['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label']

    def form_valid(self, form):
        csv_file = form.cleaned_data['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        sample = '\n'.join(decoded_file[:2])
        sniffer = csv.Sniffer()
        has_header = sniffer.has_header(sample)
        delimiter = sniffer.sniff(sample).delimiter
        reader = csv.DictReader(decoded_file, delimiter=delimiter)

        missing_columns = self.validate_columns(reader.fieldnames)
        if missing_columns:
            return self.render_with_errors(form, missing_columns)

        try:
            self.process_csv(reader)
            messages.success(self.request, "CSV file processed successfully.")
        except Exception as e:
            messages.error(self.request, f"An error occurred: {str(e)}")
            return self.render_with_errors(form)

        return super().form_valid(form)

    def validate_columns(self, fieldnames):
        return [col for col in self.required_columns if col not in fieldnames]

    def render_with_errors(self, form, missing_columns=None):
        context = {'form': form}
        if missing_columns:
            context['missing_columns'] = missing_columns
        return render(self.request, self.template_name, context)

    def process_csv(self, reader):
        for row in reader:
            survey = self.get_or_create_survey(row)
            represented_variable = self.get_or_create_represented_variable(row, survey)
            self.get_or_create_binding(survey, represented_variable, row['variable_name'])

    def get_or_create_survey(self, row):
        survey, _ = Survey.objects.get_or_create(
            external_ref=row['ddi'],
            name=row['title']
        )
        return survey

    def get_or_create_represented_variable(self, row, survey):
        name_question = row['question_text']
        var_represented = RepresentedVariable.objects.filter(question_text=name_question).first()

        if var_represented and name_question == var_represented.question_text:
            if self.check_category(row['category_label'], var_represented.categories):
                return var_represented
            else:
                return self.create_new_represented_variable(row, var_represented.conceptual_var, name_question)
        else:
            return self.create_new_represented_variable(row, ConceptualVariable.objects.create(), name_question)

    def create_new_represented_variable(self, row, conceptual_var, name_question):
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=name_question
        )
        new_categories = self.create_new_categories(row['category_label'])
        new_represented_var.categories.set(new_categories)
        return new_represented_var

    def create_new_categories(self, csv_category_string):
        categories = []
        if csv_category_string:
            parsed_categories = self.parse_categories(csv_category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(
                    code=code,
                    category_label=label
                )
                categories.append(category)
        return categories

    def get_or_create_binding(self, survey, represented_variable, variable_name):
        BindingSurveyRepresentedVariable.objects.get_or_create(
            survey=survey,
            variable=represented_variable,
            variable_name=variable_name
        )

    def check_category(self, csv_category_string, existing_categories):
        csv_categories = self.parse_categories(csv_category_string) if csv_category_string else []
        existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]
        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, csv_category_string):
        categories = []
        csv_category_pairs = csv_category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories


class RepresentedVariableSearchView(ListView):
    model = RepresentedVariable
    template_name = 'homepage.html'  # Nom du template
    context_object_name = 'variables'  # Nom du contexte utilisé dans le template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['surveys'] = Survey.objects.all()
        return context


def search_results(request):
    # Render the template that contains the DataTable
    return render(request, 'search_results.html')


def search_results_data(request):
    search_value = request.GET.get('q', '')  # Récupérer le mot clé de recherche
    questions = RepresentedVariable.objects.all()
    
    if search_value:
        questions = questions.filter(
            Q(question_text__icontains=search_value)
        ).distinct()

    # Format attendu par DataTables : une liste de dictionnaires avec les champs requis
    data = []
    for question in questions:
        data.append({
            "id": question.id,
            "question_text": question.question_text,
            "internal_label": question.internal_label or "N/A"  # Assure que ce champ ne soit pas null
        })

    # Retourner la réponse au format JSON pour DataTables
    return JsonResponse({"data": data})