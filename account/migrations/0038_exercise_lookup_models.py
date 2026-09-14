from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0037_muscle_bodycircumferencemeasurement_arm_length_cm_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExerciseBodyPart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='بخش بدن')),
            ],
            options={
                'verbose_name': 'بخش بدن',
                'verbose_name_plural': 'بخش‌های بدن',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ExerciseMovementType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='نوع حرکت')),
            ],
            options={
                'verbose_name': 'نوع حرکت',
                'verbose_name_plural': 'انواع حرکت',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ExerciseJointType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='نوع مفصل')),
            ],
            options={
                'verbose_name': 'نوع مفصل',
                'verbose_name_plural': 'انواع مفصل',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ExercisePowerType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='نوع قدرت')),
            ],
            options={
                'verbose_name': 'نوع قدرت',
                'verbose_name_plural': 'انواع قدرت',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ExerciseDifficultyLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='سطح دشواری')),
            ],
            options={
                'verbose_name': 'سطح دشواری',
                'verbose_name_plural': 'سطوح دشواری',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ExerciseEquipmentType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='تجهیزات')),
            ],
            options={
                'verbose_name': 'نوع تجهیزات',
                'verbose_name_plural': 'انواع تجهیزات',
                'ordering': ['name'],
            },
        ),
    ]
