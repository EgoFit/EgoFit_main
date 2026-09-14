# Generated manually for gender field on User model.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0035_admin_portal_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "مرد"), ("female", "زن")],
                max_length=10,
                null=True,
                verbose_name="جنسیت",
            ),
        ),
    ]
