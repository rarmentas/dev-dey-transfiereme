"""Resolución exacta de nombres, unidades y precios aprobados del comercio."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from pedidos.contratos.calculo import subtotal_centavos, total_centavos
from pedidos.contratos.validacion import ErrorContrato


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor).casefold())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())


_PRESENTACION = re.compile(r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(kg|g|l|lt|litros?|ml)$")
_ESCALAS = {"kg": ("peso", 1000), "g": ("peso", 1),
            "l": ("volumen", 1000), "lt": ("volumen", 1000),
            "litro": ("volumen", 1000), "litros": ("volumen", 1000),
            "ml": ("volumen", 1)}


def presentacion(producto):
    """Nombre y tamaño explícitos de un paquete vendido por pieza."""
    if normalizar(getattr(producto, "unidad", "")) != "pieza":
        return None
    coincidencia = _PRESENTACION.fullmatch(normalizar(producto.nombre))
    if not coincidencia:
        return None
    base, cantidad, unidad = coincidencia.groups()
    familia, factor = _ESCALAS[unidad]
    return base, Decimal(cantidad.replace(",", ".")) * factor, familia


def nombres_pedido(producto):
    nombres = [producto.nombre, *producto.alias]
    empaque = presentacion(producto)
    return [*nombres, empaque[0]] if empaque else nombres


def coincidencias_pedido(nombre, productos):
    pedido = normalizar(nombre)
    exactas = [p for p in productos if pedido in [normalizar(n) for n in [p.nombre, *p.alias]]]
    if exactas:
        return exactas
    return [p for p in productos if (empaque := presentacion(p)) and empaque[0] == pedido]


def piezas_para_cantidad(producto, cantidad, unidad):
    empaque = presentacion(producto)
    if not empaque:
        return None
    solicitado = _ESCALAS.get(normalizar(unidad))
    if not solicitado or solicitado[0] != empaque[2] or empaque[1] <= 0:
        return None
    piezas = cantidad * solicitado[1] / empaque[1]
    return piezas if piezas > 0 and piezas == piezas.to_integral_value() else None


def coincidencias_consulta(texto, productos):
    """Busca una frase breve por prefijo de nombre o alias, sin tratarla como pedido."""
    def canonico(valor):
        return re.sub(r"\b(?:lt|litro|litros)\b", "l", normalizar(valor))

    consulta = canonico(texto)
    if not consulta:
        return []
    return [producto for producto in productos if any(
        re.search(r"^" + re.escape(consulta) + r"(?:\b|$)", canonico(nombre))
        for nombre in [producto.nombre, *producto.alias] if nombre
    )]


def _unidad(valor):
    unidades = {
        "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg",
        "pieza": "pieza", "piezas": "pieza", "pza": "pieza", "pzas": "pieza",
        "l": "litro", "lt": "litro", "litro": "litro", "litros": "litro",
        "g": "g", "gr": "g", "gramo": "g", "gramos": "g", "ml": "ml",
    }
    return unidades.get(normalizar(valor), normalizar(valor))


def resolver(items, productos):
    """Devuelve renglones verificados, aclaraciones y total solo si está completo."""
    filas, faltantes, subtotales = [], [], []
    for item in items[:100]:
        nombre = normalizar(item["nombre"])
        candidatos = coincidencias_pedido(nombre, productos)
        fila = {"nombre": item["nombre"], "cantidad": item.get("cantidad"), "unidad": item.get("unidad"),
                "operacion": item.get("operacion", "reemplazar"),
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
            if cantidad is not None and unidad != _unidad(producto.unidad):
                piezas = piezas_para_cantidad(producto, cantidad, _unidad(item.get("unidad")))
                if piezas is not None:
                    cantidad, unidad = piezas, producto.unidad
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
