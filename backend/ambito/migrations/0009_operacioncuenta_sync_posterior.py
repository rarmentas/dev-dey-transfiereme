from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ambito", "0008_cuentas_cutover")]

    operations = [
        migrations.AddField(
            model_name="operacioncuenta",
            name="sync_posterior",
            field=models.BooleanField(default=False),
        ),
    ]
