from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0055_program_movement_prescriptions_and_day_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="video_1",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="exercises/videos/",
                verbose_name="ویدیوی ۱",
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="video_2",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="exercises/videos/",
                verbose_name="ویدیوی ۲",
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="video_3",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="exercises/videos/",
                verbose_name="ویدیوی ۳",
            ),
        ),
        migrations.AddField(
            model_name="correctiveexercise",
            name="video_1",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="corrective_exercises/videos/",
                verbose_name="ویدیوی ۱",
            ),
        ),
        migrations.AddField(
            model_name="correctiveexercise",
            name="video_2",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="corrective_exercises/videos/",
                verbose_name="ویدیوی ۲",
            ),
        ),
        migrations.AddField(
            model_name="correctiveexercise",
            name="video_3",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="corrective_exercises/videos/",
                verbose_name="ویدیوی ۳",
            ),
        ),
    ]
