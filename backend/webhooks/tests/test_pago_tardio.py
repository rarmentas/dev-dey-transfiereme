"""Un aviso firmado cobra la venta aunque ya se haya vencido al abrir la siguiente."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from webhooks.tests.support.pey_webhook import SECRETO, cuerpo_qr, post_firmado


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class PagoTardioVentaTests(TestCase):
    def test_aviso_de_la_venta_vencida_aparece_en_el_tablero_y_el_repetido_es_duplicado(
        self,
    ) -> None:
        comercio = Comercio.objects.create(nombre="Comercio A", semilla_active_dev=True)
        usuario = User.objects.create_user(username="vendedor_tarde", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=comercio)
        cliente = APIClient()
        cliente.force_login(usuario)
        puerto = AdaptadorDesarrollo()

        with patch("ventas.servicio.obtener_puerto", return_value=puerto):
            alta_a = cliente.post(
                "/api/ventas/",
                {"monto": "25.00", "concepto": "Tacos"},
                format="json",
            )
            self.assertEqual(alta_a.status_code, 201)
            cobro_a = Cobro.objects.get(pk=alta_a.json()["cobro_id"])
            cobro_a.vence_en = timezone.now() - timedelta(seconds=5)
            cobro_a.save(update_fields=["vence_en"])
            alta_b = cliente.post(
                "/api/ventas/",
                {"monto": "25.00", "concepto": "Refresco"},
                format="json",
            )

        self.assertEqual(alta_b.status_code, 201)
        movimiento_a = Movimiento.objects.get(pk=alta_a.json()["movimiento_id"])
        movimiento_b = Movimiento.objects.get(pk=alta_b.json()["movimiento_id"])
        self.assertEqual(movimiento_a.estado, Movimiento.Estado.VENCIDO)
        self.assertEqual(movimiento_b.estado, Movimiento.Estado.PENDIENTE)

        cuerpo = cuerpo_qr(
            transaction_id="TX-TARDE-A",
            codi_qr_id=cobro_a.pey_qr_id,
            amount=25,
        )
        with self.assertLogs("movimientos.correlacion", level="WARNING") as logs:
            aviso = post_firmado(cliente, cuerpo, "msg_tarde_a")
        self.assertEqual(aviso.status_code, 200)
        self.assertEqual(aviso.json(), {"estado": "aplicado"})
        texto = " ".join(logs.output)
        self.assertIn("pago tardío", texto)
        self.assertIn(f"movimiento_id={movimiento_a.pk}", texto)
        self.assertIn("transaction_id=TX-TARDE-A", texto)
        self.assertIn(f"comercio_id={comercio.pk}", texto)

        movimiento_a.refresh_from_db()
        movimiento_b.refresh_from_db()
        self.assertEqual(movimiento_a.estado, Movimiento.Estado.PAGADO)
        self.assertIsNotNone(movimiento_a.pagado_en)
        self.assertEqual(movimiento_a.pey_transaction_id, "TX-TARDE-A")
        self.assertEqual(movimiento_b.estado, Movimiento.Estado.PENDIENTE)

        tablero = cliente.get("/api/movimientos/tablero/")
        self.assertEqual(tablero.status_code, 200)
        filas = tablero.json()["desarrollo"]["filas"]
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["concepto"], "tacos")
        self.assertEqual(filas[0]["cantidad"], 1)

        repetido = post_firmado(cliente, cuerpo, "msg_tarde_a")
        self.assertEqual(repetido.status_code, 200)
        self.assertEqual(repetido.json(), {"estado": "duplicado"})
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).count(),
            1,
        )
        movimiento_b.refresh_from_db()
        self.assertEqual(movimiento_b.estado, Movimiento.Estado.PENDIENTE)
