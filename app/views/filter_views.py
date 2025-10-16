# -- DJANGO
from django.http import JsonResponse

from app.utils.sort import alphanum_key

# -- BASEDEQUESTIONS (LOCAL)
from ..models import (
    Subcollection,
    Survey,
)


def get_surveys_by_collections(request):
    collections_ids = request.GET.get("collections_ids")
    if collections_ids:
        collections_ids = [int(id) for id in collections_ids.split(",")]
        surveys = Survey.objects.filter(
            subcollection__collection__id__in=collections_ids
        ).order_by("name")
    else:
        surveys = Survey.objects.all().order_by("name")

    surveys_data = [{"id": survey.id, "name": survey.name} for survey in surveys]
    return JsonResponse({"surveys": surveys_data})


def get_subcollections_by_collections(request):
    collection_ids = request.GET.get("collections_ids", "").split(",")
    collection_ids = [id for id in collection_ids if id]

    if not collection_ids:
        subcollections = Subcollection.objects.all().order_by("name")
        surveys = Survey.objects.all().order_by("name")
    else:
        subcollections = Subcollection.objects.filter(
            collection_id__in=collection_ids
        ).order_by("name")
        surveys = Survey.objects.filter(
            subcollection__collection_id__in=collection_ids
        ).order_by("name")

    surveys = list(surveys)
    subcollections = list(subcollections)
    subcollections.sort(key=lambda sc: alphanum_key(sc.name))
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {
        "subcollections": [{"id": sc.id, "name": sc.name} for sc in subcollections],
        "surveys": [{"id": s.id, "name": s.name} for s in surveys],
    }

    return JsonResponse(data)


def get_surveys_by_subcollections(request):
    subcollection_ids = request.GET.get("subcollections_ids", "").split(",")
    subcollection_ids = [id for id in subcollection_ids if id]

    if not subcollection_ids:
        collection_ids = request.GET.get("collections_ids", "").split(",")
        collection_ids = [id for id in collection_ids if id]

        if collection_ids:
            surveys = Survey.objects.filter(
                subcollection__collection_id__in=collection_ids
            ).order_by("name")
        else:
            surveys = Survey.objects.all().order_by("name")
    else:
        surveys = Survey.objects.filter(
            subcollection_id__in=subcollection_ids
        ).order_by("name")

    surveys = list(surveys)
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {"surveys": [{"id": s.id, "name": s.name} for s in surveys]}
    return JsonResponse(data)


def get_decades(request):
    collection_ids = request.GET.get("collections_ids", "").split(",")
    subcollection_ids = request.GET.get("subcollections_ids", "").split(",")
    survey_ids = request.GET.get("survey_ids", "").split(",")

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

    years = surveys.values_list("start_date", flat=True).distinct()

    years = [year.year for year in years if year is not None]
    years = list(set(years))
    years.sort(reverse=True)

    decades = {}
    for year in years:
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append(year)
    return JsonResponse({"decades": decades})


def get_years_by_decade(request):
    try:
        decade = int(request.GET.get("decade", 0))
    except ValueError:
        return JsonResponse({"error": "Invalid decade value"}, status=400)
    start_year = decade
    end_year = decade + 9
    collection_ids = request.GET.get("collections_ids", "").split(",")
    subcollection_ids = request.GET.get("subcollections_ids", "").split(",")
    survey_ids = request.GET.get("survey_ids", "").split(",")

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

    years = (
        surveys.filter(start_date__year__range=(start_year, end_year))
        .values_list("start_date__year", flat=True)
        .distinct()
    )
    years = list(set(years))

    years.sort()

    return JsonResponse({"years": years})
