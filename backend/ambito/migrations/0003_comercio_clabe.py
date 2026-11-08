from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ambito", "0002_comercio_semilla_active_dev"),
    ]

    operations = [
        migrations.AddField(
            model_name="comercio",
            name="clabe",
            field=models.CharField(
                blank=True,
                default="",
                max_length=18,
                verbose_name="CLABE",
            ),
        ),
    ]
