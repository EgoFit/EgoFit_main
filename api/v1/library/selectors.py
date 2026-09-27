from __future__ import annotations

from collections import OrderedDict

from django.db.models import Q

from account.models import (
    CorrectiveExercise,
    Exercise,
    ExerciseAbnormalityType,
    ExerciseBodyPart,
    ExerciseDifficultyLevel,
    ExerciseEquipmentType,
    ExerciseExecutionEquipmentType,
    ExerciseGoal,
    ExerciseJointType,
    ExerciseMovementType,
    ExercisePowerType,
    ExercisePressureType,
    ExerciseRepetitionType,
    ExerciseRestType,
    ExerciseSecondaryMovementType,
    ExerciseSetType,
    ExerciseSportType,
    Muscle,
)


LOOKUP_MODELS = OrderedDict(
    (
        ("body-parts", ExerciseBodyPart),
        ("movement-types", ExerciseMovementType),
        ("joint-types", ExerciseJointType),
        ("power-types", ExercisePowerType),
        ("difficulty-levels", ExerciseDifficultyLevel),
        ("equipment-types", ExerciseEquipmentType),
        ("execution-equipment-types", ExerciseExecutionEquipmentType),
        ("secondary-movement-types", ExerciseSecondaryMovementType),
        ("abnormality-types", ExerciseAbnormalityType),
        ("pressure-types", ExercisePressureType),
        ("sport-types", ExerciseSportType),
        ("goals", ExerciseGoal),
        ("set-types", ExerciseSetType),
        ("repetition-types", ExerciseRepetitionType),
        ("rest-types", ExerciseRestType),
    )
)

LOOKUP_LABELS = {
    "body-parts": "بخش‌های بدن",
    "movement-types": "انواع حرکت",
    "joint-types": "انواع مفصل",
    "power-types": "انواع قدرت",
    "difficulty-levels": "سطوح دشواری",
    "equipment-types": "انواع تجهیزات",
    "execution-equipment-types": "انواع تجهیزات اجرایی",
    "secondary-movement-types": "انواع حرکت دوم",
    "abnormality-types": "انواع ناهنجاری",
    "pressure-types": "انواع فشار",
    "sport-types": "انواع ورزش",
    "goals": "اهداف برنامه",
    "set-types": "انواع ست",
    "repetition-types": "انواع تکرار",
    "rest-types": "انواع استراحت",
}

EXERCISE_RELATIONS = (
    "primary_muscle",
    "secondary_muscle",
    "body_part",
    "movement_type",
    "joint_type",
    "power_type",
    "difficulty_level",
    "equipment_type",
    "execution_equipment_type",
    "secondary_movement_type",
    "pressure_type",
)


def get_lookup_model(lookup: str):
    try:
        return LOOKUP_MODELS[lookup]
    except KeyError as exc:
        raise LookupError(lookup) from exc


def get_lookup_queryset(lookup: str, query: str = ""):
    model = get_lookup_model(lookup)
    queryset = model.objects.all().order_by("pk")
    if query:
        filters = Q()
        if hasattr(model, "name_en"):
            filters |= Q(name_en__icontains=query)
        if hasattr(model, "name"):
            filters |= Q(name__icontains=query)
        if hasattr(model, "goal"):
            filters |= Q(goal__icontains=query)
        if hasattr(model, "set_count"):
            filters |= Q(set_count__icontains=query)
        if hasattr(model, "reps"):
            filters |= Q(reps__icontains=query)
        if hasattr(model, "rest_time"):
            filters |= Q(rest_time__icontains=query)
        if filters.children:
            queryset = queryset.filter(filters)
    return queryset


def get_muscle_queryset(query: str = ""):
    queryset = Muscle.objects.all().order_by("pk")
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(name_en__icontains=query)
            | Q(function_note__icontains=query)
        )
    return queryset


def get_exercise_queryset(params):
    queryset = Exercise.objects.select_related(*EXERCISE_RELATIONS).order_by("pk")
    query = (params.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(name_en__icontains=query)
            | Q(description__icontains=query)
            | Q(primary_muscle__name__icontains=query)
            | Q(secondary_muscle__name__icontains=query)
            | Q(body_part__name__icontains=query)
            | Q(movement_type__name__icontains=query)
            | Q(equipment_type__name__icontains=query)
            | Q(secondary_movement_type__name__icontains=query)
        )

    relation_filters = {
        "body_part": "body_part_id",
        "primary_muscle": "primary_muscle_id",
        "secondary_muscle": "secondary_muscle_id",
        "movement_type": "movement_type_id",
        "joint_type": "joint_type_id",
        "power_type": "power_type_id",
        "difficulty_level": "difficulty_level_id",
        "equipment_type": "equipment_type_id",
        "execution_equipment_type": "execution_equipment_type_id",
        "secondary_movement_type": "secondary_movement_type_id",
        "pressure_type": "pressure_type_id",
    }
    for parameter, field in relation_filters.items():
        value = (params.get(parameter) or "").strip()
        if value:
            try:
                queryset = queryset.filter(**{field: int(value)})
            except ValueError as exc:
                raise ValueError(f"{parameter} must be an integer.") from exc
    return queryset


def get_corrective_exercise_queryset(params):
    queryset = CorrectiveExercise.objects.select_related(
        "equipment",
        "abnormality_type",
    ).order_by("pk")
    query = (params.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(equipment__name__icontains=query)
            | Q(abnormality_type__name__icontains=query)
        )
    for parameter, field in {
        "equipment": "equipment_id",
        "abnormality_type": "abnormality_type_id",
    }.items():
        value = (params.get(parameter) or "").strip()
        if value:
            try:
                queryset = queryset.filter(**{field: int(value)})
            except ValueError as exc:
                raise ValueError(f"{parameter} must be an integer.") from exc
    return queryset
