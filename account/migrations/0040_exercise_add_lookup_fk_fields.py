import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0039_seed_exercise_lookup_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercise',
            name='body_part_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisebodypart', verbose_name='بخش بدن'),
        ),
        migrations.AddField(
            model_name='exercise',
            name='movement_type_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisemovementtype', verbose_name='نوع حرکت'),
        ),
        migrations.AddField(
            model_name='exercise',
            name='joint_type_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisejointtype', verbose_name='نوع مفصل'),
        ),
        migrations.AddField(
            model_name='exercise',
            name='power_type_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisepowertype', verbose_name='نوع قدرت'),
        ),
        migrations.AddField(
            model_name='exercise',
            name='difficulty_level_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exercisedifficultylevel', verbose_name='سطح دشواری'),
        ),
        migrations.AddField(
            model_name='exercise',
            name='equipment_type_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exercises', to='account.exerciseequipmenttype', verbose_name='تجهیزات'),
        ),
    ]
