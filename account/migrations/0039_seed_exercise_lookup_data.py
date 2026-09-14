from django.db import migrations

# Label sets mirror the TextChoices values that used to live on Exercise
# (account/migrations/0037_..._and_more.py) before being converted to lookup tables.
LOOKUP_SEED_DATA = {
    "ExerciseBodyPart": ["بالاتنه", "پایین‌تنه"],
    "ExerciseMovementType": ["هل دادن", "کشیدن", "پا", "مرکزی بدن", "تمام بدن"],
    "ExerciseJointType": ["تک‌مفصلی", "چندمفصلی"],
    "ExercisePowerType": ["پاورلیفتینگ", "قدرتی"],
    "ExerciseDifficultyLevel": ["مبتدی", "متوسط", "پیشرفته"],
    "ExerciseEquipmentType": ["وزن بدن", "وزنه آزاد", "دستگاه ثابت", "کابل", "کش", "سایر"],
}


def seed_lookup_tables(apps, schema_editor):
    for model_name, names in LOOKUP_SEED_DATA.items():
        model = apps.get_model("account", model_name)
        for name in names:
            model.objects.get_or_create(name=name)


def remove_lookup_tables(apps, schema_editor):
    for model_name, names in LOOKUP_SEED_DATA.items():
        model = apps.get_model("account", model_name)
        model.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0038_exercise_lookup_models'),
    ]

    operations = [
        migrations.RunPython(seed_lookup_tables, remove_lookup_tables),
    ]
