from __future__ import annotations

from django.db.models import Count
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from account.models import CorrectiveExercise, Exercise, Muscle
from api.decorators import api_endpoint, api_methods
from api.responses import ok
from api.utils import parse_int
from api.v1.library.selectors import (
    LOOKUP_LABELS,
    LOOKUP_MODELS,
    get_corrective_exercise_queryset,
    get_exercise_queryset,
    get_lookup_model,
    get_lookup_queryset,
    get_muscle_queryset,
)
from api.v1.library.serializers import (
    serialize_corrective_exercise,
    serialize_exercise,
    serialize_lookup,
    serialize_muscle,
)


def _pagination(request, queryset, serializer):
    raw_page_size = request.GET.get("page_size", request.GET.get("limit", "20"))
    page_size = parse_int(raw_page_size, field="page_size")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100.")
    page_number = parse_int(request.GET.get("page", "1"), field="page")
    if page_number < 1:
        raise ValueError("page must be greater than zero.")
    page = Paginator(queryset, page_size).get_page(page_number)
    return {
        "items": [serializer(item) for item in page.object_list],
        "pagination": {
            "page": page.number,
            "page_size": page_size,
            "pages": page.paginator.num_pages,
            "total": page.paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        },
    }


@api_endpoint
@api_methods("GET")
def catalog(request):
    resources = [
        {"key": "exercises", "path": "/api/v1/library/exercises/", "count": Exercise.objects.count(), "label": "حرکت‌ها"},
        {"key": "corrective-exercises", "path": "/api/v1/library/corrective-exercises/", "count": CorrectiveExercise.objects.count(), "label": "حرکت‌های اصلاحی"},
        {"key": "muscles", "path": "/api/v1/library/muscles/", "count": Muscle.objects.count(), "label": "عضله‌ها"},
    ]
    resources.extend(
        {
            "key": key,
            "path": f"/api/v1/library/{key}/",
            "count": model.objects.count(),
            "label": LOOKUP_LABELS[key],
        }
        for key, model in LOOKUP_MODELS.items()
    )
    return ok({"resources": resources})


@api_endpoint
@api_methods("GET")
def filters(request):
    return ok(
        {
            "muscles": [
                serialize_muscle(request, item)
                for item in get_muscle_queryset().annotate(exercise_count_value=Count("primary_exercises"))
            ],
            "lookups": {
                key: [serialize_lookup(item) for item in model.objects.all().order_by("pk")]
                for key, model in LOOKUP_MODELS.items()
            },
        }
    )


@api_endpoint
@api_methods("GET")
def exercise_list(request):
    return ok(
        _pagination(
            request,
            get_exercise_queryset(request.GET),
            lambda item: serialize_exercise(request, item),
        )
    )


@api_endpoint
@api_methods("GET")
def exercise_detail(request, pk):
    exercise = get_object_or_404(
        get_exercise_queryset({}),
        pk=pk,
    )
    return ok(serialize_exercise(request, exercise, detail=True))


@api_endpoint
@api_methods("GET")
def corrective_exercise_list(request):
    return ok(
        _pagination(
            request,
            get_corrective_exercise_queryset(request.GET),
            lambda item: serialize_corrective_exercise(request, item),
        )
    )


@api_endpoint
@api_methods("GET")
def corrective_exercise_detail(request, pk):
    exercise = get_object_or_404(
        CorrectiveExercise.objects.select_related("equipment", "abnormality_type"),
        pk=pk,
    )
    return ok(serialize_corrective_exercise(request, exercise, detail=True))


@api_endpoint
@api_methods("GET")
def muscle_list(request):
    queryset = get_muscle_queryset((request.GET.get("q") or "").strip())
    queryset = queryset.annotate(exercise_count_value=Count("primary_exercises"))
    return ok(
        _pagination(
            request,
            queryset,
            lambda item: serialize_muscle(request, item),
        )
    )


@api_endpoint
@api_methods("GET")
def muscle_detail(request, pk):
    muscle = get_object_or_404(Muscle.objects.all(), pk=pk)
    return ok(serialize_muscle(request, muscle, detail=True))


@api_endpoint
@api_methods("GET")
def lookup_list(request, lookup):
    queryset = get_lookup_queryset(lookup, (request.GET.get("q") or "").strip())
    return ok(
        _pagination(
            request,
            queryset,
            serialize_lookup,
        )
    )


@api_endpoint
@api_methods("GET")
def lookup_detail(request, lookup, pk):
    model = get_lookup_model(lookup)
    item = get_object_or_404(model, pk=pk)
    return ok(serialize_lookup(item))
