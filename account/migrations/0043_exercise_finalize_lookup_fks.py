import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0042_exercise_remove_old_choice_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='exercise',
            old_name='body_part_fk',
            new_name='body_part',
        ),
        migrations.RenameField(
            model_name='exercise',
            old_name='movement_type_fk',
            new_name='movement_type',
        ),
        migrations.RenameField(
            model_name='exercise',
            old_name='joint_type_fk',
            new_name='joint_type',
        ),
        migrations.RenameField(
            model_name='exercise',
            old_name='power_type_fk',
            new_name='power_type',
        ),
        migrations.RenameField(
            model_name='exercise',
            old_name='difficulty_level_fk',
            new_name='difficulty_level',
        ),
        migrations.RenameField(
            model_name='exercise',
            old_name='equipment_type_fk',
            new_name='equipment_type',
        ),
        migrations.AlterField(
            model_name='exercise',
            name='body_part',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisebodypart', verbose_name='بخش بدن'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='movement_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisemovementtype', verbose_name='نوع حرکت'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='joint_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisejointtype', verbose_name='نوع مفصل'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='power_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisepowertype', verbose_name='نوع قدرت'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='difficulty_level',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisedifficultylevel', verbose_name='سطح دشواری'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='equipment_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exerciseequipmenttype', verbose_name='تجهیزات'),
        ),
    ]
