"""Cuerpo de alta de venta y la respuesta JSON. Sin modelos propios."""

from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from ventas.servicio import VentaCreada

_CENTAVO = Decimal("0.01")


def _monto_entrada(data: dict, errores: dict) -> Decimal | None:
    if "monto" not in data:
        errores["monto"] = ["Indique el monto."]
        return None
    valor = data["monto"]
    if isinstance(valor, bool) or valor is None:
        errores["monto"] = ["El monto debe ser un número."]
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        if texto == "":
            errores["monto"] = ["Indique el monto."]
            return None
        try:
            return Decimal(texto)
        except InvalidOperation:
            errores["monto"] = ["El monto debe ser un número."]
            return None
    errores["monto"] = ["El monto debe ser un número."]
    return None


def _texto_opcional(data: dict, campo: str, errores: dict) -> str:
    if campo not in data:
        return ""
    valor = data[campo]
    if not isinstance(valor, str):
        errores[campo] = ["Debe ser texto."]
        return ""
    return valor


class CrearVentaSerializer(serializers.Serializer):
    """Acepta monto como cadena o número. Concepto y referencia son opcionales."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("El cuerpo debe ser un objeto JSON.")
        errores: dict = {}
        monto = _monto_entrada(data, errores)
        concepto = _texto_opcional(data, "concepto", errores)
        referencia = _texto_opcional(data, "referencia", errores)
        if errores:
            raise serializers.ValidationError(errores)
        return {
            "monto": monto,
            "concepto": concepto,
            "referencia": referencia,
        }


def venta_creada_a_json(venta: VentaCreada) -> dict:
    movimiento = venta.movimiento
    cobro = venta.cobro
    return {
        "movimiento_id": movimiento.pk,
        "cobro_id": cobro.pk,
        "canal": movimiento.canal,
        "monto": format(movimiento.monto.quantize(_CENTAVO), "f"),
        "concepto": movimiento.concepto,
        "estado": movimiento.estado,
        "vence_en": cobro.vence_en.isoformat(),
        "qr_string": venta.qr_string,
        "origen": movimiento.origen,
    }
