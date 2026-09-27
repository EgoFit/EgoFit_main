from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def copy_existing_weight_records(apps, schema_editor):
    old_record_model = apps.get_model("account", "WorkoutPerformanceRecord")
    best_record_model = apps.get_model("account", "WorkoutBestRecord")
    records = old_record_model.objects.filter(mode="weight").order_by(
        "user_id", "exercise_id", "-value", "-updated_at"
    )
    seen = set()
    for record in records:
        key = (record.user_id, record.exercise_id)
        if key in seen:
            continue
        best_record = best_record_model.objects.create(
            user_id=record.user_id,
            exercise_id=record.exercise_id,
            program_id=record.program_id,
            program_exercise_id=record.program_exercise_id,
            value=record.value,
        )
        best_record_model.objects.filter(pk=best_record.pk).update(recorded_at=record.updated_at)
        seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0067_remove_dailymoodentry_resting_heart_rate_score_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkoutBestRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "value",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=8,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="بهترین رکورد (کیلوگرم)",
                    ),
                ),
                (
                    "recorded_at",
                    models.DateTimeField(auto_now=True, verbose_name="تاریخ ثبت"),
                ),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="workout_best_records",
                        to="account.exercise",
                        verbose_name="حرکت",
                    ),
                ),
                (
                    "program",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="best_records",
                        to="account.workoutprogram",
                        verbose_name="برنامه",
                    ),
                ),
                (
                    "program_exercise",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="best_records",
                        to="account.workoutprogramexercise",
                        verbose_name="حرکت برنامه",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workout_best_records",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ورزشکار",
                    ),
                ),
            ],
            options={
                "verbose_name": "بهترین رکورد حرکت",
                "verbose_name_plural": "بهترین رکوردهای حرکات",
                "ordering": ["-recorded_at"],
                "indexes": [
                    models.Index(fields=["user", "exercise"], name="account_wor_user_id_4d1f6e_idx"),
                    models.Index(fields=["user", "recorded_at"], name="account_wor_user_id_9a1c3b_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "exercise"),
                        name="unique_workout_best_record",
                    ),
                    models.CheckConstraint(
                        check=models.Q(value__gt=0),
                        name="workout_best_record_value_positive",
                    ),
                ],
            },
        ),
        migrations.RunPython(copy_existing_weight_records, migrations.RunPython.noop),
    ]
