"""Lectura de procedencia autenticada para el núcleo."""

from django.core.exceptions import ValidationError

from canales.models import ConversacionCanal, MensajeEntrante, SalidaCanal, SesionCanal
from pedidos.contratos.v1 import (
    ContextoCanalV1,
    MensajeProcedenciaDTO,
    ResumenEnviadoDTO,
    message_key,
)


class LectorProcedenciaCanal:
    def resolver_comercio(self, ctx):
        sesion = SesionCanal.objects.filter(
            instancia_id=ctx.instancia_id, sesion_id=ctx.sesion_id, estado="activa"
        ).first()
        if not sesion:
            return None
        if isinstance(ctx, ContextoCanalV1):
            try:
                existe = ConversacionCanal.objects.filter(
                    pk=ctx.conversacion_id,
                    sesion=sesion,
                    cliente_externo_id=ctx.cliente_externo_id,
                ).exists()
            except (ValueError, ValidationError):
                return None
            if not existe:
                return None
        return str(sesion.comercio_id)

    def leer_mensaje(self, ctx, mensaje_id):
        if not self.resolver_comercio(ctx):
            return None
        try:
            mensaje = MensajeEntrante.objects.filter(
                pk=mensaje_id, conversacion_id=ctx.conversacion_id
            ).first()
        except (ValueError, ValidationError):
            return None
        if not mensaje:
            return None
        return MensajeProcedenciaDTO(
            str(mensaje.id),
            message_key(
                mensaje.instancia_id, mensaje.sesion_id, mensaje.id_mensaje_proveedor
            ),
            mensaje.secuencia,
            mensaje.tipo,
            " ".join(mensaje.texto.split()),
            mensaje.timestamp_proveedor,
            mensaje.recibido_en,
            True,
        )

    def leer_resumen(self, ctx, cotizacion_id):
        return self._resumen(ctx, cotizacion_id, pendiente=False)

    def leer_resumen_pendiente(self, ctx, cotizacion_id):
        return self._resumen(ctx, cotizacion_id, pendiente=True)

    def _resumen(self, ctx, cotizacion_id, pendiente):
        if not self.resolver_comercio(ctx):
            return None
        salida = (
            SalidaCanal.objects.filter(
                conversacion_id=ctx.conversacion_id,
                tipo="cotizacion_resumen",
                estado="enviando" if pendiente else "enviada",
                payload__cotizacion_id=str(cotizacion_id),
            )
            .order_by("-envio_iniciado_en")
            .first()
        )
        if not salida or (not pendiente and not salida.id_proveedor):
            return None
        p = salida.payload
        return ResumenEnviadoDTO(
            str(salida.id),
            salida.id_proveedor,
            "enviando" if pendiente else "enviado",
            p["cotizacion_id"],
            p["token_resumen"],
            p["cotizacion_revision"],
            p["total_comercial_centavos"],
            p["importe_efectivo_centavos"],
            p["demo_mode"],
            p["politica_cobro_version"],
            salida.destinatario,
            salida.envio_iniciado_en,
            salida.enviado_en,
        )
