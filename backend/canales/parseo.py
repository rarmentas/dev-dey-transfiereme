"""Análisis determinista de renglones escritos."""

import re
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pedidos.contratos.v1 import RenglonSolicitadoV1

_PATRON = re.compile(
    r"^(\d+(?:[.,]\d{1,3})?)\s*(kg|kilos?|g|gr|litros?|l|lt|piezas?|pzas?|paquetes?|docenas?)?\s*(?:de\s+)?(.+)$",
    re.I,
)


def parsear_renglones(texto: str, semilla: str = "") -> list[RenglonSolicitadoV1]:
    partes = re.split(r"[;\n]|,(?!\d)|(?<!\d),", texto)
    resultado = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        coincidencia = _PATRON.fullmatch(parte)
        cantidad, unidad, nombre = (None, None, parte)
        if coincidencia:
            cantidad = Decimal(coincidencia.group(1).replace(",", "."))
            unidad = coincidencia.group(2)
            nombre = coincidencia.group(3).strip()
        identidad = str(uuid5(NAMESPACE_URL, f"{semilla}:{len(resultado)}:{parte}"))
        resultado.append(RenglonSolicitadoV1(identidad, nombre[:500], cantidad, unidad))
        if len(resultado) == 100:
            break
    return resultado
