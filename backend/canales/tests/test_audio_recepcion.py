"""Recepción y deduplicación de audio."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from canales import recepcion
from canales.models import MensajeEntrante, TrabajoAudio
from canales.tests.soporte_audio import crear_sesion, payload_audio


@override_settings(STT_HABILITADO=True, WAHA_INSTANCIA="waha")
class RecepcionAudioTests(TestCase):
    def setUp(self):
        crear_sesion()

    def recibir(self, payload):
        return recepcion.recibir(
            {"event": "message", "session": "s", "payload": payload}
        )

    def test_sin_url_crea_fallo_atomico_sin_red(self):
        payload = payload_audio()
        payload["media"].pop("url")
        with patch("canales.media.descargar_acotado") as descarga:
            self.assertEqual(self.recibir(payload), "recibido")
        descarga.assert_not_called()
        trabajo = TrabajoAudio.objects.get()
        self.assertEqual((trabajo.estado, trabajo.motivo), ("fallido", "sin_media"))
        self.assertEqual(trabajo.mensaje_id, MensajeEntrante.objects.get().pk)

    def test_repetir_audio_no_duplica(self):
        self.assertEqual(self.recibir(payload_audio()), "recibido")
        self.assertEqual(self.recibir(payload_audio()), "duplicado")
        self.assertEqual(MensajeEntrante.objects.count(), 1)
        self.assertEqual(TrabajoAudio.objects.count(), 1)

    def test_fallo_creacion_trabajo_revierte_mensaje(self):
        with patch("canales.audio.crear_trabajo", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.recibir(payload_audio())
        self.assertFalse(MensajeEntrante.objects.exists())
        self.assertFalse(TrabajoAudio.objects.exists())

    @override_settings(STT_HABILITADO=False)
    def test_deshabilitado_no_crea_trabajo(self):
        self.recibir(payload_audio())
        self.assertFalse(TrabajoAudio.objects.exists())
        self.assertEqual(MensajeEntrante.objects.get().tipo, "audio")

    def test_sin_medios_no_se_guarda_si_falla_transaccion(self):
        payload = payload_audio()
        payload["media"].pop("url")
        with patch(
            "canales.audio.TrabajoAudio.objects.create", side_effect=RuntimeError
        ):
            with self.assertRaises(RuntimeError):
                self.recibir(payload)
        self.assertFalse(MensajeEntrante.objects.exists())
