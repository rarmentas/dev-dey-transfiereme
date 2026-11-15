from io import StringIO

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from ambito.models import Comercio
from pedidos.management.commands.sembrar_productos_demo import leer_productos
from pedidos.models import ProductoCatalogo


class DatosProductosDemoTests(SimpleTestCase):
    def test_datasets_sin_nombres_ni_alias_ambiguos(self):
        productos = leer_productos(("abarrotes", "bebidas_botanas", "limpieza_higiene"))
        self.assertEqual(len(productos), 36)
        self.assertTrue(all(p["precio_centavos"] > 0 for p in productos))


class SembrarProductosDemoTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="Tienda de prueba", es_demo=True)

    def test_carga_repetida_conserva_ediciones(self):
        call_command("sembrar_productos_demo", comercio_id=self.comercio.pk, stdout=StringIO())
        self.assertEqual(ProductoCatalogo.objects.filter(comercio=self.comercio).count(), 36)
        producto = ProductoCatalogo.objects.get(comercio=self.comercio, nombre="Tortilla de maíz")
        producto.precio_centavos = 3000
        producto.save(update_fields=["precio_centavos"])

        salida = StringIO()
        call_command("sembrar_productos_demo", comercio_id=self.comercio.pk, stdout=salida)
        self.assertEqual(ProductoCatalogo.objects.filter(comercio=self.comercio).count(), 36)
        producto.refresh_from_db()
        self.assertEqual(producto.precio_centavos, 3000)
        self.assertIn("0 productos creados; 36 existentes", salida.getvalue())

    def test_dataset_seleccionado_y_comercio_ajeno(self):
        call_command("sembrar_productos_demo", comercio_id=self.comercio.pk,
                     dataset=["bebidas_botanas"], stdout=StringIO())
        self.assertEqual(ProductoCatalogo.objects.filter(comercio=self.comercio).count(), 12)

        ajeno = Comercio.objects.create(nombre="Tienda real")
        with self.assertRaises(CommandError):
            call_command("sembrar_productos_demo", comercio_id=ajeno.pk, stdout=StringIO())
        self.assertFalse(ProductoCatalogo.objects.filter(comercio=ajeno).exists())

    @override_settings(DEBUG=False)
    def test_semilla_local_no_se_carga_fuera_de_debug(self):
        local = Comercio.objects.create(nombre="Semilla local", semilla_active_dev=True)
        with self.assertRaises(CommandError):
            call_command("sembrar_productos_demo", comercio_id=local.pk, stdout=StringIO())
