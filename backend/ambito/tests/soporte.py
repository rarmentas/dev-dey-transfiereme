"""Datos de prueba para cuentas."""

import uuid

from ambito.models import Comercio, CuentaCobro


def clabe_valida(n: int) -> str:
    cuerpo = f"{n:017d}"
    total = sum(int(d) * (3, 7, 1)[i % 3] for i, d in enumerate(cuerpo))
    return cuerpo + str((10 - total % 10) % 10)


def crear_cuenta(comercio, estado="active", predeterminada=True):
    cuenta = CuentaCobro.objects.create(
        comercio=comercio,
        clabe=clabe_valida(comercio.cuentas.count() + 1),
        pey_bank_account_id=("01DEVS1M" + uuid.uuid4().hex.upper())[:26],
        registro_estado="registrado",
        codi_status=estado,
    )
    if predeterminada:
        comercio.cuenta_por_defecto = cuenta
        comercio.save(update_fields=["cuenta_por_defecto"])
    return cuenta


def crear_comercio_con_cuenta_activa():
    comercio = Comercio.objects.create(nombre="Comercio de prueba")
    crear_cuenta(comercio)
    return comercio
