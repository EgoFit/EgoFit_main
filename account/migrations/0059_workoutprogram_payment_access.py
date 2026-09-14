from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0058_clientdocument_access_price_consistent"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutprogram",
            name="price",
            field=models.PositiveIntegerField(default=0, verbose_name="هزینه (تومان)"),
        ),
        migrations.AddField(
            model_name="workoutprogram",
            name="requires_payment",
            field=models.BooleanField(default=False, verbose_name="نیازمند پرداخت"),
        ),
        migrations.AddConstraint(
            model_name="workoutprogram",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(requires_payment=False, price=0)
                    | models.Q(requires_payment=True, price__gt=0)
                ),
                name="workout_program_access_price_consistent",
            ),
        ),
        migrations.CreateModel(
            name="WorkoutProgramPayment",
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
                ("amount", models.PositiveIntegerField(verbose_name="مبلغ")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "در انتظار پرداخت"),
                            ("initiated", "پرداخت آغاز شده"),
                            ("paid", "پرداخت شده"),
                            ("failed", "ناموفق"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                        verbose_name="وضعیت",
                    ),
                ),
                ("authority", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("ref_id", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "program",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="account.workoutprogram",
                        verbose_name="برنامه",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workout_program_payments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "پرداخت برنامه بدنسازی",
                "verbose_name_plural": "پرداخت‌های برنامه بدنسازی",
            },
        ),
    ]
