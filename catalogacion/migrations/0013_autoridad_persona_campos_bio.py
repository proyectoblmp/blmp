from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogacion', '0012_default_solista_piano'),
    ]

    operations = [
        migrations.AddField(
            model_name='autoridadpersona',
            name='nota_biografica',
            field=models.TextField(blank=True, default='', help_text='Nota biográfica del compositor (MARC 545 $a)'),
        ),
        migrations.AddField(
            model_name='autoridadpersona',
            name='uri_nota_biografica',
            field=models.URLField(blank=True, default='', help_text='URL de referencia biográfica (MARC 545 $u)'),
        ),
    ]
