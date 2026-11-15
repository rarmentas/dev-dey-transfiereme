"""Aplica propuestas verificadas mediante el puerto del núcleo y un paso acotado de catálogo."""

import logging
import time
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from django.db import transaction
from django.utils import timezone

from asistente_pedidos.catalogo import normalizar
from asistente_pedidos.grafo import FUERA, construir
from canales.conversacion import contexto
from canales.models import ConversacionCanal, MensajeEntrante
from canales.salidas import preparar
from pedidos.contratos.calculo import subtotal_centavos, total_centavos
from pedidos.contratos.v1 import CONTRATO_VERSION, RenglonSolicitadoV1, message_key
from pedidos.contratos.validacion import ErrorContrato
from pedidos.models import Pedido, ProductoCatalogo

logger = logging.getLogger(__name__)


def _reintentar(mensaje, ahora):
    with transaction.atomic():
        mensaje = MensajeEntrante.objects.select_for_update().get(pk=mensaje.pk)
        mensaje.intentos += 1
        mensaje.estado = "reintentable" if mensaje.intentos < 3 else "fallido"
        mensaje.proximo_intento_en = ahora + timedelta(seconds=min(2 ** mensaje.intentos, 30))
        mensaje.error = "agente_no_disponible"
        mensaje.save(update_fields=["intentos", "estado", "proximo_intento_en", "error"])
        if mensaje.estado == "fallido":
            preparar(mensaje.conversacion, f"mensaje:{mensaje.id}", "respuesta",
                     {"texto": "No pude procesar su pedido. Su mensaje quedó pendiente para revisión; inténtelo más tarde."})


def _filas_anteriores(dto):
    return [RenglonSolicitadoV1(r.renglon_id, r.texto_solicitado,
                                 r.cantidad_solicitada, r.unidad_solicitada) for r in dto.renglones]


def _preparar_renglones(estado, dto, mensaje):
    anteriores = _filas_anteriores(dto) if dto else []
    cambios = {}
    filas_por_id = {}
    for indice, fila in enumerate(estado["filas"]):
        nombre = normalizar(fila["nombre"])
        coincidencias = [r for r in anteriores if normalizar(r.texto_solicitado) == nombre]
        if not coincidencias and fila["producto_id"]:
            coincidencias = [r for r in dto.renglones if r.resolucion.value == "incluido" and normalizar(r.descripcion) == normalizar(fila["descripcion"])] if dto else []
        if not coincidencias and dto and len(estado["filas"]) == 1:
            pendientes = [r for r in dto.renglones if r.resolucion.value == "pendiente"]
            if len(pendientes) == 1:
                coincidencias = pendientes
        identidad = coincidencias[0].renglon_id if len(coincidencias) == 1 else str(uuid5(NAMESPACE_URL, f"agente:{mensaje.pk}:{indice}"))
        try:
            cantidad = Decimal(str(fila["cantidad"])) if fila["cantidad"] is not None else None
        except (InvalidOperation, ValueError, TypeError):
            cantidad = None
        nuevo = RenglonSolicitadoV1(identidad, fila["nombre"], cantidad, fila["unidad"])
        cambios[identidad] = nuevo
        filas_por_id[identidad] = fila
    final = [cambios.pop(r.renglon_id) if r.renglon_id in cambios else r for r in anteriores]
    final.extend(cambios.values())
    return final, filas_por_id


def _aplicar_catalogo(pedido_id, version, filas, comercio_id):
    """Solo modifica renglones de esta versión; el precio queda congelado en la fila."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido_id, comercio_id=comercio_id)
    if pedido.version != version:
        return False
    for renglon in pedido.renglones.select_for_update().all():
        fila = filas.get(str(renglon.pk))
        if not fila:
            continue
        if fila["resolucion"] == "incluido":
            producto = ProductoCatalogo.objects.filter(pk=fila["producto_id"], comercio_id=comercio_id,
                                                        disponible=True, precio_centavos=fila["precio_centavos"]).first()
            if producto:
                renglon.producto_catalogo = producto
                renglon.descripcion = producto.nombre
                renglon.cantidad = Decimal(fila["cantidad"])
                renglon.unidad = producto.unidad
                renglon.precio_unitario_centavos = producto.precio_centavos
                renglon.resolucion = "incluido"
                renglon.motivo_exclusion = ""
            else:
                renglon.producto_catalogo = None
                renglon.descripcion = ""
                renglon.cantidad = None
                renglon.unidad = ""
                renglon.precio_unitario_centavos = None
                renglon.resolucion = "pendiente"
        else:
            renglon.producto_catalogo = None
            renglon.descripcion = ""
            renglon.cantidad = None
            renglon.unidad = ""
            renglon.precio_unitario_centavos = None
            renglon.resolucion = "pendiente"
        renglon.save()
    return True


def _respuesta_pedido(pedido_id, comercio_id):
    pedido = Pedido.objects.get(pk=pedido_id, comercio_id=comercio_id)
    filas = list(pedido.renglones.order_by("posicion"))
    pendientes = [r for r in filas if r.resolucion == "pendiente"]
    if pendientes:
        return "Pedido guardado, pendiente de cotizar. El tendero revisará: " + ", ".join(r.texto_solicitado for r in pendientes[:5]) + "."
    try:
        total = total_centavos(subtotal_centavos(r.cantidad, r.precio_unitario_centavos) for r in filas if r.resolucion == "incluido")
    except ErrorContrato:
        return "Pedido guardado, pendiente de cotizar. El tendero revisará el total."
    return f"Pedido #{pedido.numero} guardado. Total comercial propuesto: ${total / 100:.2f}. El tendero revisará y publicará la cotización."


def procesar(mensaje, nucleo, lector, ahora, lease_token, modelo=None):
    conv = mensaje.conversacion
    ctx = contexto(conv)
    comercio_id = conv.sesion.comercio_id
    pedido_id = conv.pedido_id_actual
    dto = None
    if pedido_id:
        consulta = nucleo.consultar_pedido(ctx, contrato_version=CONTRATO_VERSION, pedido_id=str(pedido_id))
        if consulta.ok:
            dto = consulta.data["pedido"]
    if mensaje.agente_resultado:
        estado = mensaje.agente_resultado
    else:
        productos = list(ProductoCatalogo.objects.filter(comercio_id=comercio_id))
        pendientes = [r.texto_solicitado for r in dto.renglones if r.resolucion.value == "pendiente"] if dto else []
        inicio = time.monotonic()
        try:
            estado = construir(modelo).invoke({
                "comercio_id": comercio_id, "conversacion_id": str(conv.pk), "mensaje_id": str(mensaje.pk),
                "texto": mensaje.texto, "pedido_id": str(pedido_id) if pedido_id else None,
                "version": dto.version if dto else None, "pendientes": pendientes, "productos": productos,
            })
        except Exception as exc:
            logger.warning("agente_error tipo=%s mensaje=%s", type(exc).__name__, mensaje.pk)
            _reintentar(mensaje, ahora)
            return
        finally:
            logger.info("agente_latencia_ms=%s mensaje=%s", round((time.monotonic() - inicio) * 1000), mensaje.pk)
        estado = {k: estado.get(k) for k in ("intencion", "items", "filas", "aclaraciones", "total", "respuesta", "version")}
        if not ConversacionCanal.objects.filter(pk=conv.pk, lease_token=lease_token, lease_hasta__gt=timezone.now()).exists():
            return
        MensajeEntrante.objects.filter(pk=mensaje.pk, agente_resultado={}).update(agente_resultado=estado)
    with transaction.atomic():
        actual = ConversacionCanal.objects.select_for_update().get(pk=conv.pk)
        if actual.lease_token != lease_token or not actual.lease_hasta or actual.lease_hasta <= timezone.now():
            return
        if MensajeEntrante.objects.filter(pk=mensaje.pk, estado__in=["procesado", "ignorado"]).exists():
            return
        salida = estado["respuesta"]
        if estado["intencion"] == "consulta":
            if "precio" in normalizar(mensaje.texto) or "cuesta" in normalizar(mensaje.texto):
                catalogo = ProductoCatalogo.objects.filter(comercio_id=comercio_id, disponible=True)
                encontrados = [p for p in catalogo if p.precio_centavos and any(
                    normalizar(n) in normalizar(mensaje.texto) for n in [p.nombre, *p.alias]
                )]
                salida = ("; ".join(f"{p.nombre}: ${p.precio_centavos // 100}.{p.precio_centavos % 100:02d} por {p.unidad}" for p in encontrados[:5])
                          if len(encontrados) == 1 else "Indíqueme cuál producto de la lista desea consultar.")
            elif dto:
                salida = _respuesta_pedido(pedido_id, comercio_id)
                if dto.pago_estado.value == "pagado":
                    salida += " Pago confirmado por el servidor."
            else:
                salida = "Aún no tiene un pedido registrado. Indíqueme productos y cantidades."
        if estado["intencion"] in {"nuevo", "correccion"} and estado.get("filas"):
            if dto and not dto.abierto:
                salida = "Su pedido actual ya no admite cambios. Pida al tendero que lo revise."
            else:
                renglones, filas = _preparar_renglones(estado, dto, mensaje)
                datos = dict(contrato_version=CONTRATO_VERSION, mensaje_id=str(mensaje.pk),
                             message_key=message_key(mensaje.instancia_id, mensaje.sesion_id, mensaje.id_mensaje_proveedor),
                             secuencia_conversacion=mensaje.secuencia, renglones=renglones)
                if dto:
                    version = estado.get("version") or dto.version
                    respuesta = nucleo.corregir_borrador(ctx, command_key=f"agente:corregir:{mensaje.pk}",
                        pedido_id=str(pedido_id), expected_version=version, **datos)
                else:
                    respuesta = nucleo.registrar_solicitud(ctx, command_key=f"agente:registrar:{mensaje.pk}", **datos)
                if not respuesta.ok:
                    if respuesta.error.retryable:
                        _reintentar(mensaje, ahora)
                        return
                    salida = "El pedido cambió. Revise el estado y vuelva a indicar la corrección."
                else:
                    pedido = respuesta.data["pedido"]
                    pedido_id = pedido.id
                    _aplicar_catalogo(pedido_id, pedido.version, filas, comercio_id)
                    salida = _respuesta_pedido(pedido_id, comercio_id)
        if nucleo.ES_SIMULACION:
            salida = "[SIMULACIÓN] " + salida
        ConversacionCanal.objects.filter(pk=conv.pk).update(pedido_id_actual=pedido_id)
        preparar(conv, f"mensaje:{mensaje.pk}", "respuesta", {"texto": salida})
        MensajeEntrante.objects.filter(pk=mensaje.pk).update(estado="procesado", procesado_en=ahora, error="")
