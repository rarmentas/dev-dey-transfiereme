"""PENDING con id de pey no borra el registro. En desarrollo, sin id, sí se limpia."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.models import Comercio
from pey.cuentas import CuentaPey


class CuentaSyncIdTests(TestCase):
    @override_settings(DEBUG=False, PEY_ADAPTADOR="produccion", PEY_API_KEY="llave")
    def test_pending_de_produccion_conserva_el_id(self) -> None:
        comercio = Comercio.objects.create(
            nombre="En proceso",
            pey_bank_account_id="01KEEP",
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id="01KEEP", codi_status="PROCESSING"),
        ):
            sincronizar_codi_status(comercio)
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.pey_bank_account_id, "01KEEP")

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_desarrollo_sin_id_en_el_resultado_sigue_limpiando(self) -> None:
        comercio = Comercio.objects.create(
            nombre="Local",
            semilla_active_dev=False,
            pey_bank_account_id="01VIEJO",
        )
        sincronizar_codi_status(comercio)
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.pey_bank_account_id, "")
