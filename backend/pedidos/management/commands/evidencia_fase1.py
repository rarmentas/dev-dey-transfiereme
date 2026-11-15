"""Consulta la evidencia persistida de un pedido sin exponer contenido."""

import json
import re
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from canales.models import MensajeEntrante
from pedidos.models import Aceptacion, EventoPedido, Pedido


def _identificador_externo(valor: str | None) -> str | None:
    """Oculta valores que podrían contener datos bancarios o telefónicos."""
    if not valor:
        return None
    if len(re.sub(r"\D", "", valor)) >= 10:
        return "[identificador omitido]"
    return valor


def _cuenta(cuenta) -> dict | None:
    if cuenta is None:
        return None
    return {
        "id": cuenta.pk,
        "clabe_enmascarada": f"***{cuenta.clabe[-4:]}" if cuenta.clabe else None,
        "estado": cuenta.codi_status,
        "registro_estado": cuenta.registro_estado,
        "sincronizada_en": cuenta.sincronizada_en,
    }


class Command(BaseCommand):
    help = "Muestra en JSON la cadena de evidencia de un pedido."

    def add_arguments(self, parser):
        parser.add_argument("--pedido", required=True)

    def handle(self, *args, **opciones):
        try:
            identificador = uuid.UUID(opciones["pedido"])
            pedido = Pedido.objects.get(pk=identificador)
        except (ValueError, TypeError, Pedido.DoesNotExist) as exc:
            raise CommandError("Pedido no encontrado o UUID inválido.") from exc

        revisiones = list(
            pedido.cotizaciones.order_by("revision").values(
                "id", "revision", "publicada_en"
            )
        )
        aceptaciones = list(
            Aceptacion.objects.filter(pedido=pedido)
            .order_by("aceptada_en", "id")
            .values("id", "cotizacion_id", "mensaje_consentimiento_id", "aceptada_en")
        )
        intentos = []
        for intento in pedido.intentos.select_related("cuenta", "cobro").order_by(
            "creado_en", "id"
        ):
            cobro = intento.cobro
            movimientos = []
            if cobro:
                for movimiento in cobro.movimientos.order_by("pk"):
                    avisos = [
                        {
                            "webhook_id": _identificador_externo(aviso.webhook_id),
                            "resultado": aviso.resultado,
                            "correlacion": aviso.correlacion,
                            "recibido_en": aviso.recibido_en,
                            "verificado_en": aviso.verificado_en,
                        }
                        for aviso in movimiento.avisos_recibidos.order_by("pk")
                    ]
                    movimientos.append(
                        {
                            "id": movimiento.pk,
                            "estado": movimiento.estado,
                            "transaccion": _identificador_externo(
                                movimiento.pey_transaction_id
                            ),
                            "creado_en": movimiento.creado_en,
                            "pagado_en": movimiento.pagado_en,
                            "avisos": avisos,
                        }
                    )
            intentos.append(
                {
                    "id": intento.pk,
                    "aceptacion_id": intento.aceptacion_id,
                    "cotizacion_id": intento.cotizacion_id,
                    "estado": intento.estado,
                    "canal": intento.canal,
                    "creado_en": intento.creado_en,
                    "actualizado_en": intento.actualizado_en,
                    "enviado_en": intento.enviado_en,
                    "cuenta": _cuenta(intento.cuenta),
                    "cobro": None
                    if cobro is None
                    else {
                        "id": cobro.pk,
                        "creado_en": cobro.creado_en,
                        "vence_en": cobro.vence_en,
                        "qr_id": _identificador_externo(cobro.pey_qr_id),
                        "transaccion": _identificador_externo(cobro.pey_transaction_id),
                        "movimientos": movimientos,
                    },
                }
            )
        mensaje = (
            MensajeEntrante.objects.filter(
                pk=pedido.mensaje_origen_id,
                conversacion__sesion__comercio_id=pedido.comercio_id,
            )
            .values("id", "tipo", "estado", "recibido_en", "procesado_en")
            .first()
        )
        datos = {
            "mensaje": mensaje,
            "pedido": {
                "id": pedido.pk,
                "mensaje_origen_id": pedido.mensaje_origen_id,
                "estado": pedido.estado,
                "preparacion": pedido.preparacion,
                "revision_vigente": pedido.revision_vigente,
                "creado_en": pedido.creado_en,
                "actualizado_en": pedido.actualizado_en,
                "listo_en": pedido.listo_en,
                "entregado_en": pedido.entregado_en,
            },
            "revisiones": revisiones,
            "aceptaciones": aceptaciones,
            "intentos": intentos,
            "eventos": list(
                EventoPedido.objects.filter(pedido=pedido)
                .order_by("secuencia_comercio")
                .values("evento_id", "tipo", "intento_id", "creado_en")
            ),
        }
        self.stdout.write(json.dumps(datos, cls=DjangoJSONEncoder, ensure_ascii=False))
