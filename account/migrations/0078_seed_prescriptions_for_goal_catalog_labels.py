from django.db import migrations


GOAL_PRESETS = {
    "strength": {"sets": "3", "reps": "4-6", "rest": "180-300 ثانیه"},
    "volume": {"sets": "3", "reps": "8-12", "rest": "60-120 ثانیه"},
    "fat_burning": {"sets": "2", "reps": "10-15", "rest": "45-90 ثانیه"},
    "endurance": {"sets": "2", "reps": "12-20", "rest": "30-60 ثانیه"},
    "power": {"sets": "3", "reps": "3-5", "rest": "180-300 ثانیه"},
    "general": {"sets": "2", "reps": "8-12", "rest": "60-90 ثانیه"},
}

GOAL_ALIASES = {
    "strength": "strength",
    "volume": "volume",
    "hypertrophy": "volume",
    "muscle gain": "volume",
    "muscle_gain": "volume",
    "fat_burning": "fat_burning",
    "fat burning": "fat_burning",
    "fat-burning": "fat_burning",
    "fat burn": "fat_burning",
    "endurance": "endurance",
    "power": "power",
    "general": "general",
    # Some legacy catalogs contain this typo as the English goal key.
    "ggeneral": "general",
}

METHOD_REPETITIONS = {
    "normal": {
        "strength": "4-6",
        "volume": "8-12",
        "fat_burning": "10-15",
        "endurance": "12-20",
        "power": "3-5",
        "general": "8-12",
    },
    "pyramid": {
        "strength": "8-6-4",
        "volume": "12-10-8",
        "fat_burning": "15-12-10",
        "endurance": "20-15-12",
        "power": "5-3-2",
        "general": "12-10-8",
    },
    "reverse_pyramid": {
        "strength": "4-6-8",
        "volume": "8-10-12",
        "fat_burning": "10-12-15",
        "endurance": "12-15-20",
        "power": "2-3-5",
        "general": "8-10-12",
    },
    "21_reps": {goal: "7+7+7" for goal in GOAL_PRESETS},
    "drop_set": {goal: values["reps"] for goal, values in GOAL_PRESETS.items()},
    "low_to_high": {
        "strength": "4-6-8",
        "volume": "8-10-12",
        "fat_burning": "10-12-15",
        "endurance": "12-15-20",
        "power": "2-3-5",
        "general": "8-10-12",
    },
    "high_to_low": {
        "strength": "8-6-4",
        "volume": "12-10-8",
        "fat_burning": "15-12-10",
        "endurance": "20-15-12",
        "power": "5-3-2",
        "general": "12-10-8",
    },
}


def seed_goal_catalog_prescriptions(apps, schema_editor):
    ExerciseGoal = apps.get_model("account", "ExerciseGoal")
    ExerciseSetType = apps.get_model("account", "ExerciseSetType")
    ExerciseRepetitionType = apps.get_model("account", "ExerciseRepetitionType")
    ExerciseRestType = apps.get_model("account", "ExerciseRestType")
    database = schema_editor.connection.alias

    for goal in ExerciseGoal.objects.using(database).all().iterator():
        goal_key = (goal.name_en or "").strip()
        canonical_goal = GOAL_ALIASES.get(goal_key.casefold())
        if not canonical_goal:
            continue

        defaults = GOAL_PRESETS[canonical_goal]
        for method, repetitions_by_goal in METHOD_REPETITIONS.items():
            ExerciseSetType.objects.using(database).get_or_create(
                set_count=defaults["sets"], goal=goal_key, method=method
            )
            ExerciseRepetitionType.objects.using(database).get_or_create(
                reps=repetitions_by_goal[canonical_goal], goal=goal_key, method=method
            )
            ExerciseRestType.objects.using(database).get_or_create(
                rest_time=defaults["rest"], goal=goal_key, method=method
            )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0077_seed_automatic_program_prescriptions"),
    ]

    operations = [
        migrations.RunPython(seed_goal_catalog_prescriptions, migrations.RunPython.noop),
    ]
