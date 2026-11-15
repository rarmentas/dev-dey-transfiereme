"""Enlaza solo los destinos históricos identificados sin ambigüedad."""

from django.db import migrations


def enlazar_cuentas(apps, schema_editor):
    Cobro = apps.get_model("movimientos", "Cobro")
    Cuenta = apps.get_model("ambito", "CuentaCobro")
    alias = schema_editor.connection.alias
    for cobro in Cobro.objects.using(alias).exclude(pey_bank_account_id="").iterator():
        ids = list(
            Cuenta.objects.using(alias)
            .filter(
                comercio_id=cobro.comercio_id,
                pey_bank_account_id=cobro.pey_bank_account_id,
            )
            .values_list("pk", flat=True)[:2]
        )
        if len(ids) == 1:
            Cobro.objects.using(alias).filter(pk=cobro.pk).update(cuenta_id=ids[0])


class Migration(migrations.Migration):
    dependencies = [
        ("movimientos", "0006_cobro_cuenta"),
        ("ambito", "0007_cuentas_backfill"),
    ]
    operations = [migrations.RunPython(enlazar_cuentas, migrations.RunPython.noop)]
