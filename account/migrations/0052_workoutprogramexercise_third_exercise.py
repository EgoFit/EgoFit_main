from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0051_workoutprogram_workoutprogramday_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutprogramexercise",
            name="third_exercise",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="third_program_items",
                to="account.exercise",
                verbose_name="حرکت سوم",
            ),
        ),
    ]
