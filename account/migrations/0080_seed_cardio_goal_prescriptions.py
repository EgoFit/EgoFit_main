from django.db import migrations


CARDIO_PRESCRIPTIONS = {
    "ExerciseSetType": {"set_count": "1"},
    "ExerciseRepetitionType": {"reps": "20-30 دقیقه"},
    "ExerciseRestType": {"rest_time": "0-30 ثانیه"},
}


def seed_cardio_goal(apps, schema_editor):
    database = schema_editor.connection.alias
    ExerciseGoal = apps.get_model("account", "ExerciseGoal")
    ExerciseSetType = apps.get_model("account", "ExerciseSetType")
    ExerciseRepetitionType = apps.get_model("account", "ExerciseRepetitionType")
    ExerciseRestType = apps.get_model("account", "ExerciseRestType")

    goal = ExerciseGoal.objects.using(database).filter(name_en__iexact="cardio").first()
    if goal is None:
        goal = ExerciseGoal.objects.using(database).filter(name__iexact="هوازی").first()
    if goal is None:
        goal = ExerciseGoal.objects.using(database).create(name="هوازی", name_en="cardio")
    elif goal.name_en != "cardio":
        goal.name_en = "cardio"
        goal.save(using=database, update_fields=["name_en"])
    elif goal.name != "هوازی" and not ExerciseGoal.objects.using(database).exclude(pk=goal.pk).filter(name="هوازی").exists():
        goal.name = "هوازی"
        goal.save(using=database, update_fields=["name"])

    for model_name, values in CARDIO_PRESCRIPTIONS.items():
        model = {
            "ExerciseSetType": ExerciseSetType,
            "ExerciseRepetitionType": ExerciseRepetitionType,
            "ExerciseRestType": ExerciseRestType,
        }[model_name]
        model.objects.using(database).get_or_create(
            goal="cardio",
            method="normal",
            **values,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0079_cardioexercise_alter_workoutprogramexercise_exercise_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_cardio_goal, migrations.RunPython.noop),
    ]
