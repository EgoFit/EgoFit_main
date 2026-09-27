from __future__ import annotations

from api.utils import absolute_file_url


def _lookup_reference(value):
    if value is None:
        return None
    payload = {"id": value.pk, "name": getattr(value, "name", str(value))}
    if hasattr(value, "name_en"):
        payload["name_en"] = value.name_en
    return payload


def serialize_lookup(value):
    payload = {"id": value.pk, "label": str(value)}
    if hasattr(value, "name"):
        payload["name"] = value.name
    if hasattr(value, "name_en"):
        payload["name_en"] = value.name_en
    if hasattr(value, "set_count"):
        payload.update({"set_count": value.set_count, "goal": value.goal})
    if hasattr(value, "reps"):
        payload.update({"reps": value.reps, "goal": value.goal})
    if hasattr(value, "rest_time"):
        payload.update({"rest_time": value.rest_time, "goal": value.goal})
    return payload


def serialize_muscle(request, muscle, *, detail=False):
    payload = {
        "id": muscle.pk,
        "name": muscle.name,
        "name_en": muscle.name_en,
        "image": absolute_file_url(request, muscle.image),
        "exercise_count": getattr(muscle, "exercise_count_value", None),
    }
    if detail:
        payload.update(
            {
                "origin": muscle.origin,
                "insertion": muscle.insertion,
                "nerve": muscle.nerve,
                "function_note": muscle.function_note,
            }
        )
    return payload


def serialize_exercise(request, exercise, *, detail=False):
    payload = {
        "id": exercise.pk,
        "name": exercise.name,
        "name_en": exercise.name_en,
        "description": exercise.description,
        "primary_muscle": _lookup_reference(exercise.primary_muscle),
        "secondary_muscle": _lookup_reference(exercise.secondary_muscle),
        "body_part": _lookup_reference(exercise.body_part),
        "movement_type": _lookup_reference(exercise.movement_type),
        "joint_type": _lookup_reference(exercise.joint_type),
        "power_type": _lookup_reference(exercise.power_type),
        "difficulty_level": _lookup_reference(exercise.difficulty_level),
        "equipment_type": _lookup_reference(exercise.equipment_type),
        "execution_equipment_type": _lookup_reference(exercise.execution_equipment_type),
        "secondary_movement_type": _lookup_reference(exercise.secondary_movement_type),
        "pressure_type": _lookup_reference(exercise.pressure_type),
    }
    if detail:
        payload["media"] = {
            "primary": absolute_file_url(request, exercise.media),
            "preview": absolute_file_url(request, exercise.media_preview),
            "videos": [absolute_file_url(request, item) for item in exercise.video_files],
        }
    return payload


def serialize_corrective_exercise(request, exercise, *, detail=False):
    payload = {
        "id": exercise.pk,
        "name": exercise.name,
        "description": exercise.description,
        "equipment": _lookup_reference(exercise.equipment),
        "abnormality_type": _lookup_reference(exercise.abnormality_type),
    }
    if detail:
        payload["media"] = {
            "primary": absolute_file_url(request, exercise.media),
            "preview": absolute_file_url(request, exercise.media_preview),
            "videos": [absolute_file_url(request, item) for item in exercise.video_files],
        }
    return payload
