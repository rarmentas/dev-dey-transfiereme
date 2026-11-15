"""Datos sintéticos y dobles para audio."""

import wave

from ambito.models import Comercio
from canales.models import SesionCanal


class TranscriptorFalso:
    def __init__(self, texto="2 panes"):
        self.texto = texto

    def precargar(self):
        pass

    def transcribir(self, muestras, deadline):
        return self.texto


def crear_sesion():
    comercio = Comercio.objects.create(nombre="Tienda")
    return SesionCanal.objects.create(
        instancia_id="waha", sesion_id="s", comercio=comercio
    )


def payload_audio(identidad="1"):
    return {
        "id": identidad,
        "from": "a@c.us",
        "fromMe": False,
        "hasMedia": True,
        "media": {"mimetype": "audio/ogg", "url": "http://waha/api/files/a"},
    }


def escribir_wav(ruta, canales=1, frecuencia=16000, bytes_muestra=2, frames=160):
    with wave.open(str(ruta), "wb") as wav:
        wav.setparams((canales, bytes_muestra, frecuencia, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01" * canales * bytes_muestra * frames)
