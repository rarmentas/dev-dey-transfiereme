"""Resolución exacta de nombres, unidades y precios aprobados del comercio."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from pedidos.contratos.calculo import subtotal_centavos, total_centavos
from pedidos.contratos.validacion import ErrorContrato


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor).casefold())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())


def _unidad(valor):
    unidades = {
        "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg",
        "pieza": "pieza", "piezas": "pieza", "pza": "pieza", "pzas": "pieza",
        "l": "litro", "lt": "litro", "litro": "litro", "litros": "litro",
        "g": "g", "gr": "g", "gramo": "g", "gramos": "g",
    }
    return unidades.get(normalizar(valor), normalizar(valor))


def resolver(items, productos):
    """Devuelve renglones verificados, aclaraciones y total solo si está completo."""
    filas, faltantes, subtotales = [], [], []
    for item in items[:100]:
        nombre = normalizar(item["nombre"])
        candidatos = [p for p in productos if nombre in [normalizar(p.nombre), *[normalizar(a) for a in p.alias]]]
        fila = {"nombre": item["nombre"], "cantidad": item.get("cantidad"), "unidad": item.get("unidad"),
                "producto_id": None, "descripcion": "", "precio_centavos": None, "resolucion": "pendiente"}
        try:
            cantidad = Decimal(str(item.get("cantidad"))) if item.get("cantidad") is not None else None
        except (InvalidOperation, ValueError, TypeError):
            cantidad = None
        if len(candidatos) != 1:
            motivo = "Producto ambiguo" if candidatos else "Producto sin precio autorizado"
        elif not candidatos[0].disponible or candidatos[0].precio_centavos is None:
            motivo = "Producto no disponible o sin precio autorizado"
        else:
            producto = candidatos[0]
            unidad = _unidad(item.get("unidad") or ("pieza" if _unidad(producto.unidad) == "pieza" else ""))
            if unidad != _unidad(producto.unidad):
                motivo = f"Unidad incompatible para {producto.nombre}: {producto.unidad}"
            elif cantidad is None:
                motivo = f"Falta cantidad de {producto.nombre}"
            else:
                try:
                    subtotal = subtotal_centavos(cantidad, int(producto.precio_centavos))
                except (ErrorContrato, ValueError, TypeError):
                    motivo = f"Cantidad inválida para {producto.nombre}"
                else:
                    fila.update(producto_id=producto.pk, descripcion=producto.nombre,
                                cantidad=str(cantidad), unidad=producto.unidad,
                                precio_centavos=producto.precio_centavos, resolucion="incluido")
                    subtotales.append(subtotal)
                    motivo = None
        if motivo:
            faltantes.append(motivo)
        filas.append(fila)
    try:
        total = total_centavos(subtotales) if filas and not faltantes else None
    except ErrorContrato:
        total = None
        faltantes.append("Total fuera de límite; requiere revisión")
    return filas, faltantes, total
