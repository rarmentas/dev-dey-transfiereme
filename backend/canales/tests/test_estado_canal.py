from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from canales.models import LatidoCanal


class EstadoCanalTests(TestCase):
    def test_sin_latido_falla(self) -> None:
        with self.assertRaisesMessage(CommandError, "Latido ausente o vencido"):
            call_command("estado_canal", stdout=StringIO())

    def test_latido_reciente_anterior_al_reinicio_falla(self) -> None:
        inicio = timezone.now()
        LatidoCanal.objects.create(
            proceso="procesar_canal", ultimo_ciclo=inicio - timedelta(seconds=5)
        )
        with self.assertRaisesMessage(CommandError, "Latido anterior al reinicio"):
            call_command("estado_canal", desde=inicio.isoformat(), stdout=StringIO())

    def test_latido_posterior_al_reinicio_pasa(self) -> None:
        inicio = timezone.now() - timedelta(seconds=1)
        LatidoCanal.objects.create(
            proceso="procesar_canal", ultimo_ciclo=timezone.now()
        )
        call_command("estado_canal", desde=inicio.isoformat(), stdout=StringIO())

    def test_fecha_invalida_falla(self) -> None:
        for fecha in ("", "no-es-fecha", "2026-01-01T00:00:00"):
            with self.subTest(fecha=fecha):
                with self.assertRaisesMessage(CommandError, "Fecha de inicio inválida"):
                    call_command("estado_canal", desde=fecha, stdout=StringIO())

    def test_latido_igual_al_reinicio_falla(self) -> None:
        inicio = timezone.now()
        LatidoCanal.objects.create(proceso="procesar_canal", ultimo_ciclo=inicio)
        with self.assertRaisesMessage(CommandError, "Latido anterior al reinicio"):
            call_command("estado_canal", desde=inicio.isoformat(), stdout=StringIO())
