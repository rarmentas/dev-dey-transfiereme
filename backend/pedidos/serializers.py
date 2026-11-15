"""Validación estricta de cuerpos de la API del tendero."""

from uuid import UUID

from pedidos.contratos.v1 import CodigoError
from pedidos.contratos.validacion import ErrorContrato, validar_cantidad
from pedidos.errores import ErrorNucleo


def _fallo(detalle, errores=None):
    exc = ErrorNucleo(CodigoError.PAYLOAD_INVALIDO, detalle)
    exc.errores = errores
    raise exc


def validar_cuerpo(datos, revision=False):
    if not isinstance(datos, dict):
        _fallo("El cuerpo debe ser un objeto JSON.")
    if datos.get("contrato_version", "1.0") != "1.0":
        raise ErrorNucleo(CodigoError.VERSION_CONTRATO_NO_SOPORTADA)
    obligatorios = {"command_key", "expected_version"}
    if revision:
        obligatorios.add("renglones")
    if not obligatorios <= datos.keys() or datos.keys() - obligatorios - {
        "contrato_version"
    }:
        _fallo("Campos faltantes o desconocidos.")
    clave = datos["command_key"]
    if not isinstance(clave, str) or not clave.strip() or len(clave) > 128:
        _fallo("Clave inválida.", {"command_key": ["Clave inválida."]})
    if type(datos["expected_version"]) is not int or datos["expected_version"] < 1:
        _fallo("Versión inválida.", {"expected_version": ["Versión inválida."]})
    limpio = dict(datos)
    if not revision:
        return limpio
    filas = datos["renglones"]
    if not isinstance(filas, list) or len(filas) > 100:
        _fallo("Renglones inválidos.", {"renglones": ["Lista inválida."]})
    campos = {
        "renglon_id",
        "descripcion",
        "cantidad",
        "unidad",
        "precio_unitario_centavos",
        "resolucion",
        "motivo_exclusion",
    }
    errores = {}
    limpio["renglones"] = []
    for i, fila in enumerate(filas):

        def error(campo, mensaje, indice=i):
            errores[f"renglones.{indice}.{campo}"] = [mensaje]

        if not isinstance(fila, dict) or set(fila) - campos:
            error("campos", "Campos inválidos.")
            continue
        try:
            identidad = str(UUID(fila.get("renglon_id", "")))
        except (TypeError, ValueError, AttributeError):
            error("renglon_id", "ID inválido.")
            continue
        resolucion = fila.get("resolucion")
        if resolucion not in ("pendiente", "incluido", "excluido"):
            error("resolucion", "Resolución inválida.")
        normal = {"renglon_id": identidad, "resolucion": resolucion}
        for campo, limite in (
            ("descripcion", 200),
            ("unidad", 30),
            ("motivo_exclusion", 200),
        ):
            valor = fila.get(campo, "")
            if not isinstance(valor, str) or len(valor) > limite:
                error(campo, "Texto inválido.")
                valor = ""
            normal[campo] = valor
        cantidad = fila.get("cantidad")
        if cantidad is not None:
            try:
                if not isinstance(cantidad, str):
                    raise ValueError
                validar_cantidad(cantidad)
            except (ErrorContrato, ValueError):
                error("cantidad", "Cantidad inválida.")
        normal["cantidad"] = cantidad
        precio = fila.get("precio_unitario_centavos")
        if precio is not None and (
            type(precio) is not int or precio <= 0 or precio > 9223372036854775807
        ):
            error("precio_unitario_centavos", "Precio inválido.")
        normal["precio_unitario_centavos"] = precio
        if resolucion == "incluido":
            if not normal["descripcion"].strip():
                error("descripcion", "La descripción es requerida.")
            if cantidad is None:
                error("cantidad", "La cantidad es requerida.")
            if precio is None:
                error("precio_unitario_centavos", "El precio es requerido.")
        if resolucion == "excluido" and not normal["motivo_exclusion"].strip():
            error("motivo_exclusion", "El motivo es requerido.")
        limpio["renglones"].append(normal)
    if errores:
        _fallo("Renglones inválidos.", errores)
    return limpio
