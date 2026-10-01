from django.db import migrations, models
import django.utils.translation


def split_abdominal_exercises(apps, schema_editor):
    Exercise = apps.get_model("account", "Exercise")
    ExerciseSecondaryMovementType = apps.get_model(
        "account", "ExerciseSecondaryMovementType"
    )
    abdomen, _ = ExerciseSecondaryMovementType.objects.get_or_create(
        name="شکم",
        defaults={"name_en": "Abs"},
    )
    lumbar, _ = ExerciseSecondaryMovementType.objects.get_or_create(
        name="کمر",
        defaults={"name_en": "Lumbar"},
    )
    abdominal_terms = ("شکم", "راست شکمی", "مایل", "عرضی شکمی")
    for exercise in Exercise.objects.select_related("primary_muscle"):
        muscle_name = (exercise.primary_muscle.name or "").replace("ي", "ی").replace("\u200c", "")
        if any(term in muscle_name for term in abdominal_terms):
            exercise.secondary_movement_type_id = abdomen.pk
            exercise.save(update_fields=["secondary_movement_type"])
        elif any(term in muscle_name for term in ("راستکننده", "فیله")):
            exercise.secondary_movement_type_id = lumbar.pk
            exercise.save(update_fields=["secondary_movement_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0075_workout_program_type_and_day_progress"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workoutprogram",
            name="program_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("normal", "Normal"),
                    ("full_body", "Full Body"),
                    ("push_pull", "Push/Pull"),
                    ("split", "Split"),
                    ("push_pull_legs", "Push/Pull/Leg"),
                ],
                default="normal",
                max_length=20,
                verbose_name=django.utils.translation.gettext_lazy("نوع برنامه"),
            ),
        ),
        migrations.AddField(
            model_name="exercisesettype",
            name="method",
            field=models.CharField(
                choices=[
                    ("normal", django.utils.translation.gettext_lazy("معمولی")),
                    ("pyramid", "Pyramid"),
                    ("reverse_pyramid", "Reverse Pyramid"),
                    ("21_reps", "21 Reps"),
                    ("drop_set", "Drop Set"),
                    ("low_to_high", "Low To High"),
                    ("high_to_low", "High To Low"),
                ],
                db_index=True,
                default="normal",
                max_length=20,
                verbose_name=django.utils.translation.gettext_lazy("روش تمرین"),
            ),
        ),
        migrations.AddField(
            model_name="exerciserepetitiontype",
            name="method",
            field=models.CharField(
                choices=[
                    ("normal", django.utils.translation.gettext_lazy("معمولی")),
                    ("pyramid", "Pyramid"),
                    ("reverse_pyramid", "Reverse Pyramid"),
                    ("21_reps", "21 Reps"),
                    ("drop_set", "Drop Set"),
                    ("low_to_high", "Low To High"),
                    ("high_to_low", "High To Low"),
                ],
                db_index=True,
                default="normal",
                max_length=20,
                verbose_name=django.utils.translation.gettext_lazy("روش تمرین"),
            ),
        ),
        migrations.AddField(
            model_name="exerciseresttype",
            name="method",
            field=models.CharField(
                choices=[
                    ("normal", django.utils.translation.gettext_lazy("معمولی")),
                    ("pyramid", "Pyramid"),
                    ("reverse_pyramid", "Reverse Pyramid"),
                    ("21_reps", "21 Reps"),
                    ("drop_set", "Drop Set"),
                    ("low_to_high", "Low To High"),
                    ("high_to_low", "High To Low"),
                ],
                db_index=True,
                default="normal",
                max_length=20,
                verbose_name=django.utils.translation.gettext_lazy("روش تمرین"),
            ),
        ),
        migrations.RunPython(split_abdominal_exercises, migrations.RunPython.noop),
    ]
