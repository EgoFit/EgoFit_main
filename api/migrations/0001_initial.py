from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("token_type", models.CharField(choices=[("access", "Access"), ("refresh", "Refresh")], db_index=True, default="access", max_length=8)),
                ("family_id", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(blank=True, max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "revoked_at", "expires_at"], name="api_apitoke_user_id_9a44a5_idx"),
                    models.Index(fields=["family_id", "revoked_at"], name="api_apitoke_family__b5d394_idx"),
                ],
            },
        ),
    ]
