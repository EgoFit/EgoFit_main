from django.db import migrations


# Baseline editable prescriptions ensure every built-in goal and method has a
# complete catalog entry. Coaches can add alternatives in the library.
GOAL_PRESCRIPTIONS = {
    "strength": {"sets": "3", "reps": "4-6", "rest": "180-300 ثانیه"},
    "volume": {"sets": "3", "reps": "8-12", "rest": "60-120 ثانیه"},
    "fat_burning": {"sets": "2", "reps": "10-15", "rest": "45-90 ثانیه"},
    "endurance": {"sets": "2", "reps": "12-20", "rest": "30-60 ثانیه"},
    "power": {"sets": "3", "reps": "3-5", "rest": "180-300 ثانیه"},
    "general": {"sets": "2", "reps": "8-12", "rest": "60-90 ثانیه"},
}

METHOD_REPETITIONS = {
    "normal": {"strength": "4-6", "volume": "8-12", "fat_burning": "10-15", "endurance": "12-20", "power": "3-5", "general": "8-12"},
    "pyramid": {"strength": "8-6-4", "volume": "12-10-8", "fat_burning": "15-12-10", "endurance": "20-15-12", "power": "5-3-2", "general": "12-10-8"},
    "reverse_pyramid": {"strength": "4-6-8", "volume": "8-10-12", "fat_burning": "10-12-15", "endurance": "12-15-20", "power": "2-3-5", "general": "8-10-12"},
    "21_reps": {goal: "7+7+7" for goal in GOAL_PRESCRIPTIONS},
    "drop_set": {goal: values["reps"] for goal, values in GOAL_PRESCRIPTIONS.items()},
    "low_to_high": {"strength": "4-6-8", "volume": "8-10-12", "fat_burning": "10-12-15", "endurance": "12-15-20", "power": "2-3-5", "general": "8-10-12"},
    "high_to_low": {"strength": "8-6-4", "volume": "12-10-8", "fat_burning": "15-12-10", "endurance": "20-15-12", "power": "5-3-2", "general": "12-10-8"},
}


def seed_prescription_catalogs(apps, schema_editor):
    ExerciseSetType = apps.get_model("account", "ExerciseSetType")
    ExerciseRepetitionType = apps.get_model("account", "ExerciseRepetitionType")
    ExerciseRestType = apps.get_model("account", "ExerciseRestType")
    database = schema_editor.connection.alias

    for goal, defaults in GOAL_PRESCRIPTIONS.items():
        for method, repetitions in METHOD_REPETITIONS.items():
            ExerciseSetType.objects.using(database).get_or_create(
                set_count=defaults["sets"], goal=goal, method=method
            )
            ExerciseRepetitionType.objects.using(database).get_or_create(
                reps=repetitions[goal], goal=goal, method=method
            )
            ExerciseRestType.objects.using(database).get_or_create(
                rest_time=defaults["rest"], goal=goal, method=method
            )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0076_program_methods_and_abdominal_category"),
    ]

    operations = [
        migrations.RunPython(seed_prescription_catalogs, migrations.RunPython.noop),
    ]
