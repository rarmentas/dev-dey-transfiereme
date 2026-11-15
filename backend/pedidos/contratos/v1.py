"""Contrato serializable entre el canal y el núcleo."""

import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, Sequence
from uuid import UUID

CONTRATO_VERSION = "1.0"
MAX_RENGLONES = 100
MAX_MENSAJE = 4000
MAX_COMMAND_KEY = 128
TOTAL_MAXIMO_CENTAVOS = 100_000_000
CANTIDAD_MAXIMA = Decimal("9999.999")


class EstadoPedido(str, Enum):
    BORRADOR = "borrador"
    EN_REVISION = "en_revision"
    COTIZADO = "cotizado"
    ACEPTADO = "aceptado"
    CERRADO = "cerrado"


class EstadoPago(str, Enum):
    SIN_COBRO = "sin_cobro"
    EN_ESPERA = "en_espera"
    RESERVADO = "reservado"
    ENVIANDO = "enviando"
    PENDIENTE = "pendiente"
    INCIERTO = "incierto"
    RECHAZADO = "rechazado"
    VENCIDO = "vencido"
    PAGADO = "pagado"
    DESCARTADO = "descartado"


class EstadoPreparacion(str, Enum):
    PENDIENTE = "pendiente"
    LISTO = "listo"
    ENTREGADO = "entregado"


class TipoEvento(str, Enum):
    PEDIDO_CREADO = "pedido.creado"
    PEDIDO_CORREGIDO = "pedido.corregido"
    COTIZACION_PUBLICADA = "cotizacion.publicada"
    COTIZACION_INVALIDADA = "cotizacion.invalidada"
    PEDIDO_ACEPTADO = "pedido.aceptado"
    COBRO_EN_ESPERA = "cobro.en_espera"
    COBRO_PENDIENTE = "cobro.pendiente"
    COBRO_INCIERTO = "cobro.incierto"
    COBRO_RECHAZADO = "cobro.rechazado"
    COBRO_DESCARTADO = "cobro.descartado"
    COBRO_VENCIDO = "cobro.vencido"
    PAGO_CONFIRMADO = "pago.confirmado"
    PEDIDO_LISTO = "pedido.listo"
    PEDIDO_ENTREGADO = "pedido.entregado"
    PEDIDO_CANCELADO = "pedido.cancelado"


class Resolucion(str, Enum):
    PENDIENTE = "pendiente"
    INCLUIDO = "incluido"
    EXCLUIDO = "excluido"


class CanalCobro(str, Enum):
    QR_VENTA = "qr_venta"
    NOTIFICACION = "notificacion"


class CodigoError(str, Enum):
    VERSION_CONTRATO_NO_SOPORTADA = "VERSION_CONTRATO_NO_SOPORTADA"
    PAYLOAD_INVALIDO = "PAYLOAD_INVALIDO"
    CONTEXTO_INVALIDO = "CONTEXTO_INVALIDO"
    PERMISO_DENEGADO = "PERMISO_DENEGADO"
    PEDIDO_NO_ACCESIBLE = "PEDIDO_NO_ACCESIBLE"
    VERSION_OBSOLETA = "VERSION_OBSOLETA"
    REVISION_OBSOLETA = "REVISION_OBSOLETA"
    CLAVE_REUTILIZADA = "CLAVE_REUTILIZADA"
    PEDIDO_ABIERTO = "PEDIDO_ABIERTO"
    PEDIDO_CONGELADO = "PEDIDO_CONGELADO"
    PAGO_NO_CONFIRMADO = "PAGO_NO_CONFIRMADO"
    PREPARACION_INVALIDA = "PREPARACION_INVALIDA"
    RENGLON_PENDIENTE = "RENGLON_PENDIENTE"
    ACEPTACION_REQUERIDA = "ACEPTACION_REQUERIDA"
    IMPORTE_NO_COINCIDE = "IMPORTE_NO_COINCIDE"
    MODO_CAMBIO = "MODO_CAMBIO"
    CUENTA_NO_ACTIVE = "CUENTA_NO_ACTIVE"
    DEMO_DESTINO_NO_PERMITIDO = "DEMO_DESTINO_NO_PERMITIDO"
    CURSOR_INVALIDO = "CURSOR_INVALIDO"
    INTENCION_DISTINTA = "INTENCION_DISTINTA"
    COBRO_OCUPADO = "COBRO_OCUPADO"
    COBRO_EN_CURSO = "COBRO_EN_CURSO"
    PEY_INCIERTO = "PEY_INCIERTO"
    PROVEEDOR_NO_DISPONIBLE = "PROVEEDOR_NO_DISPONIBLE"
    SERVICIO_NO_DISPONIBLE = "SERVICIO_NO_DISPONIBLE"
    SYNC_PRONTO = "SYNC_PRONTO"


def message_key(instancia_id: str, sesion_id: str, payload_id: str) -> str:
    return json.dumps(
        [instancia_id, sesion_id, payload_id], separators=(",", ":"), ensure_ascii=False
    )


def serializar(valor: Any) -> Any:
    """Convierte DTO y valores de dominio a tipos JSON."""
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (UUID, Decimal)):
        return str(valor)
    if isinstance(valor, datetime):
        if valor.utcoffset() is None:
            raise ValueError("La fecha debe tener zona horaria")
        return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if is_dataclass(valor) and not isinstance(valor, type):
        return {
            campo.name: serializar(getattr(valor, campo.name))
            for campo in fields(valor)
        }
    if isinstance(valor, dict):
        return {clave: serializar(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializar(item) for item in valor]
    return valor


class Serializable:
    def a_dict(self) -> dict:
        return serializar(self)


@dataclass(frozen=True)
class ContextoCanalV1(Serializable):
    instancia_id: str
    sesion_id: str
    conversacion_id: str
    cliente_externo_id: str


@dataclass(frozen=True)
class ContextoConsumidorV1(Serializable):
    instancia_id: str
    sesion_id: str


@dataclass(frozen=True)
class RenglonSolicitadoV1(Serializable):
    renglon_id: str
    texto_solicitado: str
    cantidad_solicitada: Decimal | None = None
    unidad_solicitada: str | None = None


@dataclass(frozen=True)
class RenglonDTO(Serializable):
    renglon_id: str
    posicion: int
    texto_solicitado: str
    cantidad_solicitada: Decimal | None
    unidad_solicitada: str | None
    descripcion: str = ""
    cantidad: Decimal | None = None
    unidad: str = ""
    precio_unitario_centavos: int | None = None
    subtotal_centavos: int | None = None
    resolucion: Resolucion = Resolucion.PENDIENTE
    motivo_exclusion: str = ""


@dataclass(frozen=True)
class CotizacionDTO(Serializable):
    id: str
    revision: int
    renglones: Sequence[dict]
    total_comercial_centavos: int
    importe_efectivo_centavos: int
    moneda: str
    demo_mode: bool
    politica_cobro_version: str
    token_resumen: str
    publicada_en: datetime


@dataclass(frozen=True)
class AceptacionDTO(Serializable):
    id: str
    cotizacion_id: str
    aceptada_en: datetime
    identidad: dict


@dataclass(frozen=True)
class CobroDTO(Serializable):
    intento_id: str
    cobro_id: str | None
    canal: CanalCobro
    estado: EstadoPago
    qr: str | None = None
    vencimiento: datetime | None = None
    destino_enmascarado: str | None = None
    aceptacion_id: str | None = None


@dataclass(frozen=True)
class PedidoDTO(Serializable):
    id: str
    numero: int
    version: int
    estado: EstadoPedido
    abierto: bool
    origen: dict
    cliente_etiqueta: str
    renglones: Sequence[RenglonDTO]
    cotizacion: CotizacionDTO | None
    ultima_revision: int
    aceptacion: AceptacionDTO | None
    pago_estado: EstadoPago
    preparacion: EstadoPreparacion
    intento: CobroDTO | None
    simulacion: bool


@dataclass(frozen=True)
class EventoDTO(Serializable):
    evento_id: str
    secuencia_comercio: int
    tipo: TipoEvento
    creado_en: datetime
    pedido_id: str
    pedido_version: int
    conversacion_id: str
    cotizacion_id: str | None
    snapshot: dict
    intento_id: str | None = None
    contrato_version: str = CONTRATO_VERSION


@dataclass(frozen=True)
class MensajeProcedenciaDTO(Serializable):
    mensaje_id: str
    message_key: str
    secuencia_conversacion: int
    tipo: str
    texto_normalizado: str
    timestamp_proveedor: datetime
    recibido_en: datetime
    origen_autenticado: bool


@dataclass(frozen=True)
class ResumenEnviadoDTO(Serializable):
    salida_id: str
    id_proveedor: str
    estado: str
    cotizacion_id: str
    token_resumen: str
    cotizacion_revision: int
    total_comercial_centavos: int
    importe_efectivo_centavos: int
    demo_mode: bool
    politica_cobro_version: str
    destinatario: str
    envio_iniciado_en: datetime
    enviado_en: datetime | None


@dataclass(frozen=True)
class ErrorV1(Serializable):
    code: CodigoError
    detail: str
    retryable: bool = False
    next_action: str = "ninguna"
    pedido_id: str | None = None
    pedido_version: int | None = None
    intento_id: str | None = None


@dataclass(frozen=True)
class RespuestaV1(Serializable):
    ok: bool
    replayed: bool = False
    data: dict | None = None
    error: ErrorV1 | None = None
    contrato_version: str = CONTRATO_VERSION

    def a_dict(self) -> dict:
        if self.ok:
            return serializar(
                {
                    "contrato_version": self.contrato_version,
                    "ok": True,
                    "replayed": self.replayed,
                    "data": self.data,
                }
            )
        return serializar(
            {
                "contrato_version": self.contrato_version,
                "ok": False,
                "error": self.error,
            }
        )


class PuertoNucleoV1(Protocol):
    ES_SIMULACION: bool

    def registrar_solicitud(
        self,
        ctx: ContextoCanalV1,
        *,
        contrato_version: str,
        command_key: str,
        mensaje_id: str,
        message_key: str,
        secuencia_conversacion: int,
        renglones: Sequence[RenglonSolicitadoV1],
    ) -> RespuestaV1: ...

    def corregir_borrador(
        self,
        ctx: ContextoCanalV1,
        *,
        contrato_version: str,
        command_key: str,
        pedido_id: str,
        expected_version: int,
        mensaje_id: str,
        message_key: str,
        secuencia_conversacion: int,
        renglones: Sequence[RenglonSolicitadoV1],
    ) -> RespuestaV1: ...

    def consultar_pedido(
        self, ctx: ContextoCanalV1, *, contrato_version: str, pedido_id: str
    ) -> RespuestaV1: ...

    def aceptar_cotizacion(
        self,
        ctx: ContextoCanalV1,
        *,
        contrato_version: str,
        command_key: str,
        pedido_id: str,
        expected_version: int,
        cotizacion_id: str,
        cotizacion_revision: int,
        importe_efectivo_mostrado_centavos: int,
        politica_cobro_version: str,
        mensaje_consentimiento_id: str,
        token_resumen: str,
    ) -> RespuestaV1: ...

    def solicitar_cobro(
        self,
        ctx: ContextoCanalV1,
        *,
        contrato_version: str,
        command_key: str,
        pedido_id: str,
        expected_version: int,
        aceptacion_id: str,
        canal: str,
        telefono_bancario_confirmado: str | None = None,
    ) -> RespuestaV1: ...

    def consultar_eventos(
        self,
        ctx_consumidor: ContextoConsumidorV1,
        *,
        contrato_version: str,
        cursor: str | None,
        limite: int = 50,
    ) -> RespuestaV1: ...


class LectorProcedenciaV1(Protocol):
    def resolver_comercio(
        self, ctx: ContextoCanalV1 | ContextoConsumidorV1
    ) -> str | None: ...
    def leer_mensaje(
        self, ctx: ContextoCanalV1, mensaje_id: str
    ) -> MensajeProcedenciaDTO | None: ...
    def leer_resumen(
        self, ctx: ContextoCanalV1, cotizacion_id: str
    ) -> ResumenEnviadoDTO | None: ...
