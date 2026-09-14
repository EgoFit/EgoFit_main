from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0048_coachrequest_abdomen_cm_coachrequest_arm_flexed_cm_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bodycircumferencemeasurement",
            name="height_cm",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=5,
                null=True,
                verbose_name="قد (سانتی‌متر)",
            ),
        ),
        migrations.AlterField(
            model_name="bodycircumferencemeasurement",
            name="weight_kg",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=6,
                null=True,
                verbose_name="وزن (کیلوگرم)",
            ),
        ),
        migrations.AlterField(
            model_name="coachrequest",
            name="height_cm",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=5,
                null=True,
                verbose_name="قد (سانتی‌متر)",
            ),
        ),
        migrations.AlterField(
            model_name="coachrequest",
            name="weight_kg",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=6,
                null=True,
                verbose_name="وزن (کیلوگرم)",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="height_cm",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=5,
                null=True,
                verbose_name="قد (سانتی‌متر)",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="weight_kg",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=6,
                null=True,
                verbose_name="وزن (کیلوگرم)",
            ),
        ),
    ]
