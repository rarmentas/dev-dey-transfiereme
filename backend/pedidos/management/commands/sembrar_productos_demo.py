"""Carga manual de catálogos ilustrativos para comercios demo."""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ambito.models import Comercio
from asistente_pedidos.catalogo import normalizar
from pedidos.models import ProductoCatalogo


DATOS = Path(__file__).resolve().parents[2] / "datos_demo"
DATASETS = ("abarrotes", "bebidas_botanas", "limpieza_higiene")
COLUMNAS = ("nombre", "alias", "unidad", "precio_centavos")


def leer_productos(datasets):
    """Valida todos los CSV antes de insertar la primera fila."""
    productos = []
    nombres = set()
    for dataset in datasets:
        ruta = DATOS / f"{dataset}.csv"
        try:
            with ruta.open(encoding="utf-8-sig", newline="") as archivo:
                lector = csv.DictReader(archivo)
                if tuple(lector.fieldnames or ()) != COLUMNAS:
                    raise CommandError(f"Columnas inválidas en {ruta.name}.")
                for numero, fila in enumerate(lector, start=2):
                    if None in fila:
                        raise CommandError(f"Columnas de más en {ruta.name}:{numero}.")
                    if any(valor is None for valor in fila.values()):
                        raise CommandError(f"Columnas incompletas en {ruta.name}:{numero}.")
                    nombre = fila["nombre"].strip()
                    unidad = fila["unidad"].strip()
                    alias = [a.strip() for a in fila["alias"].split("|") if a.strip()]
                    try:
                        precio = int(fila["precio_centavos"])
                    except (TypeError, ValueError):
                        raise CommandError(f"Precio inválido en {ruta.name}:{numero}.") from None
                    nombres_fila = [normalizar(nombre), *(normalizar(a) for a in alias)]
                    if (not nombre or len(nombre) > 200 or not unidad or len(unidad) > 30
                            or precio <= 0 or precio > 9007199254740991
                            or len(alias) > 20 or any(len(a) > 200 for a in alias)
                            or len(set(nombres_fila)) != len(nombres_fila)
                            or any(n in nombres for n in nombres_fila)):
                        raise CommandError(f"Producto inválido o ambiguo en {ruta.name}:{numero}.")
                    nombres.update(nombres_fila)
                    productos.append({
                        "nombre": nombre, "alias": alias, "unidad": unidad,
                        "precio_centavos": precio, "disponible": True,
                    })
        except OSError as exc:
            raise CommandError(f"No se pudo leer {ruta.name}: {exc}") from exc
    return productos


class Command(BaseCommand):
    help = "Carga productos ilustrativos en un comercio demo; conserva productos existentes."

    def add_arguments(self, parser):
        parser.add_argument("--comercio-id", type=int, required=True)
        parser.add_argument(
            "--dataset", action="append", choices=DATASETS,
            help="Puede repetirse; si se omite, carga los tres datasets.",
        )

    def handle(self, *args, **options):
        comercio = Comercio.objects.filter(pk=options["comercio_id"]).first()
        if comercio is None:
            raise CommandError("No existe el comercio indicado.")
        if not (comercio.es_demo or (settings.DEBUG and comercio.semilla_active_dev)):
            raise CommandError("El comercio debe estar designado demo o ser la semilla local de desarrollo.")

        productos = leer_productos(dict.fromkeys(options["dataset"] or DATASETS))
        creados = 0
        with transaction.atomic():
            for producto in productos:
                _, creado = ProductoCatalogo.objects.get_or_create(
                    comercio=comercio, nombre=producto["nombre"], defaults={
                        campo: valor for campo, valor in producto.items() if campo != "nombre"
                    },
                )
                creados += creado

        self.stdout.write(self.style.SUCCESS(
            f"{creados} productos creados; {len(productos) - creados} existentes "
            f"sin cambios en «{comercio.nombre}»."
        ))
