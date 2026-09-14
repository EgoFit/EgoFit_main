from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0041_populate_exercise_lookup_fks'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='exercise',
            name='account_exe_body_pa_3f4848_idx',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='body_part',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='movement_type',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='joint_type',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='power_type',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='difficulty_level',
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='equipment_type',
        ),
    ]
