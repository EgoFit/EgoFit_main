from django.db import migrations, models
import django.db.models.deletion


def attach_existing_feedback_to_first_day(apps, schema_editor):
    WorkoutProgramFeedback = apps.get_model("account", "WorkoutProgramFeedback")
    WorkoutProgramDay = apps.get_model("account", "WorkoutProgramDay")

    for feedback in WorkoutProgramFeedback.objects.filter(day__isnull=True).iterator():
        first_day = (
            WorkoutProgramDay.objects.filter(program_id=feedback.program_id)
            .order_by("order", "id")
            .first()
        )
        if first_day:
            feedback.day_id = first_day.pk
            feedback.save(update_fields=["day"])


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0054_workoutprogramexercise_performance_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="superset_sets",
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                verbose_name="تعداد ست حرکت دوم",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="superset_reps",
            field=models.CharField(
                blank=True,
                max_length=60,
                null=True,
                verbose_name="تعداد تکرار حرکت دوم",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="superset_rest",
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                verbose_name="استراحت حرکت دوم",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="third_sets",
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                verbose_name="تعداد ست حرکت سوم",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="third_reps",
            field=models.CharField(
                blank=True,
                max_length=60,
                null=True,
                verbose_name="تعداد تکرار حرکت سوم",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="third_rest",
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                verbose_name="استراحت حرکت سوم",
            ),
        ),
        migrations.AlterField(
            model_name="workoutprogramfeedback",
            name="program",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="difficulty_feedback",
                to="account.workoutprogram",
                verbose_name="برنامه",
            ),
        ),
        migrations.AddField(
            model_name="workoutprogramfeedback",
            name="day",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="difficulty_feedback",
                to="account.workoutprogramday",
                verbose_name="روز برنامه",
            ),
        ),
        migrations.RunPython(
            attach_existing_feedback_to_first_day,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="workoutprogramfeedback",
            constraint=models.UniqueConstraint(
                fields=("program", "day"),
                name="unique_workout_program_feedback_day",
            ),
        ),
    ]
