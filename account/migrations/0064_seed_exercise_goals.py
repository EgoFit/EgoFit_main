from django.db import migrations


INITIAL_GOALS = (
    ("قدرت", "strength"),
    ("حجم", "volume"),
    ("چربی سوزی", "fat_burning"),
    ("استقامت", "endurance"),
    ("توان انفجاری", "power"),
    ("تناسب عمومی", "general"),
)


def seed_exercise_goals(apps, schema_editor):
    ExerciseGoal = apps.get_model("account", "ExerciseGoal")
    for name, name_en in INITIAL_GOALS:
        ExerciseGoal.objects.update_or_create(
            name_en=name_en,
            defaults={"name": name},
        )


def remove_seeded_exercise_goals(apps, schema_editor):
    ExerciseGoal = apps.get_model("account", "ExerciseGoal")
    ExerciseGoal.objects.filter(name_en__in=[name_en for _, name_en in INITIAL_GOALS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0063_exercisegoal"),
    ]

    operations = [
        migrations.RunPython(seed_exercise_goals, remove_seeded_exercise_goals),
    ]
