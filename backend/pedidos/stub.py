"""Simulación local del puerto núcleo-canal."""

from dataclasses import dataclass, replace

from django.core import signing

from .contratos.calculo import importe_efectivo, subtotal_centavos, total_centavos
from .contratos.fixtures import RelojFijo, id_determinista
from .contratos.v1 import (
    AceptacionDTO,
    CanalCobro,
    CobroDTO,
    CodigoError,
    ContextoCanalV1,
    ContextoConsumidorV1,
    CotizacionDTO,
    ErrorV1,
    EstadoPago,
    EstadoPedido,
    EstadoPreparacion,
    EventoDTO,
    PedidoDTO,
    RenglonDTO,
    RenglonSolicitadoV1,
    RespuestaV1,
    TipoEvento,
    serializar,
)
from .contratos.validacion import ErrorContrato, hash_canonico, validar_comando


@dataclass(frozen=True)
class ModoStub:
    demo: bool = False
    politica: str = "normal-1"


class NucleoStubV1:
    ES_SIMULACION = True

    def __init__(self, lector, reloj=None, modo=ModoStub()):
        self.lector = lector
        self.reloj = reloj or RelojFijo()
        self.modo = modo
        self.pedidos = {}
        self.contextos = {}
        self.eventos = []
        self.comandos = {}
        self.cuenta = "active"
        self.plazas = {}
        self.intenciones = {}
        self.webhooks = set()
        self.webhooks_tempranos = {}
        self.llamadas = 0
        self.resultado_envio = "pendiente"
        self.secuencias = {}

    def _error(self, codigo, detalle="Operación rechazada.", **datos):
        accion = (
            "consultar_pedido"
            if codigo
            in {
                CodigoError.VERSION_OBSOLETA,
                CodigoError.REVISION_OBSOLETA,
                CodigoError.PEDIDO_ABIERTO,
                CodigoError.PROVEEDOR_NO_DISPONIBLE,
            }
            else "ninguna"
        )
        return RespuestaV1(
            False, error=ErrorV1(codigo, detalle, next_action=accion, **datos)
        )

    def _preparar(self, operacion, ctx, datos, mensaje=None):
        try:
            validar_comando(operacion, datos)
        except ErrorContrato as exc:
            return None, None, self._error(exc.codigo, exc.detalle)
        tipo_ctx = (
            ContextoConsumidorV1
            if operacion == "consultar_eventos"
            else ContextoCanalV1
        )
        if not isinstance(ctx, tipo_ctx) or any(
            not isinstance(valor, str) or not valor.strip()
            for valor in ctx.a_dict().values()
        ):
            return None, None, self._error(CodigoError.CONTEXTO_INVALIDO)
        comercio = self.lector.resolver_comercio(ctx)
        if not comercio:
            return None, None, self._error(CodigoError.CONTEXTO_INVALIDO)
        if mensaje:
            procedencia = self.lector.leer_mensaje(ctx, datos[mensaje])
            if (
                not procedencia
                or not procedencia.origen_autenticado
                or not isinstance(procedencia.texto_normalizado, str)
                or len(procedencia.texto_normalizado) > 4000
                or (
                    "message_key" in datos
                    and (
                        procedencia.message_key != datos["message_key"]
                        or procedencia.secuencia_conversacion
                        != datos["secuencia_conversacion"]
                    )
                )
            ):
                return None, None, self._error(CodigoError.CONTEXTO_INVALIDO)
        clave = (comercio, operacion, datos.get("command_key"))
        huella = hash_canonico(operacion, datos, ctx)
        if clave in self.comandos:
            anterior, respuesta = self.comandos[clave]
            if anterior != huella:
                return None, None, self._error(CodigoError.CLAVE_REUTILIZADA)
            return None, None, replace(respuesta, replayed=True)
        return clave, huella, None

    def _guardar(self, clave, huella, pedido, replayed=False):
        respuesta = RespuestaV1(True, replayed=replayed, data={"pedido": pedido})
        self.comandos[clave] = (huella, respuesta)
        return respuesta

    def _obtener(self, ctx, pedido_id):
        return (
            self.pedidos.get(pedido_id)
            if self.contextos.get(pedido_id) == ctx
            else None
        )

    def _evento(self, pedido, ctx, tipo):
        comercio = self.lector.resolver_comercio(ctx)
        secuencia = sum(1 for c, _, _ in self.eventos if c == comercio) + 1
        evento = EventoDTO(
            id_determinista(comercio, f"evento:{secuencia}"),
            secuencia,
            tipo,
            self.reloj(),
            pedido.id,
            pedido.version,
            ctx.conversacion_id,
            pedido.cotizacion.id if pedido.cotizacion else None,
            {
                "estado": pedido.estado,
                "pago_estado": pedido.pago_estado,
                "preparacion": pedido.preparacion,
                "cotizacion_revision": pedido.cotizacion.revision
                if pedido.cotizacion
                else None,
                "total_comercial_centavos": pedido.cotizacion.total_comercial_centavos
                if pedido.cotizacion
                else None,
                "importe_efectivo_centavos": pedido.cotizacion.importe_efectivo_centavos
                if pedido.cotizacion
                else None,
                "demo_mode": pedido.cotizacion.demo_mode if pedido.cotizacion else None,
            },
            intento_id=pedido.intento.intento_id if pedido.intento else None,
        )
        self.eventos.append((comercio, ctx, evento))

    def registrar_solicitud(self, ctx, **datos):
        clave, huella, error = self._preparar(
            "registrar_solicitud", ctx, datos, "mensaje_id"
        )
        if error:
            return error
        for pedido_id, contexto in self.contextos.items():
            pedido = self.pedidos[pedido_id]
            if (
                self.lector.resolver_comercio(contexto) == clave[0]
                and (
                    contexto.instancia_id,
                    contexto.sesion_id,
                    contexto.conversacion_id,
                )
                == (ctx.instancia_id, ctx.sesion_id, ctx.conversacion_id)
                and pedido.abierto
            ):
                return self._error(
                    CodigoError.PEDIDO_ABIERTO,
                    pedido_id=pedido.id,
                    pedido_version=pedido.version,
                )
        pedido_id = id_determinista(clave[0], f"pedido:{datos['mensaje_id']}")
        solicitados = [
            RenglonSolicitadoV1(**r) if isinstance(r, dict) else r
            for r in datos["renglones"]
        ]
        renglones = [
            RenglonDTO(
                r.renglon_id,
                i,
                r.texto_solicitado,
                r.cantidad_solicitada,
                r.unidad_solicitada,
            )
            for i, r in enumerate(solicitados, 1)
        ]
        pedido = PedidoDTO(
            pedido_id,
            len(self.pedidos) + 1,
            1,
            EstadoPedido.BORRADOR,
            True,
            {
                "canal": "whatsapp",
                "mensaje_id": datos["mensaje_id"],
                "creado_en": self.reloj(),
            },
            ctx.cliente_externo_id[-4:],
            renglones,
            None,
            0,
            None,
            EstadoPago.SIN_COBRO,
            EstadoPreparacion.PENDIENTE,
            None,
            True,
        )
        self.pedidos[pedido_id] = pedido
        self.contextos[pedido_id] = ctx
        self.secuencias[pedido_id] = datos["secuencia_conversacion"]
        self._evento(pedido, ctx, TipoEvento.PEDIDO_CREADO)
        return self._guardar(clave, huella, pedido)

    def corregir_borrador(self, ctx, **datos):
        clave, huella, error = self._preparar(
            "corregir_borrador", ctx, datos, "mensaje_id"
        )
        if error:
            return error
        pedido = self._obtener(ctx, datos["pedido_id"])
        if not pedido:
            return self._error(CodigoError.PEDIDO_NO_ACCESIBLE)
        if pedido.version != datos["expected_version"]:
            return self._error(CodigoError.VERSION_OBSOLETA)
        if datos["secuencia_conversacion"] <= self.secuencias[pedido.id]:
            return self._error(CodigoError.VERSION_OBSOLETA)
        if pedido.pago_estado not in {EstadoPago.SIN_COBRO, EstadoPago.EN_ESPERA}:
            return self._error(CodigoError.PEDIDO_CONGELADO)
        solicitados = [
            RenglonSolicitadoV1(**r) if isinstance(r, dict) else r
            for r in datos["renglones"]
        ]
        renglones = [
            RenglonDTO(
                r.renglon_id,
                i,
                r.texto_solicitado,
                r.cantidad_solicitada,
                r.unidad_solicitada,
            )
            for i, r in enumerate(solicitados, 1)
        ]
        descartado = (
            pedido.intento is not None and pedido.pago_estado == EstadoPago.EN_ESPERA
        )
        if descartado:
            aceptacion_id = pedido.aceptacion.id
            pedido = replace(
                pedido,
                intento=replace(pedido.intento, estado=EstadoPago.DESCARTADO),
                pago_estado=EstadoPago.DESCARTADO,
            )
        if descartado:
            self.intenciones[aceptacion_id] = (
                pedido.intento,
                self.intenciones[aceptacion_id][1],
            )
        tenia_cotizacion = pedido.cotizacion is not None
        pedido = replace(
            pedido,
            version=pedido.version + 1,
            renglones=renglones,
            estado=EstadoPedido.BORRADOR,
            cotizacion=None,
            aceptacion=None,
        )
        self.pedidos[pedido.id] = pedido
        self.secuencias[pedido.id] = datos["secuencia_conversacion"]
        if descartado:
            self._evento(pedido, ctx, TipoEvento.COBRO_DESCARTADO)
        if tenia_cotizacion:
            self._evento(pedido, ctx, TipoEvento.COTIZACION_INVALIDADA)
        self._evento(pedido, ctx, TipoEvento.PEDIDO_CORREGIDO)
        return self._guardar(clave, huella, pedido)

    def consultar_pedido(self, ctx, **datos):
        _, _, error = self._preparar("consultar_pedido", ctx, datos)
        if error:
            return error
        pedido = self._obtener(ctx, datos["pedido_id"])
        return (
            RespuestaV1(True, data={"pedido": pedido})
            if pedido
            else self._error(CodigoError.PEDIDO_NO_ACCESIBLE)
        )

    def aceptar_cotizacion(self, ctx, **datos):
        clave, huella, error = self._preparar(
            "aceptar_cotizacion", ctx, datos, "mensaje_consentimiento_id"
        )
        if error:
            return error
        pedido = self._obtener(ctx, datos["pedido_id"])
        if not pedido:
            return self._error(CodigoError.PEDIDO_NO_ACCESIBLE)
        cot = pedido.cotizacion
        if (
            not cot
            or cot.id != datos["cotizacion_id"]
            or cot.revision != datos["cotizacion_revision"]
            or cot.token_resumen != datos["token_resumen"]
        ):
            return self._error(CodigoError.REVISION_OBSOLETA)
        if (cot.demo_mode, cot.politica_cobro_version) != (
            self.modo.demo,
            self.modo.politica,
        ):
            return self._error(CodigoError.MODO_CAMBIO)
        if datos["politica_cobro_version"] != cot.politica_cobro_version:
            return self._error(CodigoError.MODO_CAMBIO)
        if datos["importe_efectivo_mostrado_centavos"] != cot.importe_efectivo_centavos:
            return self._error(CodigoError.IMPORTE_NO_COINCIDE)
        msg = self.lector.leer_mensaje(ctx, datos["mensaje_consentimiento_id"])
        resumen = self.lector.leer_resumen(ctx, cot.id)
        if (
            not resumen
            or resumen.estado != "enviado"
            or not resumen.id_proveedor
            or not resumen.enviado_en
            or resumen.destinatario != ctx.cliente_externo_id
            or resumen.token_resumen != cot.token_resumen
            or resumen.cotizacion_id != cot.id
            or resumen.cotizacion_revision != cot.revision
            or resumen.total_comercial_centavos != cot.total_comercial_centavos
            or resumen.importe_efectivo_centavos != cot.importe_efectivo_centavos
            or resumen.demo_mode != cot.demo_mode
            or resumen.politica_cobro_version != cot.politica_cobro_version
            or msg.recibido_en < resumen.envio_iniciado_en
            or msg.tipo != "texto"
            or " ".join(msg.texto_normalizado.split()).casefold()
            != f"ACEPTAR {cot.token_resumen}".casefold()
        ):
            retryable = bool(resumen and resumen.estado != "enviado")
            return RespuestaV1(
                False,
                error=ErrorV1(
                    CodigoError.ACEPTACION_REQUERIDA,
                    "Consentimiento o resumen inválido.",
                    retryable=retryable,
                ),
            )
        if pedido.aceptacion:
            return self._guardar(clave, huella, pedido, replayed=True)
        if pedido.version != datos["expected_version"]:
            return self._error(CodigoError.VERSION_OBSOLETA)
        aceptacion = AceptacionDTO(
            id_determinista(cot.id, "aceptacion"),
            cot.id,
            self.reloj(),
            {
                "conversacion_id": ctx.conversacion_id,
                "cliente_etiqueta": pedido.cliente_etiqueta,
            },
        )
        pedido = replace(
            pedido,
            aceptacion=aceptacion,
            estado=EstadoPedido.ACEPTADO,
            version=pedido.version + 1,
        )
        self.pedidos[pedido.id] = pedido
        self._evento(pedido, ctx, TipoEvento.PEDIDO_ACEPTADO)
        return self._guardar(clave, huella, pedido)

    def solicitar_cobro(self, ctx, **datos):
        clave, huella, error = self._preparar("solicitar_cobro", ctx, datos)
        if error:
            return error
        pedido = self._obtener(ctx, datos["pedido_id"])
        if not pedido:
            return self._error(CodigoError.PEDIDO_NO_ACCESIBLE)
        intencion = self.intenciones.get(datos["aceptacion_id"])
        if intencion:
            anterior, telefono = intencion
            if anterior.canal.value != datos["canal"] or telefono != datos.get(
                "telefono_bancario_confirmado"
            ):
                return self._error(CodigoError.INTENCION_DISTINTA)
            return self._guardar(clave, huella, pedido, replayed=True)
        if not pedido.aceptacion or pedido.aceptacion.id != datos["aceptacion_id"]:
            return self._error(CodigoError.ACEPTACION_REQUERIDA)
        if pedido.version != datos["expected_version"]:
            return self._error(CodigoError.VERSION_OBSOLETA)
        if not pedido.cotizacion or (
            pedido.cotizacion.demo_mode,
            pedido.cotizacion.politica_cobro_version,
        ) != (self.modo.demo, self.modo.politica):
            return self._error(CodigoError.MODO_CAMBIO)
        if self.cuenta != "active":
            return self._error(CodigoError.CUENTA_NO_ACTIVE)
        comercio = self.lector.resolver_comercio(ctx)
        ocupado = comercio in self.plazas
        estado = EstadoPago.EN_ESPERA if ocupado else EstadoPago.RESERVADO
        intento = CobroDTO(
            id_determinista(pedido.id, "intento"),
            None,
            CanalCobro(datos["canal"]),
            estado,
        )
        self.intenciones[datos["aceptacion_id"]] = (
            intento,
            datos.get("telefono_bancario_confirmado"),
        )
        pedido = replace(
            pedido, intento=intento, pago_estado=estado, version=pedido.version + 1
        )
        self.pedidos[pedido.id] = pedido
        if ocupado:
            self._evento(pedido, ctx, TipoEvento.COBRO_EN_ESPERA)
        else:
            self.plazas[comercio] = pedido.id
            pedido = self._enviar(pedido)
        return self._guardar(clave, huella, pedido)

    def _enviar(self, pedido):
        self.llamadas += 1
        estado = (
            EstadoPago.INCIERTO
            if self.resultado_envio == "incierto"
            else EstadoPago.PENDIENTE
        )
        cobro_id = (
            None
            if estado == EstadoPago.INCIERTO
            else id_determinista(pedido.id, "cobro")
        )
        intento = replace(pedido.intento, estado=estado, cobro_id=cobro_id)
        pedido = replace(
            pedido, intento=intento, pago_estado=estado, version=pedido.version + 1
        )
        self.pedidos[pedido.id] = pedido
        aceptacion_id = pedido.aceptacion.id
        self.intenciones[aceptacion_id] = (intento, self.intenciones[aceptacion_id][1])
        tipo = (
            TipoEvento.COBRO_INCIERTO
            if estado == EstadoPago.INCIERTO
            else TipoEvento.COBRO_PENDIENTE
        )
        self._evento(pedido, self.contextos[pedido.id], tipo)
        if cobro_id in self.webhooks_tempranos:
            for webhook in self.webhooks_tempranos.pop(cobro_id):
                self._confirmar(pedido.id, webhook)
            pedido = self.pedidos[pedido.id]
        return pedido

    def _confirmar(self, pedido_id, webhook_id):
        if webhook_id in self.webhooks:
            return self.pedidos[pedido_id]
        self.webhooks.add(webhook_id)
        pedido = self.pedidos[pedido_id]
        if pedido.pago_estado == EstadoPago.PAGADO:
            return pedido
        intento = replace(pedido.intento, estado=EstadoPago.PAGADO)
        pedido = replace(
            pedido,
            intento=intento,
            pago_estado=EstadoPago.PAGADO,
            version=pedido.version + 1,
        )
        self.pedidos[pedido.id] = pedido
        self.intenciones[pedido.aceptacion.id] = (
            intento,
            self.intenciones[pedido.aceptacion.id][1],
        )
        comercio = self.lector.resolver_comercio(self.contextos[pedido.id])
        self.plazas.pop(comercio, None)
        self._evento(pedido, self.contextos[pedido.id], TipoEvento.PAGO_CONFIRMADO)
        return pedido

    def consultar_eventos(self, ctx_consumidor, **datos):
        _, _, error = self._preparar("consultar_eventos", ctx_consumidor, datos)
        if error:
            return error
        comercio = self.lector.resolver_comercio(ctx_consumidor)
        identidad = [comercio, ctx_consumidor.instancia_id, ctx_consumidor.sesion_id]
        try:
            payload = (
                signing.loads(
                    datos["cursor"], key="pedidos-stub-v1", salt="pedidos.cursor.v1"
                )
                if datos["cursor"]
                else {"identidad": identidad, "secuencia": 0}
            )
            if (
                not isinstance(payload, dict)
                or payload.get("identidad") != identidad
                or type(payload.get("secuencia")) is not int
                or payload["secuencia"] < 0
            ):
                raise ValueError
            ultimo = payload["secuencia"]
        except (signing.BadSignature, ValueError, TypeError):
            return self._error(CodigoError.CURSOR_INVALIDO)
        filtrados = [
            evento
            for c, ctx, evento in self.eventos
            if c == comercio
            and ctx.instancia_id == ctx_consumidor.instancia_id
            and ctx.sesion_id == ctx_consumidor.sesion_id
            and evento.secuencia_comercio > ultimo
        ]
        pagina = filtrados[: datos.get("limite", 50)]
        siguiente = pagina[-1].secuencia_comercio if pagina else ultimo
        cursor = signing.dumps(
            {"identidad": identidad, "secuencia": siguiente},
            key="pedidos-stub-v1",
            salt="pedidos.cursor.v1",
        )
        return RespuestaV1(
            True,
            data={
                "eventos": pagina,
                "next_cursor": cursor,
                "has_more": len(filtrados) > len(pagina),
            },
        )


class DriverStubV1:
    def __init__(self, nucleo):
        self.nucleo = nucleo

    def publicar_cotizacion(self, pedido_id, renglones):
        pedido = self.nucleo.pedidos[pedido_id]
        snapshot = [
            dict(
                r,
                subtotal_centavos=subtotal_centavos(
                    r["cantidad"], r["precio_unitario_centavos"]
                ),
            )
            for r in renglones
        ]
        total = total_centavos([r["subtotal_centavos"] for r in snapshot])
        revision = pedido.ultima_revision + 1
        cot = CotizacionDTO(
            id_determinista(pedido_id, f"cotizacion:{revision}"),
            revision,
            serializar(snapshot),
            total,
            importe_efectivo(total, self.nucleo.modo.demo),
            "MXN",
            self.nucleo.modo.demo,
            self.nucleo.modo.politica,
            f"P{pedido.numero}-R{revision}",
            self.nucleo.reloj(),
        )
        pedido = replace(
            pedido,
            cotizacion=cot,
            ultima_revision=revision,
            estado=EstadoPedido.COTIZADO,
            version=pedido.version + 1,
            aceptacion=None,
        )
        self.nucleo.pedidos[pedido_id] = pedido
        self.nucleo._evento(
            pedido, self.nucleo.contextos[pedido_id], TipoEvento.COTIZACION_PUBLICADA
        )
        return pedido

    def invalidar_cotizacion(self, pedido_id):
        pedido = self.nucleo.pedidos[pedido_id]
        pedido = replace(
            pedido,
            cotizacion=None,
            aceptacion=None,
            estado=EstadoPedido.EN_REVISION,
            version=pedido.version + 1,
        )
        self.nucleo.pedidos[pedido_id] = pedido
        self.nucleo._evento(
            pedido, self.nucleo.contextos[pedido_id], TipoEvento.COTIZACION_INVALIDADA
        )
        return pedido

    def cambiar_modo(self, demo, politica):
        self.nucleo.modo = ModoStub(demo, politica)
        for pedido in list(self.nucleo.pedidos.values()):
            if pedido.pago_estado != EstadoPago.RESERVADO or not pedido.cotizacion:
                continue
            if (
                pedido.cotizacion.demo_mode,
                pedido.cotizacion.politica_cobro_version,
            ) == (demo, politica):
                continue
            intento = replace(pedido.intento, estado=EstadoPago.DESCARTADO)
            aceptacion_id = pedido.aceptacion.id
            self.nucleo.intenciones[aceptacion_id] = (
                intento,
                self.nucleo.intenciones[aceptacion_id][1],
            )
            pedido = replace(
                pedido,
                intento=intento,
                pago_estado=EstadoPago.DESCARTADO,
                cotizacion=None,
                aceptacion=None,
                estado=EstadoPedido.EN_REVISION,
                version=pedido.version + 1,
            )
            self.nucleo.pedidos[pedido.id] = pedido
            ctx = self.nucleo.contextos[pedido.id]
            self.nucleo.plazas.pop(self.nucleo.lector.resolver_comercio(ctx), None)
            self.nucleo._evento(pedido, ctx, TipoEvento.COBRO_DESCARTADO)
            self.nucleo._evento(pedido, ctx, TipoEvento.COTIZACION_INVALIDADA)

    def fijar_cuenta(self, estado):
        self.nucleo.cuenta = estado

    def ocupar_comercio(self, comercio="comercio"):
        self.nucleo.plazas[comercio] = "ocupado"

    def forzar_incierto(self):
        self.nucleo.resultado_envio = "incierto"

    def confirmar_pago(self, pedido_id, webhook_id):
        return self.nucleo._confirmar(pedido_id, webhook_id)

    def webhook_temprano(self, cobro_id, webhook_id):
        self.nucleo.webhooks_tempranos.setdefault(cobro_id, set()).add(webhook_id)

    def marcar_listo(self, pedido_id):
        pedido = self.nucleo.pedidos[pedido_id]
        if pedido.pago_estado != EstadoPago.PAGADO:
            raise ValueError("El pedido no está pagado.")
        pedido = replace(
            pedido, preparacion=EstadoPreparacion.LISTO, version=pedido.version + 1
        )
        self.nucleo.pedidos[pedido_id] = pedido
        self.nucleo._evento(
            pedido, self.nucleo.contextos[pedido_id], TipoEvento.PEDIDO_LISTO
        )
        return pedido

    def marcar_entregado(self, pedido_id):
        pedido = self.nucleo.pedidos[pedido_id]
        if pedido.preparacion != EstadoPreparacion.LISTO:
            raise ValueError("El pedido no está listo.")
        pedido = replace(
            pedido,
            preparacion=EstadoPreparacion.ENTREGADO,
            estado=EstadoPedido.CERRADO,
            abierto=False,
            version=pedido.version + 1,
        )
        self.nucleo.pedidos[pedido_id] = pedido
        self.nucleo._evento(
            pedido, self.nucleo.contextos[pedido_id], TipoEvento.PEDIDO_ENTREGADO
        )
        return pedido

    def activar_intento_en_espera(
        self, pedido_id, intento_id, expected_version, command_key
    ):
        pedido = self.nucleo.pedidos[pedido_id]
        if pedido.intento is None or pedido.intento.intento_id != intento_id:
            raise ValueError("Intento desconocido.")
        if pedido.pago_estado != EstadoPago.EN_ESPERA:
            return pedido
        if pedido.version != expected_version:
            raise ValueError("Versión obsoleta.")
        comercio = self.nucleo.lector.resolver_comercio(
            self.nucleo.contextos[pedido_id]
        )
        if (
            not pedido.aceptacion
            or not pedido.cotizacion
            or (pedido.cotizacion.demo_mode, pedido.cotizacion.politica_cobro_version)
            != (self.nucleo.modo.demo, self.nucleo.modo.politica)
        ):
            intento = replace(pedido.intento, estado=EstadoPago.DESCARTADO)
            pedido = replace(
                pedido,
                intento=intento,
                pago_estado=EstadoPago.DESCARTADO,
                cotizacion=None,
                aceptacion=None,
                version=pedido.version + 1,
            )
            self.nucleo.pedidos[pedido.id] = pedido
            self.nucleo._evento(
                pedido, self.nucleo.contextos[pedido.id], TipoEvento.COBRO_DESCARTADO
            )
            self.nucleo._evento(
                pedido,
                self.nucleo.contextos[pedido.id],
                TipoEvento.COTIZACION_INVALIDADA,
            )
            return pedido
        if comercio in self.nucleo.plazas or self.nucleo.cuenta != "active":
            return pedido
        self.nucleo.plazas[comercio] = pedido.id
        pedido = replace(
            pedido,
            intento=replace(pedido.intento, estado=EstadoPago.RESERVADO),
            pago_estado=EstadoPago.RESERVADO,
        )
        self.nucleo.pedidos[pedido.id] = pedido
        return self.nucleo._enviar(pedido)

    def contexto(self, sufijo="", comercio="comercio"):
        from .contratos.v1 import ContextoCanalV1

        ctx = ContextoCanalV1(
            "instancia", "sesion", "chat" + sufijo, "cliente" + sufijo
        )
        self.nucleo.lector.comercios[(ctx.instancia_id, ctx.sesion_id)] = comercio
        return ctx

    def agregar_mensaje(self, ctx, clave, secuencia, texto, tipo="texto"):
        from .contratos.v1 import MensajeProcedenciaDTO, message_key

        mensaje_id = id_determinista(ctx.conversacion_id, clave)
        llave = message_key(ctx.instancia_id, ctx.sesion_id, clave)
        fecha = self.nucleo.reloj()
        self.nucleo.lector.mensajes[(ctx, mensaje_id)] = MensajeProcedenciaDTO(
            mensaje_id, llave, secuencia, tipo, texto, fecha, fecha, True
        )
        return mensaje_id, llave

    def agregar_resumen(self, ctx, cotizacion):
        from .contratos.v1 import ResumenEnviadoDTO

        fecha = self.nucleo.reloj()
        resumen = ResumenEnviadoDTO(
            id_determinista(cotizacion.id, "salida"),
            "proveedor",
            "enviado",
            cotizacion.id,
            cotizacion.token_resumen,
            cotizacion.revision,
            cotizacion.total_comercial_centavos,
            cotizacion.importe_efectivo_centavos,
            cotizacion.demo_mode,
            cotizacion.politica_cobro_version,
            ctx.cliente_externo_id,
            fecha,
            fecha,
        )
        self.nucleo.lector.resumenes[(ctx, cotizacion.id)] = resumen

    def liberar_comercio(self, comercio="comercio"):
        self.nucleo.plazas.pop(comercio, None)

    def contar_llamadas(self):
        return self.nucleo.llamadas

    def cambiar_sesion(self, ctx, sesion, comercio=None):
        comercio = comercio or self.nucleo.lector.resolver_comercio(ctx)
        self.nucleo.lector.comercios[(ctx.instancia_id, sesion)] = comercio

    def reservar_sin_envio(self, pedido_id):
        pedido = self.nucleo.pedidos[pedido_id]
        intento = CobroDTO(
            id_determinista(pedido_id, "intento"),
            None,
            CanalCobro.QR_VENTA,
            EstadoPago.RESERVADO,
        )
        self.nucleo.intenciones[pedido.aceptacion.id] = (intento, None)
        comercio = self.nucleo.lector.resolver_comercio(
            self.nucleo.contextos[pedido_id]
        )
        self.nucleo.plazas[comercio] = pedido_id
        pedido = replace(
            pedido,
            intento=intento,
            pago_estado=EstadoPago.RESERVADO,
            version=pedido.version + 1,
        )
        self.nucleo.pedidos[pedido_id] = pedido
        return pedido

    def audio_fallido(self, ctx, mensaje_id):
        mensaje = self.nucleo.lector.leer_mensaje(ctx, mensaje_id)
        if not mensaje or mensaje.tipo != "audio":
            raise ValueError("Se requiere un mensaje de audio.")
        return "Envíe su pedido por texto."
