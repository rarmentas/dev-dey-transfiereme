import logging
import re

from django.db import migrations
from django.db.models import Count

from ambito.clabe import clabe_es_valida

logger = logging.getLogger(__name__)
ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def backfill(apps, schema_editor):
    Comercio = apps.get_model("ambito", "Comercio")
    Cuenta = apps.get_model("ambito", "CuentaCobro")
    duplicados = (
        Comercio.objects.exclude(pey_bank_account_id="")
        .values("pey_bank_account_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    conflictos = []
    for duplicado in duplicados:
        conflictos.extend(
            Comercio.objects.filter(
                pey_bank_account_id=duplicado["pey_bank_account_id"]
            ).values_list("id", flat=True)
        )
    if conflictos:
        raise RuntimeError(f"IDs pey duplicados en comercios {sorted(conflictos)}")
    for comercio in Comercio.objects.all().iterator():
        if not comercio.clabe:
            if comercio.pey_bank_account_id or comercio.pey_codi_status == "active":
                logger.warning("cuenta legado sin CLABE comercio_id=%s", comercio.pk)
            continue
        if Cuenta.objects.filter(
            comercio_id=comercio.pk, clabe=comercio.clabe
        ).exists():
            continue
        ident = comercio.pey_bank_account_id
        activo = comercio.pey_codi_status == "active"
        valido = bool(ULID.fullmatch(ident))
        clabe_valida = clabe_es_valida(comercio.clabe)
        apta = activo and valido and clabe_valida
        anomalia = ""
        if activo and not valido:
            anomalia = "ACTIVE_SIN_ID"
        elif activo and not clabe_valida:
            anomalia = "ACTIVE_SIN_CLABE_VALIDA"
        cuenta = Cuenta.objects.create(
            comercio_id=comercio.pk,
            clabe=comercio.clabe,
            pey_bank_account_id=ident,
            codi_status_crudo=comercio.pey_codi_status,
            sincronizada_en=comercio.pey_codi_status_actualizado_en,
            registro_estado="registrado" if ident else "sin_registro",
            codi_status="active" if apta else "pending",
            anomalia=anomalia,
        )
        if apta:
            comercio.cuenta_por_defecto_id = cuenta.pk
            comercio.save(update_fields=["cuenta_por_defecto"])


class Migration(migrations.Migration):
    dependencies = [("ambito", "0006_cuentas_expand")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
