"""Pruebas de audio del canal."""

from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from ambito.models import Comercio
from canales import audio, recepcion, worker
from canales.conversacion import procesar_mensaje
from canales.models import MensajeEntrante, SalidaCanal, SesionCanal, TrabajoAudio


@override_settings(STT_HABILITADO=True, WAHA_INSTANCIA="waha")
class ColaAudioTests(TestCase):
    def setUp(self):
        comercio = Comercio.objects.create(nombre="Tienda")
        SesionCanal.objects.create(
            instancia_id="waha", sesion_id="s", comercio=comercio
        )
        self.payload = {
            "id": "1",
            "from": "a@c.us",
            "fromMe": False,
            "hasMedia": True,
            "media": {"mimetype": "audio/ogg", "url": "http://waha/api/files/a"},
        }

    def recibir(self, payload):
        return recepcion.recibir(
            {"event": "message", "session": "s", "payload": payload}
        )

    def test_recepcion_idempotente_y_sin_media(self):
        self.assertEqual(self.recibir(self.payload), "recibido")
        self.assertEqual(self.recibir(self.payload), "duplicado")
        self.assertEqual(TrabajoAudio.objects.count(), 1)
        self.recibir({**self.payload, "id": "2", "media": {"mimetype": "audio/ogg"}})
        self.assertEqual(
            TrabajoAudio.objects.get(mensaje__secuencia=2).motivo, "sin_media"
        )

    def test_espera_expira_y_descarta_resultado_tardio(self):
        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        self.recibir({"id": "2", "from": "a@c.us", "fromMe": False, "body": "pan"})
        self.assertIsNone(worker.reclamar())
        TrabajoAudio.objects.filter(pk=trabajo.pk).update(
            vence_en=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(audio.expirar_trabajos(), 1)
        self.assertFalse(audio.completar(trabajo, texto="texto viejo"))
        self.assertEqual(MensajeEntrante.objects.get(secuencia=1).texto, "")
        self.assertEqual(worker.reclamar()[2], trabajo.mensaje_id)

    def test_aceptar_voz_y_fallo_no_llaman_nucleo(self):
        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        self.assertTrue(audio.completar(trabajo, texto="ACEPTAR P1-R1"))
        mensaje = MensajeEntrante.objects.select_related("conversacion__sesion").get()
        from uuid import uuid4

        conversacion = mensaje.conversacion
        conversacion.pedido_id_actual = uuid4()
        conversacion.save(update_fields=["pedido_id_actual"])
        SalidaCanal.objects.create(
            conversacion=conversacion, causa="resumen",
            destinatario=conversacion.cliente_externo_id, tipo="cotizacion_resumen",
            estado="enviada", id_proveedor="ack", envio_iniciado_en=timezone.now(),
            payload={
                "token_resumen": "P1-R1", "pedido_version": 1,
                "cotizacion_id": "cot", "cotizacion_revision": 1,
                "importe_efectivo_centavos": 100, "politica_cobro_version": "v1",
            },
        )
        nucleo = Mock(ES_SIMULACION=False)
        procesar_mensaje(mensaje, nucleo, None, timezone.now())
        nucleo.aceptar_cotizacion.assert_not_called()
        nucleo.solicitar_cobro.assert_not_called()
        self.assertIn(
            "texto", SalidaCanal.objects.get(tipo="respuesta").payload["texto"]
        )

    def test_procesar_audio_con_dobles_y_vacio(self):
        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        conversion = Mock()
        conversion.validar_wav.return_value = [0.1]
        transcriptor = Mock()
        transcriptor.transcribir.return_value = "2 panes"
        self.assertTrue(audio.procesar(trabajo, transcriptor, Mock(), conversion))
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, "listo")
        self.assertEqual(trabajo.mensaje.texto, "2 panes")
        self.recibir({**self.payload, "id": "2"})
        trabajo = audio.reclamar_trabajo()
        transcriptor.transcribir.return_value = "   "
        self.assertTrue(audio.procesar(trabajo, transcriptor, Mock(), conversion))
        trabajo.refresh_from_db()
        self.assertEqual((trabajo.estado, trabajo.motivo), ("fallido", "stt_vacio"))

    def test_largo_y_timeout_no_transcriben(self):
        self.recibir({**self.payload, "_data": {"seconds": 91}})
        trabajo = audio.reclamar_trabajo()
        transcriptor = Mock()
        self.assertTrue(audio.procesar(trabajo, transcriptor, Mock(), Mock()))
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.motivo, "demasiado_largo")
        transcriptor.transcribir.assert_not_called()
        self.recibir({**self.payload, "id": "2"})
        trabajo = audio.reclamar_trabajo()
        transcriptor.transcribir.side_effect = audio.SttTimeout()
        self.assertTrue(audio.procesar(trabajo, transcriptor, Mock(), Mock()))
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.motivo, "stt_timeout")

    @override_settings(NUCLEO_ADAPTADOR="real")
    def test_voz_real_crea_y_corrige_pedido(self):
        from unittest.mock import patch

        from pedidos.models import Pedido

        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        audio.completar(trabajo, texto="2 piezas de pan")
        transporte = Mock()
        transporte.enviar_texto.return_value = "ack"
        with patch("canales.worker.import_string", return_value=lambda: transporte):
            worker.ciclo()
            pedido = Pedido.objects.get()
            self.assertEqual(pedido.renglones.get().texto_solicitado, "pan")
            self.recibir({**self.payload, "id": "2"})
            trabajo = audio.reclamar_trabajo()
            audio.completar(trabajo, texto="CORREGIR: 3 piezas de leche")
            worker.ciclo()
        pedido.refresh_from_db()
        self.assertEqual(pedido.renglones.get().texto_solicitado, "leche")

    @override_settings(STT_HABILITADO=False)
    def test_deshabilitado_ofrece_texto_sin_trabajo(self):
        self.recibir(self.payload)
        self.assertFalse(TrabajoAudio.objects.exists())
        mensaje = MensajeEntrante.objects.select_related("conversacion__sesion").get()
        procesar_mensaje(mensaje, Mock(ES_SIMULACION=False), None, timezone.now())
        self.assertIn("texto", SalidaCanal.objects.get().payload["texto"])

    def test_fallo_audio_conserva_pedido_y_no_cobra(self):
        from pedidos.models import Pedido

        self.recibir({"id": "texto", "from": "a@c.us", "fromMe": False, "body": "pan"})
        from unittest.mock import patch

        transporte = Mock()
        transporte.enviar_texto.return_value = "ack"
        with patch("canales.worker.import_string", return_value=lambda: transporte):
            worker.ciclo()
            pedido = Pedido.objects.get()
            version = pedido.version
            self.recibir({**self.payload, "id": "audio"})
            trabajo = audio.reclamar_trabajo()
            audio.completar(trabajo, motivo="formato")
            worker.ciclo()
        pedido.refresh_from_db()
        self.assertEqual(pedido.version, version)
        self.assertEqual(pedido.renglones.get().texto_solicitado, "pan")
        self.assertIn("texto", SalidaCanal.objects.latest("creado_en").payload["texto"])

    def test_directorio_privado_y_eliminado(self):
        import os

        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        rutas = []

        def descarga(url, destino, timeout):
            rutas.append(destino.parent)
            self.assertEqual(os.stat(destino.parent).st_mode & 0o777, 0o700)

        audio.procesar(trabajo, Mock(), descarga, Mock())
        self.assertEqual(len(rutas), 1)
        self.assertFalse(rutas[0].exists())

    def test_lease_vencido_al_reiniciar_no_reprocesa(self):
        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        TrabajoAudio.objects.filter(pk=trabajo.pk).update(
            lease_hasta=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(audio.expirar_trabajos(), 1)
        trabajo.refresh_from_db()
        self.assertEqual((trabajo.estado, trabajo.motivo), ("fallido", "stt_timeout"))
        self.assertIsNone(audio.reclamar_trabajo())

    def test_token_de_lease_distinto_descarta_sin_escribir(self):
        import uuid

        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        nuevo_token = uuid.uuid4()
        TrabajoAudio.objects.filter(pk=trabajo.pk).update(lease_token=nuevo_token)
        self.assertFalse(audio.completar(trabajo, texto="resultado tardío"))
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.lease_token, nuevo_token)
        self.assertEqual((trabajo.estado, trabajo.transcripcion), ("procesando", ""))
        self.assertEqual(trabajo.mensaje.texto, "")

    @override_settings(NUCLEO_ADAPTADOR="real")
    def test_audio_lento_seguido_de_texto_procesa_sin_pisar_version(self):
        from unittest.mock import patch

        from pedidos.models import Pedido

        transporte = Mock()
        transporte.enviar_texto.return_value = "ack"
        with patch("canales.worker.import_string", return_value=lambda: transporte):
            self.recibir({"id": "p", "from": "a@c.us", "fromMe": False, "body": "pan"})
            worker.ciclo()
            pedido = Pedido.objects.get()
            self.recibir({**self.payload, "id": "audio"})
            trabajo = audio.reclamar_trabajo()
            self.recibir(
                {
                    "id": "texto",
                    "from": "a@c.us",
                    "fromMe": False,
                    "body": "CORREGIR: leche",
                }
            )
            worker.ciclo()
            pedido.refresh_from_db()
            version = pedido.version
            self.assertEqual(pedido.renglones.get().texto_solicitado, "pan")
            TrabajoAudio.objects.filter(pk=trabajo.pk).update(
                vence_en=timezone.now() - timedelta(seconds=1)
            )
            worker.ciclo()
            pedido.refresh_from_db()
            self.assertGreater(pedido.version, version)
            self.assertEqual(pedido.renglones.get().texto_solicitado, "leche")
            nueva_version = pedido.version
            self.assertFalse(audio.completar(trabajo, texto="CORREGIR: arroz"))
            worker.ciclo()
            pedido.refresh_from_db()
            self.assertEqual(pedido.version, nueva_version)
            self.assertEqual(pedido.renglones.get().texto_solicitado, "leche")

    def test_temporal_se_elimina_si_descarga_falla(self):
        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        rutas = []

        def descarga(_url, destino, _timeout):
            rutas.append(destino.parent)
            raise OSError("fallo")

        audio.procesar(trabajo, Mock(), descarga, Mock())
        self.assertEqual(len(rutas), 1)
        self.assertFalse(rutas[0].exists())
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, "fallido")

    def test_presupuesto_por_etapa_y_transcriptor_inyectado(self):
        from canales.tests.soporte_audio import TranscriptorFalso

        self.recibir(self.payload)
        trabajo = audio.reclamar_trabajo()
        tiempos = []
        conversion = Mock()
        conversion.inspeccionar.side_effect = lambda ruta, timeout: tiempos.append(
            timeout
        )
        conversion.a_wav_16k.side_effect = lambda src, dst, timeout: tiempos.append(
            timeout
        )
        conversion.validar_wav.return_value = [0.1]

        def descarga(url, destino, timeout):
            tiempos.append(timeout)

        self.assertTrue(
            audio.procesar(trabajo, TranscriptorFalso(), descarga, conversion)
        )
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.transcripcion, "2 panes")
        self.assertEqual(len(tiempos), 3)
        for valor, maximo in zip(tiempos, (15, 10, 10), strict=True):
            self.assertGreater(valor, 0)
            self.assertLessEqual(valor, maximo)
        self.assertLessEqual(trabajo.lease_hasta or trabajo.vence_en, trabajo.vence_en)


class ConcurrenciaAudioTests(TransactionTestCase):
    @override_settings(STT_HABILITADO=True, WAHA_INSTANCIA="waha")
    def test_dos_workers_un_solo_ganador(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from django.db import close_old_connections, connections

        from canales.tests.soporte_audio import crear_sesion, payload_audio

        crear_sesion()
        recepcion.recibir(
            {"event": "message", "session": "s", "payload": payload_audio()}
        )
        barrera = threading.Barrier(2)

        def reclamar():
            close_old_connections()
            try:
                barrera.wait(timeout=5)
                trabajo = audio.reclamar_trabajo()
                return trabajo.pk if trabajo else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: reclamar(), range(2)))
        self.assertEqual(sum(resultado is not None for resultado in resultados), 1)
        self.assertEqual(TrabajoAudio.objects.get().intentos, 1)

    @override_settings(STT_HABILITADO=True, WAHA_INSTANCIA="waha")
    def test_skip_locked_no_espera_candado_de_otro_worker(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from django.db import close_old_connections, connections, transaction

        from canales.tests.soporte_audio import crear_sesion, payload_audio

        crear_sesion()
        recepcion.recibir(
            {"event": "message", "session": "s", "payload": payload_audio()}
        )
        bloqueado = threading.Event()
        liberar = threading.Event()

        def retener():
            close_old_connections()
            try:
                with transaction.atomic():
                    TrabajoAudio.objects.select_for_update().get()
                    bloqueado.set()
                    liberar.wait(5)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            futuro = ejecutor.submit(retener)
            try:
                self.assertTrue(bloqueado.wait(5))
                inicio = timezone.now()
                self.assertIsNone(audio.reclamar_trabajo())
                self.assertLess((timezone.now() - inicio).total_seconds(), 2)
            finally:
                liberar.set()
                futuro.result(timeout=5)
        self.assertIsNotNone(audio.reclamar_trabajo())
