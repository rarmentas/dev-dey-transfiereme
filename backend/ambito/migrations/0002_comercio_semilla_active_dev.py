from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ambito", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="comercio",
            name="semilla_active_dev",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Marca de la semilla local de desarrollo. No autoriza cobros "
                    "ni cuenta como cuenta ACTIVE en pey."
                ),
            ),
        ),
    ]
