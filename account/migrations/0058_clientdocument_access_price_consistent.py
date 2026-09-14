from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0057_clientdocument_price_clientdocument_requires_payment_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="clientdocument",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(requires_payment=False, price=0)
                    | models.Q(requires_payment=True, price__gt=0)
                ),
                name="client_document_access_price_consistent",
            ),
        ),
    ]
