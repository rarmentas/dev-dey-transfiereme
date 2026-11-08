"""Movimientos de desarrollo para ver el tablero sin pey."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from ambito.models import Comercio
from movimientos.models import Cobro, Movimiento
from movimientos.tablero import ZONA

CORREO_DEMO = "vendedor@demo.mx"
PREFIJO_DEMO = "demo-"

# canal, concepto visible, monto, estado, días atrás, hora, minuto.
# Los no pagados dejan días/hora en None. El modelo acepta el alta ya pagada
# con pagado_en explícito; cambiar_estado() siempre estampa timezone.now().
_PLAN = (
    ("qr_general", "Transferencia", "10.00", "pagado", 0, 9, 0),
    ("qr_general", "Transferencia", "4.50", "pagado", 1, 11, 30),
    ("qr_general", "Refrescos", "3.00", "pagado", 2, 8, 30),
    ("qr_venta", "Tortas", "15.50", "pagado", 0, 14, 0),
    ("qr_venta", "tortas ", "5.00", "pagado", 0, 18, 20),
    ("qr_venta", "Refrescos", "12.00", "pagado", 1, 16, 0),
    ("qr_venta", "Transferencia", "2.00", "pagado", 2, 19, 0),
    ("notificacion", "Tortas", "8.00", "pagado", 0, 12, 15),
    ("notificacion", "Refrescos", "6.50", "pagado", 1, 20, 10),
    ("notificacion", "Transferencia", "1.25", "pagado", 2, 10, 45),
    ("qr_venta", "Tortas", "30.00", "pendiente", None, None, 0),
    ("notificacion", "Refrescos", "7.00", "vencido", None, None, 0),
)


class Command(BaseCommand):
    help = "Crea movimientos origen_desarrollo para ver el tablero sin pey."

    def add_arguments(self, parser):
        parser.add_argument("--correo", default=CORREO_DEMO)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra solo los cobros y movimientos demo- de ese comercio.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Este comando solo corre con DEBUG activo.")

        correo = options["correo"].strip().lower()
        if not correo:
            raise CommandError("Indique el correo del vendedor.")
        comercio = _comercio_del_vendedor(correo)

        with transaction.atomic():
            if _hay_demo(comercio):
                if not options["reset"]:
                    self.stdout.write(
                        f"Ya hay movimientos demo en «{comercio.nombre}». "
                        "Use --reset para recrearlos."
                    )
                    return
                _borrar_demo(comercio)
            creados = _crear_demo(comercio)

        self.stdout.write(
            f"Listos {creados} movimientos demo en «{comercio.nombre}»."
        )


def _comercio_del_vendedor(correo: str) -> Comercio:
    try:
        usuario = User.objects.get(username=correo)
    except User.DoesNotExist:
        raise CommandError(
            f"No existe el vendedor {correo}. Corra sembrar_vendedor antes."
        ) from None
    membresia = getattr(usuario, "membresia", None)
    if membresia is None:
        raise CommandError(f"{correo} no tiene comercio asignado.")
    return membresia.comercio


def _q_demo() -> Q:
    return Q(pey_qr_id__startswith=PREFIJO_DEMO) | Q(
        pey_transaction_id__startswith=PREFIJO_DEMO
    )


def _hay_demo(comercio: Comercio) -> bool:
    cobros = Cobro.objects.filter(comercio=comercio).filter(_q_demo())
    movimientos = Movimiento.objects.filter(comercio=comercio).filter(
        Q(pey_transaction_id__startswith=PREFIJO_DEMO) | Q(cobro__in=cobros)
    )
    return cobros.exists() or movimientos.exists()


def _borrar_demo(comercio: Comercio) -> None:
    cobros = Cobro.objects.filter(comercio=comercio).filter(_q_demo())
    Movimiento.objects.filter(comercio=comercio).filter(
        Q(pey_transaction_id__startswith=PREFIJO_DEMO) | Q(cobro__in=cobros)
    ).delete()
    cobros.delete()


def _crear_demo(comercio: Comercio) -> int:
    cobro_general = (
        Cobro.objects.filter(
            comercio=comercio,
            canal=Movimiento.Canal.QR_GENERAL,
        ).first()
        or Cobro.objects.create(
            comercio=comercio,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0"),
            concepto="QR general",
            pey_qr_id="demo-qr-general",
            qr_string="demo-qr-general",
        )
    )
    for indice, spec in enumerate(_PLAN, start=1):
        canal, concepto, monto, estado, dias, hora, minuto = spec
        cobro = _cobro_para(comercio, cobro_general, canal, concepto, monto, indice)
        datos = {
            "comercio": comercio,
            "cobro": cobro,
            "monto": Decimal(monto),
            "concepto": concepto,
            "concepto_visible": concepto,
            "canal": canal,
            "estado": estado,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
            "pey_transaction_id": f"demo-pago-{indice:02d}",
        }
        if estado == Movimiento.Estado.PAGADO:
            datos["pagado_en"] = _momento_local(dias, hora, minuto)
        Movimiento.objects.create(**datos)
    return len(_PLAN)


def _cobro_para(
    comercio: Comercio,
    cobro_general: Cobro,
    canal: str,
    concepto: str,
    monto: str,
    indice: int,
) -> Cobro:
    if canal == Movimiento.Canal.QR_GENERAL:
        return cobro_general
    if canal == Movimiento.Canal.QR_VENTA:
        return Cobro.objects.create(
            comercio=comercio,
            canal=canal,
            monto=Decimal(monto),
            concepto=concepto,
            pey_qr_id=f"demo-qr-venta-{indice:02d}",
            qr_string=f"demo-qr-venta-{indice:02d}",
        )
    return Cobro.objects.create(
        comercio=comercio,
        canal=canal,
        monto=Decimal(monto),
        concepto=concepto,
        pey_transaction_id=f"demo-pn-{indice:02d}",
    )


def _momento_local(dias_atras: int, hora: int, minuto: int) -> datetime:
    dia = datetime.now(ZONA).date() - timedelta(days=dias_atras)
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZONA)
