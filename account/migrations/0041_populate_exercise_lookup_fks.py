from django.db import migrations

# Maps the old TextChoices codes (still present in the CharFields at this point in
# migration history) to the Persian label used as the lookup row's `name`.
CODE_TO_LABEL = {
    "body_part_fk": {"upper": "بالاتنه", "lower": "پایین‌تنه"},
    "movement_type_fk": {
        "push": "هل دادن",
        "pull": "کشیدن",
        "leg": "پا",
        "core": "مرکزی بدن",
        "full_body": "تمام بدن",
    },
    "joint_type_fk": {"single": "تک‌مفصلی", "multi": "چندمفصلی"},
    "power_type_fk": {"power": "پاورلیفتینگ", "strength": "قدرتی"},
    "difficulty_level_fk": {
        "beginner": "مبتدی",
        "intermediate": "متوسط",
        "advanced": "پیشرفته",
    },
    "equipment_type_fk": {
        "bodyweight": "وزن بدن",
        "free_weight": "وزنه آزاد",
        "fixed_machine": "دستگاه ثابت",
        "cable": "کابل",
        "band": "کش",
        "other": "سایر",
    },
}

FK_FIELD_TO_MODEL = {
    "body_part_fk": "ExerciseBodyPart",
    "movement_type_fk": "ExerciseMovementType",
    "joint_type_fk": "ExerciseJointType",
    "power_type_fk": "ExercisePowerType",
    "difficulty_level_fk": "ExerciseDifficultyLevel",
    "equipment_type_fk": "ExerciseEquipmentType",
}

OLD_CHARFIELD_NAME = {
    "body_part_fk": "body_part",
    "movement_type_fk": "movement_type",
    "joint_type_fk": "joint_type",
    "power_type_fk": "power_type",
    "difficulty_level_fk": "difficulty_level",
    "equipment_type_fk": "equipment_type",
}


def populate_fk_fields(apps, schema_editor):
    Exercise = apps.get_model("account", "Exercise")

    pk_by_name = {}
    for fk_field, model_name in FK_FIELD_TO_MODEL.items():
        model = apps.get_model("account", model_name)
        pk_by_name[fk_field] = {row.name: row.pk for row in model.objects.all()}

    for exercise in Exercise.objects.all():
        update_fields = []
        for fk_field, code_map in CODE_TO_LABEL.items():
            old_field = OLD_CHARFIELD_NAME[fk_field]
            old_code = getattr(exercise, old_field)
            label = code_map.get(old_code)
            target_pk = pk_by_name[fk_field].get(label) if label else None
            setattr(exercise, f"{fk_field}_id", target_pk)
            update_fields.append(f"{fk_field}_id")
        exercise.save(update_fields=update_fields)


def clear_fk_fields(apps, schema_editor):
    Exercise = apps.get_model("account", "Exercise")
    fk_fields = list(CODE_TO_LABEL.keys())
    Exercise.objects.update(**{f"{field}_id": None for field in fk_fields})


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0040_exercise_add_lookup_fk_fields'),
    ]

    operations = [
        migrations.RunPython(populate_fk_fields, clear_fk_fields),
    ]
