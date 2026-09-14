from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0059_workoutprogram_payment_access"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="clientdocumentpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="initiated"),
                fields=("document", "user"),
                name="unique_active_document_payment",
            ),
        ),
        migrations.AddConstraint(
            model_name="workoutprogrampayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="initiated"),
                fields=("program", "user"),
                name="unique_active_workout_payment",
            ),
        ),
    ]
