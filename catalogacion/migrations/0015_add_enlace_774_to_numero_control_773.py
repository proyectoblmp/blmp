import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogacion', '0014_alter_mediointerpretacion382_solista_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='numerocontrol773',
            name='enlace_774',
            field=models.ForeignKey(
                blank=True,
                help_text='Slot 774 en la colección al que corresponde esta obra hija (referencia explícita)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='numeros_control_773',
                to='catalogacion.enlaceunidadconstituyente774',
            ),
        ),
    ]
