from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ambito", "0003_comercio_clabe"),
    ]

    operations = [
        migrations.AddField(
            model_name="comercio",
            name="pey_bank_account_id",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="id de cuenta en pey",
            ),
        ),
        migrations.AddField(
            model_name="comercio",
            name="pey_codi_status",
            field=models.CharField(
                choices=[("pending", "Pendiente"), ("active", "Activa")],
                default="pending",
                max_length=10,
                verbose_name="estado de cuenta CoDi en pey",
            ),
        ),
        migrations.AddField(
            model_name="comercio",
            name="pey_codi_status_actualizado_en",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="última sincronización de estado pey",
            ),
        ),
    ]
