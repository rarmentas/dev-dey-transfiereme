from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ambito", "0007_cuentas_backfill")]
    operations = [
        migrations.AddConstraint(
            model_name="cuentacobro",
            constraint=models.UniqueConstraint(
                fields=["pey_bank_account_id"],
                condition=~models.Q(pey_bank_account_id=""),
                name="cuenta_id_pey_unico",
            ),
        ),
    ]
