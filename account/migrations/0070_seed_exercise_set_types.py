from django.db import migrations


INITIAL_SET_TYPES = (
    ("۳", ""),
)


def seed_exercise_set_types(apps, schema_editor):
    ExerciseSetType = apps.get_model("account", "ExerciseSetType")
    for set_count, goal in INITIAL_SET_TYPES:
        ExerciseSetType.objects.get_or_create(set_count=set_count, goal=goal)


def remove_seeded_exercise_set_types(apps, schema_editor):
    ExerciseSetType = apps.get_model("account", "ExerciseSetType")
    for set_count, goal in INITIAL_SET_TYPES:
        ExerciseSetType.objects.filter(set_count=set_count, goal=goal).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0069_coachrequest_admin_read_at"),
    ]

    operations = [
        migrations.RunPython(seed_exercise_set_types, remove_seeded_exercise_set_types),
    ]
