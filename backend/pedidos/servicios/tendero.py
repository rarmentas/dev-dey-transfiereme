"""Operaciones del tendero sobre pedidos."""

from django.db import transaction

from ambito.candados import bloquear_comercio
from pedidos.contratos.v1 import CodigoError
from pedidos.contratos.validacion import hash_canonico
from pedidos.errores import ErrorNucleo
from pedidos.models import Pedido
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.cotizaciones import invalidar, publicar
from pedidos.servicios.intentos import exigir_editable


def operar(comercio, pedido_id, operacion, datos, usuario=None):
    huella = hash_canonico(
        operacion, {**datos, "pedido_id": str(pedido_id)}, str(comercio.pk)
    )
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = (
            Pedido.objects.select_for_update()
            .filter(comercio=comercio, pk=pedido_id)
            .first()
        )
        if not pedido:
            raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(
                CodigoError.VERSION_OBSOLETA,
                pedido_id=str(pedido.id),
                pedido_version=pedido.version,
            )
        if pedido.estado == "cerrado":
            raise ErrorNucleo(CodigoError.PEDIDO_CONGELADO)
        exigir_editable(comercio, pedido)
        if operacion == "revisar_renglones":
            existentes = {str(r.id): r for r in pedido.renglones.all()}
            recibidos = datos["renglones"]
            ids = [r["renglon_id"] for r in recibidos]
            if len(ids) != len(set(ids)) or set(ids) != set(existentes):
                raise ErrorNucleo(
                    CodigoError.PAYLOAD_INVALIDO, "Los renglones no coinciden."
                )
            pedido.version += 1
            invalidar(comercio, pedido)
            for item in recibidos:
                renglon = existentes[item["renglon_id"]]
                for campo in (
                    "descripcion",
                    "cantidad",
                    "unidad",
                    "precio_unitario_centavos",
                    "resolucion",
                    "motivo_exclusion",
                ):
                    setattr(
                        renglon,
                        campo,
                        item.get(
                            campo,
                            None
                            if campo in ("cantidad", "precio_unitario_centavos")
                            else "",
                        ),
                    )
                renglon.producto_catalogo = None
                renglon.save()
            pedido.estado = "en_revision"
            pedido.save()
        else:
            publicar(comercio, pedido, usuario)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)
