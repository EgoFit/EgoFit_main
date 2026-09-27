from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0070_seed_exercise_set_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDismissal",
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
                ("notification_key", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_dismissals",
                        to="account.user",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "notification_key"),
                        name="unique_user_notification_dismissal",
                    ),
                ],
                "indexes": [
                    models.Index(
                        fields=["user", "created_at"],
                        name="account_notif_user_created_idx",
                    ),
                ],
            },
        ),
    ]
