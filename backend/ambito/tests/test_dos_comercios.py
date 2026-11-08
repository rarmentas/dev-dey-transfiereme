from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from ambito.exceptions import ComercioEnCuerpoError, SinAmbitoError
from ambito.middleware import AmbitoComercioMiddleware
from ambito.models import Comercio, Membresia
from ambito.scope import (
    filtrar_por_comercio,
    obtener_por_id_en_ambito,
    preparar_operacion_cobro,
    rechazar_comercio_en_query,
    requerir_comercio,
)


def _ejecutar_middleware(request):
    def vista_dummy(req):
        return req

    return AmbitoComercioMiddleware(vista_dummy)(request)


class DosComerciosTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.client = APIClient()

        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")

        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        self.usuario_sin_membresia = User.objects.create_user(
            username="sin_membresia",
            password="pass-x",
        )

        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

    def test_middleware_asigna_comercio_por_membresia(self) -> None:
        request_a = self.factory.get("/api/cualquiera/")
        request_a.user = self.usuario_a
        _ejecutar_middleware(request_a)
        self.assertEqual(request_a.comercio, self.comercio_a)

        request_b = self.factory.get("/api/cualquiera/")
        request_b.user = self.usuario_b
        _ejecutar_middleware(request_b)
        self.assertEqual(request_b.comercio, self.comercio_b)

    def test_preparar_operacion_cobro_sin_comercio_en_cuerpo_usa_membresia(self) -> None:
        request = self.factory.post("/api/cobro/")
        request.user = self.usuario_a
        _ejecutar_middleware(request)

        comercio = preparar_operacion_cobro(request, {"monto": "0.01"})
        self.assertEqual(comercio, self.comercio_a)

    def test_rechazar_comercio_en_query_rechaza_comercio_id(self) -> None:
        query = self.factory.get(
            "/api/movimientos/",
            {"comercio_id": self.comercio_b.pk},
        ).GET

        with self.assertRaises(ComercioEnCuerpoError) as ctx:
            rechazar_comercio_en_query(query)
        self.assertIn("comercio_id", str(ctx.exception))

    def test_preparar_operacion_cobro_rechaza_comercio_en_cuerpo(self) -> None:
        request = self.factory.post("/api/cobro/")
        request.user = self.usuario_a
        _ejecutar_middleware(request)

        with self.assertRaises(ComercioEnCuerpoError):
            preparar_operacion_cobro(request, {"monto": "0.01", "comercio": self.comercio_b.pk})

        with self.assertRaises(ComercioEnCuerpoError):
            preparar_operacion_cobro(request, {"comercio_id": self.comercio_b.pk})

    def test_aislamiento_comercio_b_no_obtiene_comercio_a(self) -> None:
        request_b = self.factory.post("/api/cobro/")
        request_b.user = self.usuario_b
        _ejecutar_middleware(request_b)

        comercio = preparar_operacion_cobro(request_b, {"monto": "1.00"})
        self.assertEqual(comercio, self.comercio_b)
        self.assertNotEqual(comercio.pk, self.comercio_a.pk)

    def test_usuario_sin_membresia_lanza_sin_ambito(self) -> None:
        request = self.factory.get("/api/cualquiera/")
        request.user = self.usuario_sin_membresia
        _ejecutar_middleware(request)
        self.assertIsNone(request.comercio)

        with self.assertRaises(SinAmbitoError):
            requerir_comercio(request)

    def test_filtrar_por_comercio_no_incluye_registros_del_otro_comercio(self) -> None:
        qs = Membresia.objects.all()
        solo_a = filtrar_por_comercio(qs, self.comercio_a)
        self.assertEqual(solo_a.count(), 1)
        self.assertEqual(solo_a.get().comercio_id, self.comercio_a.pk)
        self.assertNotIn(
            self.comercio_b.pk,
            solo_a.values_list("comercio_id", flat=True),
        )

    def test_obtener_por_id_en_ambito_no_devuelve_id_del_otro_comercio(self) -> None:
        membresia_b = Membresia.objects.get(usuario=self.usuario_b)
        qs = Membresia.objects.all()

        en_ambito_a = obtener_por_id_en_ambito(qs, self.comercio_a, membresia_b.pk)
        self.assertIsNone(en_ambito_a)

        en_ambito_b = obtener_por_id_en_ambito(qs, self.comercio_b, membresia_b.pk)
        self.assertIsNotNone(en_ambito_b)
        self.assertEqual(en_ambito_b.comercio_id, self.comercio_b.pk)

    def test_anonimo_sin_comercio_y_salud_responde_200(self) -> None:
        request = self.factory.get("/api/salud/")
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        _ejecutar_middleware(request)
        self.assertIsNone(request.comercio)

        response = self.client.get("/api/salud/")
        self.assertEqual(response.status_code, 200)
