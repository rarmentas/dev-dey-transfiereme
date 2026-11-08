from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("movimientos", "0004_cobro_qr_string"),
    ]

    operations = [
        migrations.AddField(
            model_name="cobro",
            name="pey_bank_account_id",
            field=models.CharField(
                blank=True,
                default="",
                max_length=26,
                verbose_name="id de cuenta en pey",
            ),
        ),
    ]
