from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0074_coachrequest_training_experience_years_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutprogram",
            name="program_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("normal", "Normal"),
                    ("full_body", "Full Body"),
                    ("push_pull", "Push/Pull"),
                    ("split", "Spilt"),
                    ("push_pull_legs", "Push/Pull/Leg"),
                ],
                default="normal",
                max_length=20,
                verbose_name="نوع برنامه",
            ),
        ),
        migrations.CreateModel(
            name="WorkoutProgramDayProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completed_count", models.PositiveIntegerField(default=0, verbose_name="تعداد دفعات انجام‌شده")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین به‌روزرسانی")),
                (
                    "day",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress",
                        to="account.workoutprogramday",
                        verbose_name="جلسه برنامه",
                    ),
                ),
            ],
            options={
                "verbose_name": "پیشرفت جلسه برنامه",
                "verbose_name_plural": "پیشرفت جلسات برنامه",
            },
        ),
    ]
