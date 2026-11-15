"""Conversación guiada mediante el puerto del núcleo."""

import re
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from canales import mensajes
from canales.models import ConversacionCanal, MensajeEntrante, SalidaCanal
from canales.parseo import parsear_renglones
from canales.salidas import preparar
from pedidos.contratos.v1 import CONTRATO_VERSION, ContextoCanalV1, message_key


def contexto(conversacion):
    return ContextoCanalV1(
        conversacion.sesion.instancia_id,
        conversacion.sesion.sesion_id,
        str(conversacion.id),
        conversacion.cliente_externo_id,
    )


def procesar_mensaje(mensaje, nucleo, lector, ahora, lease_token=None, modelo=None):
    conversacion = mensaje.conversacion
    ctx = contexto(conversacion)
    texto = mensaje.texto.strip()
    partes = texto.split()
    comando = partes[0].upper() if partes else ""
    respuesta = None
    salida = mensajes.ERROR
    pedido_id = conversacion.pedido_id_actual
    ignorado = False
    datos = {"contrato_version": CONTRATO_VERSION}
    if (
        conversacion.sesion.comercio.agente_pedidos_habilitado
        and lease_token is not None
        and mensaje.tipo in ("texto", "audio")
        and (mensaje.tipo != "audio" or (
            hasattr(mensaje, "trabajoaudio") and mensaje.trabajoaudio.estado == "listo"
        ))
        and comando not in {"ACEPTAR", "AYUDA"}
        and not (
            pedido_id
            and re.search(r"\b(?:ya\s+)?pagu[eé]\b", texto, re.IGNORECASE)
        )
        and not (texto.casefold() in {"sí", "si"} and SalidaCanal.objects.filter(
            conversacion=conversacion, tipo="cotizacion_resumen", estado="enviada"
        ).exists())
    ):
        from asistente_pedidos.servicio import procesar
        return procesar(mensaje, nucleo, lector, ahora, lease_token, modelo)
    if mensaje.tipo == "audio" and not hasattr(mensaje, "trabajoaudio"):
        if settings.STT_HABILITADO:
            salida = mensajes.AUDIO_FALLIDO
        else:
            salida, ignorado = mensajes.SOLO_TEXTO, True
    elif mensaje.tipo == "audio" and mensaje.trabajoaudio.estado != "listo":
        salida = mensajes.AUDIO_FALLIDO
    elif mensaje.tipo == "audio" and comando == "ACEPTAR":
        salida = mensajes.ACEPTAR_POR_TEXTO
    elif mensaje.tipo not in ("texto", "audio"):
        salida, ignorado = mensajes.SOLO_TEXTO, True
    elif comando == "AYUDA":
        salida = mensajes.AYUDA
    elif comando == "ACEPTAR":
        resumen = (
            SalidaCanal.objects.filter(
                conversacion=conversacion,
                tipo="cotizacion_resumen",
                estado__in=["enviada", "enviando"],
            )
            .order_by("-envio_iniciado_en")
            .first()
        )
        if not pedido_id or not resumen:
            salida = mensajes.SIN_COTIZACION
        elif (
            len(partes) != 2
            or partes[1].casefold() != resumen.payload["token_resumen"].casefold()
        ):
            salida = mensajes.TOKEN_INVALIDO
        else:
            p = resumen.payload
            respuesta = nucleo.aceptar_cotizacion(
                ctx,
                **datos,
                command_key=f"aceptacion:{mensaje.id}",
                pedido_id=str(pedido_id),
                expected_version=p["pedido_version"],
                cotizacion_id=p["cotizacion_id"],
                cotizacion_revision=p["cotizacion_revision"],
                importe_efectivo_mostrado_centavos=p["importe_efectivo_centavos"],
                politica_cobro_version=p["politica_cobro_version"],
                mensaje_consentimiento_id=str(mensaje.id),
                token_resumen=p["token_resumen"],
            )
            if respuesta.ok:
                pedido = respuesta.data["pedido"]
                cobro = nucleo.solicitar_cobro(
                    ctx,
                    **datos,
                    command_key=f"cobro:{pedido.aceptacion.id}",
                    pedido_id=pedido.id,
                    expected_version=pedido.version,
                    aceptacion_id=pedido.aceptacion.id,
                    canal="qr_venta",
                )
                if not cobro.ok and cobro.error.retryable:
                    respuesta = cobro
                elif not cobro.ok and cobro.error.code.value == "CUENTA_NO_ACTIVE":
                    salida = mensajes.COBRO_NO_DISPONIBLE
                elif (
                    not cobro.ok and cobro.error.code.value != "PROVEEDOR_NO_DISPONIBLE"
                ):
                    salida = mensajes.ERROR
                elif cobro.ok:
                    estado = cobro.data["pedido"].pago_estado.value
                    salida = {
                        "en_espera": mensajes.ESPERA,
                        "reservado": mensajes.PENDIENTE,
                        "enviando": mensajes.PENDIENTE,
                        "pendiente": mensajes.PENDIENTE,
                        "incierto": mensajes.INCIERTO,
                        "descartado": mensajes.OBSOLETA,
                    }.get(estado, mensajes.ACEPTADO)
                else:
                    salida = mensajes.ACEPTADO
    elif pedido_id and re.search(r"\b(?:ya\s+)?pagu[eé]\b", texto, re.IGNORECASE):
        respuesta = nucleo.consultar_pedido(ctx, **datos, pedido_id=str(pedido_id))
        if respuesta.ok:
            pedido = respuesta.data["pedido"]
            estado = pedido.pago_estado.value
            if estado == "pagado":
                salida = mensajes.PAGADO.format(pedido_numero=pedido.numero)
            elif estado == "incierto":
                salida = mensajes.INCIERTO
            else:
                salida = mensajes.AUN_SIN_PAGO
    elif comando == "CORREGIR" or comando.startswith("CORREGIR:"):
        contenido = texto[len("CORREGIR") :].lstrip(": ").strip()
        if not any(c.isalnum() for c in contenido):
            salida = mensajes.AYUDA
        elif pedido_id and contenido:
            consulta = nucleo.consultar_pedido(ctx, **datos, pedido_id=str(pedido_id))
            if consulta.ok:
                version = (
                    int(mensaje.error[8:])
                    if mensaje.error.startswith("version:")
                    else consulta.data["pedido"].version
                )
                if not mensaje.error.startswith("version:"):
                    mensaje.error = f"version:{version}"
                    mensaje.save(update_fields=["error"])
                nuevos = parsear_renglones(contenido, str(mensaje.id))
                disponibles = list(consulta.data["pedido"].renglones)
                for indice, nuevo in enumerate(nuevos):
                    clave = (
                        " ".join(nuevo.texto_solicitado.casefold().split()),
                        nuevo.cantidad_solicitada,
                        (nuevo.unidad_solicitada or "").casefold(),
                    )
                    for anterior in disponibles:
                        cantidad = anterior.cantidad_solicitada
                        anterior_clave = (
                            " ".join(anterior.texto_solicitado.casefold().split()),
                            Decimal(str(cantidad)) if cantidad is not None else None,
                            (anterior.unidad_solicitada or "").casefold(),
                        )
                        if clave == anterior_clave:
                            nuevos[indice] = replace(
                                nuevo, renglon_id=anterior.renglon_id
                            )
                            disponibles.remove(anterior)
                            break
                respuesta = nucleo.corregir_borrador(
                    ctx,
                    **datos,
                    command_key=f"corregir:{mensaje.id}",
                    pedido_id=str(pedido_id),
                    expected_version=version,
                    mensaje_id=str(mensaje.id),
                    message_key=message_key(
                        mensaje.instancia_id,
                        mensaje.sesion_id,
                        mensaje.id_mensaje_proveedor,
                    ),
                    secuencia_conversacion=mensaje.secuencia,
                    renglones=nuevos,
                )
                salida = mensajes.CORREGIDO
            else:
                respuesta = consulta
    elif not any(c.isalnum() for c in texto) or texto.casefold() in {"hola", "gracias"}:
        salida = mensajes.AYUDA
    elif (
        texto.casefold() in {"sí", "si"}
        and SalidaCanal.objects.filter(
            conversacion=conversacion, tipo="cotizacion_resumen", estado="enviada"
        ).exists()
    ):
        salida = mensajes.TOKEN_INVALIDO
    elif texto:
        if pedido_id:
            consulta = nucleo.consultar_pedido(ctx, **datos, pedido_id=str(pedido_id))
            if not consulta.ok:
                respuesta = consulta
            elif consulta.data["pedido"].abierto:
                salida = mensajes.ABIERTO
            else:
                pedido_id = None
        if not pedido_id and respuesta is None:
            respuesta = nucleo.registrar_solicitud(
                ctx,
                **datos,
                command_key=f"registrar:{mensaje.id}",
                mensaje_id=str(mensaje.id),
                message_key=message_key(
                    mensaje.instancia_id,
                    mensaje.sesion_id,
                    mensaje.id_mensaje_proveedor,
                ),
                secuencia_conversacion=mensaje.secuencia,
                renglones=parsear_renglones(texto, str(mensaje.id)),
            )
            salida = mensajes.RECIBIDO
    if respuesta and not respuesta.ok:
        if respuesta.error.retryable:
            with transaction.atomic():
                mensaje.intentos += 1
                mensaje.estado = "reintentable" if mensaje.intentos < 6 else "fallido"
                mensaje.proximo_intento_en = ahora + timedelta(
                    seconds=min(2**mensaje.intentos, 64)
                )
                mensaje.save(
                    update_fields=["intentos", "estado", "proximo_intento_en", "error"]
                )
                aviso = (
                    mensajes.REINTENTO_AGOTADO
                    if mensaje.estado == "fallido"
                    else mensajes.REINTENTO_ESPERA
                )
                if nucleo.ES_SIMULACION:
                    aviso = "[SIMULACIÓN] " + aviso
                causa = "fallo" if mensaje.estado == "fallido" else "espera"
                preparar(
                    conversacion,
                    f"{causa}:{mensaje.id}",
                    "respuesta",
                    {"texto": aviso},
                )
            return
        codigo = respuesta.error.code.value
        salida = {
            "PEDIDO_ABIERTO": mensajes.ABIERTO,
            "REVISION_OBSOLETA": mensajes.OBSOLETA,
            "MODO_CAMBIO": mensajes.OBSOLETA,
        }.get(codigo, mensajes.ERROR)
        if codigo == "PEDIDO_ABIERTO" and respuesta.error.pedido_id:
            pedido_id = respuesta.error.pedido_id
    elif respuesta and respuesta.ok and respuesta.data and respuesta.data.get("pedido"):
        pedido_id = respuesta.data["pedido"].id
    if nucleo.ES_SIMULACION:
        salida = "[SIMULACIÓN] " + salida
    with transaction.atomic():
        ConversacionCanal.objects.filter(pk=conversacion.pk).update(
            pedido_id_actual=pedido_id
        )
        preparar(conversacion, f"mensaje:{mensaje.id}", "respuesta", {"texto": salida})
        MensajeEntrante.objects.filter(pk=mensaje.pk).update(
            estado="ignorado" if ignorado else "procesado", procesado_en=ahora
        )
