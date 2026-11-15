from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta


class EndpointsAnterioresTests(TestCase):
    def test_rutas_anteriores_no_cambian_el_legado(self):
        comercio = Comercio.objects.create(nombre="A", clabe="dato legado")
        cuenta = crear_cuenta(comercio)
        usuario = User.objects.create_user(username="dueño")
        Membresia.objects.create(usuario=usuario, comercio=comercio, es_dueno=True)
        cliente = APIClient()
        cliente.force_login(usuario)
        self.assertEqual(
            cliente.get("/api/cuenta/clabe/").json()["clabe"],
            "*" * 14 + cuenta.clabe[-4:],
        )
        for ruta in ("clabe/", "pey/registro/", "pey/sincronizar/"):
            respuesta = cliente.post(
                "/api/cuenta/" + ruta, {"clabe": "otra"}, format="json"
            )
            self.assertEqual(
                (respuesta.status_code, respuesta.json()["codigo"]),
                (409, "USAR_CUENTAS"),
            )
        comercio.refresh_from_db()
        self.assertEqual(comercio.clabe, "dato legado")
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "registrado")
