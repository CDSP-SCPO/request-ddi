# -- STDLIB
import csv
import os
from datetime import datetime

# -- DJANGO
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
# views.py
from django.views.decorators.csrf import csrf_exempt

# -- THIRDPARTY
from bs4 import BeautifulSoup

# -- BASEDEQUESTIONS (LOCAL)
from .models import (
    BindingSurveyRepresentedVariable, Distributor, Subcollection, Survey,
)
from .utils.sort import alphanum_key
from .views_utils import check_file_access


def similar_representative_variable_questions(request, question_id):
    question = get_object_or_404(BindingSurveyRepresentedVariable, id=question_id)

    rep_variable = question.variable
    questions_from_rep_variable = BindingSurveyRepresentedVariable.objects.filter(variable=rep_variable).exclude(
        id=question_id)

    data = []
    for similar_question in questions_from_rep_variable:
        data.append({
            "id": similar_question.id,
            "variable_name": similar_question.variable_name,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey": similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_rep_variable),
        "recordsFiltered": len(questions_from_rep_variable),
        "data": data
    })

def similar_conceptual_variable_questions(request, question_id):
    question = get_object_or_404(BindingSurveyRepresentedVariable, id=question_id)
    rep_variable = question.variable

    conceptual_variable = rep_variable.conceptual_var

    questions_from_conceptual_variable = BindingSurveyRepresentedVariable.objects.filter(
        variable__conceptual_var=conceptual_variable).exclude(id=question_id)

    data = []
    for similar_question in questions_from_conceptual_variable:
        data.append({
            "id": similar_question.id,
            "variable_name": similar_question.variable_name,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey": similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_conceptual_variable),
        "recordsFiltered": len(questions_from_conceptual_variable),
        "data": data
    })


@csrf_exempt
def check_duplicates(request):
    if request.method == 'POST':
        # Récupérer soit le fichier CSV, soit le fichier XML
        file = request.FILES.get('csv_file') or request.FILES.get('xml_file')

        if not file:
            return JsonResponse({'error': 'Aucun fichier fourni'}, status=400)
        decoded_file = file.read().decode('utf-8', errors='replace').splitlines()

        # Vérifier si c'est un fichier XML
        if file.name.endswith('.xml'):
            soup = BeautifulSoup("\n".join(decoded_file), 'xml')
            existing_variables = []
            variable_survey_id = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo",
                                                                                                           attrs={
                                                                                                               "agency": "DataCite"}) else soup.find(
                "IDNo").text.strip()
            for var in soup.find_all('var'):
                variable_name = var.get('name', '').strip()
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name,
                                                                                    survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)

        # Vérifier si c'est un fichier CSV
        elif file.name.endswith('.csv'):
            reader = csv.DictReader(decoded_file)
            existing_variables = []
            for row in reader:
                variable_name = row['variable_name']
                variable_survey_id = row['doi']
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name,
                                                                                    survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)

        else:
            return JsonResponse({'error': 'Format de fichier non supporté'}, status=400)
        if existing_variables:
            return JsonResponse({'status': 'exists', 'existing_variables': existing_variables})
        else:
            return JsonResponse({'status': 'no_duplicates'})

    return JsonResponse({'error': 'Requête invalide'}, status=400)


def get_surveys_by_collections(request):
    collections_ids = request.GET.get('collections_ids')
    if collections_ids:
        collections_ids = [int(id) for id in collections_ids.split(',')]
        surveys = Survey.objects.filter(subcollection__collection__id__in=collections_ids).order_by('name')
    else:
        surveys = Survey.objects.all().order_by('name')

    surveys_data = [{'id': survey.id, 'name': survey.name} for survey in surveys]
    return JsonResponse({'surveys': surveys_data})


def create_distributor(request):
    if request.method == "POST":
        name = request.POST.get('name')
        if name:
            Distributor.objects.get_or_create(name=name)
            return JsonResponse({"success": True, "message": "Diffuseur ajouté avec succès."})
        return JsonResponse({"success": False, "message": "Le nom du diffeuseur est requis."})
    return JsonResponse({"success": False, "message": "Requête invalide."})



def get_distributor(request):
    distributors = Distributor.objects.all().values("id", "name")
    return JsonResponse({"distributors": list(distributors)})



def get_subcollections_by_collections(request):
    collection_ids = request.GET.get('collections_ids', '').split(',')
    collection_ids = [id for id in collection_ids if id]

    if not collection_ids:
        subcollections = Subcollection.objects.all().order_by('name')
        surveys = Survey.objects.all().order_by('name')
    else:
        subcollections = Subcollection.objects.filter(collection_id__in=collection_ids).order_by('name')
        surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids).order_by('name')

    surveys = list(surveys)
    subcollections = list(subcollections)
    subcollections.sort(key=lambda sc: alphanum_key(sc.name))
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {
        'subcollections': [{'id': sc.id, 'name': sc.name} for sc in subcollections],
        'surveys': [{'id': s.id, 'name': s.name} for s in surveys],
    }

    return JsonResponse(data)


def get_surveys_by_subcollections(request):
    subcollection_ids = request.GET.get('subcollections_ids', '').split(',')
    subcollection_ids = [id for id in subcollection_ids if id]

    if not subcollection_ids:
        collection_ids = request.GET.get('collections_ids', '').split(',')
        collection_ids = [id for id in collection_ids if id]

        if collection_ids:
            surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids).order_by('name')
        else:
            surveys = Survey.objects.all().order_by('name')
    else:
        surveys = Survey.objects.filter(subcollection_id__in=subcollection_ids).order_by('name')

    surveys = list(surveys)
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {'surveys': [{'id': s.id, 'name': s.name} for s in surveys]}
    return JsonResponse(data)

def get_decades(request):
    collection_ids = request.GET.get('collections_ids', '').split(',')
    subcollection_ids = request.GET.get('subcollections_ids', '').split(',')
    survey_ids = request.GET.get('survey_ids', '').split(',')

    collection_ids = [id for id in collection_ids if id]
    subcollection_ids = [id for id in subcollection_ids if id]
    survey_ids = [id for id in survey_ids if id]

    if survey_ids:
        surveys = Survey.objects.filter(id__in=survey_ids)
    elif subcollection_ids:
        surveys = Survey.objects.filter(subcollection_id__in=subcollection_ids)
    elif collection_ids:
        surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids)
    else:
        surveys = Survey.objects.all()

    years = surveys.values_list('start_date', flat=True).distinct()

    years = [year.year for year in years if year is not None]
    years = list(set(years))
    years.sort(reverse=True)

    decades = {}
    for year in years:
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append(year)
    return JsonResponse({'decades': decades})


def get_years_by_decade(request):
    try:
        decade = int(request.GET.get('decade', 0))
    except ValueError:
        return JsonResponse({'error': 'Invalid decade value'}, status=400)
    start_year = decade
    end_year = decade + 9
    collection_ids = request.GET.get('collections_ids', '').split(',')
    subcollection_ids = request.GET.get('subcollections_ids', '').split(',')
    survey_ids = request.GET.get('survey_ids', '').split(',')

    collection_ids = [id for id in collection_ids if id]
    subcollection_ids = [id for id in subcollection_ids if id]
    survey_ids = [id for id in survey_ids if id]

    if survey_ids:
        surveys = Survey.objects.filter(id__in=survey_ids)
    elif subcollection_ids:
        surveys = Survey.objects.filter(subcollection_id__in=subcollection_ids)
    elif collection_ids:
        surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids)
    else:
        surveys = Survey.objects.all()

    years = surveys.filter(start_date__year__range=(start_year, end_year)) \
        .values_list('start_date__year', flat=True) \
        .distinct()
    years = list(set(years))

    years.sort()

    return JsonResponse({'years': years})

def check_media_root(request):
    # Vérifier si le répertoire MEDIA_ROOT existe
    if not os.path.exists(settings.MEDIA_ROOT):
        return JsonResponse({"error": "MEDIA_ROOT directory does not exist."})

    # Parcourir les fichiers et dossiers dans MEDIA_ROOT
    media_files_info = []
    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
        for name in files:
            file_path = os.path.join(root, name)
            relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)

            # Tenter de construire l'URL de l'image et vérifier si l'URL est accessible
            file_url = os.path.join(settings.MEDIA_URL, relative_path).replace("\\", "/")
            file_exists = check_file_access(file_url)

            # Obtenir les informations sur le fichier
            file_info = {
                "name": name,
                "relative_path": relative_path,
                "size": os.path.getsize(file_path),  # Taille en octets
                "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                "url": file_url,
                "accessible": file_exists,
            }
            media_files_info.append(file_info)

    return JsonResponse({
        "MEDIA_ROOT": str(settings.MEDIA_ROOT),
        "MEDIA_URL": settings.MEDIA_URL,
        "file_count": len(media_files_info),
        "files": media_files_info,
    })