import tempfile
from pathlib import Path

from django.http import Http404
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from config.frontend import aplicacion


class FrontendDistTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.dist = raiz / "web"
        self.dist.mkdir()
        (self.dist / "index.html").write_text(
            "<!doctype html><title>app</title>",
            encoding="utf-8",
        )
        (self.dist / "flutter_bootstrap.js").write_text("console.log(1)\n", encoding="utf-8")
        assets = self.dist / "assets"
        assets.mkdir()
        (assets / "FontManifest.json").write_text("[]", encoding="utf-8")
        (raiz / "secreto.txt").write_text("no", encoding="utf-8")
        self.client = Client()

    def test_la_raiz_entrega_index(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/html", respuesta["Content-Type"])
        self.assertContains(respuesta, "<title>app</title>")
        self.assertEqual(respuesta["Cache-Control"], "no-cache")

    def test_la_ruta_de_cliente_entrega_index(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            respuesta = self.client.get("/entrar")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "<title>app</title>")

    def test_la_barra_final_vuelve_a_la_ruta_de_cliente(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            respuesta = self.client.get("/entrar/?siguiente=1")
        self.assertRedirects(
            respuesta,
            "/entrar?siguiente=1",
            fetch_redirect_response=False,
        )

    def test_un_archivo_del_build_se_entrega_tal_cual(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            js = self.client.get("/flutter_bootstrap.js")
            manifiesto = self.client.get("/assets/FontManifest.json")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js["Content-Type"])
        self.assertEqual(b"".join(js.streaming_content), b"console.log(1)\n")
        self.assertEqual(manifiesto.status_code, 200)
        self.assertIn("json", manifiesto["Content-Type"])
        self.assertEqual(b"".join(manifiesto.streaming_content), b"[]")

    def test_un_archivo_que_no_esta_no_devuelve_html(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            respuesta = self.client.get("/main.dart.js")
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn(b"<title>app</title>", respuesta.content)

    def test_head_en_la_raiz(self) -> None:
        with override_settings(FRONTEND_DIST=self.dist):
            respuesta = self.client.head("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/html", respuesta["Content-Type"])

    def test_sin_build_la_raiz_sigue_en_404(self) -> None:
        vacio = Path(self.tmp.name) / "vacio"
        vacio.mkdir()
        with override_settings(FRONTEND_DIST=vacio):
            raiz = self.client.get("/")
            con_barra = self.client.get("/entrar/")
        self.assertEqual(raiz.status_code, 404)
        self.assertEqual(con_barra.status_code, 404)

    def test_no_sirve_un_archivo_fuera_del_build(self) -> None:
        request = RequestFactory().get("/secreto.txt")
        with override_settings(FRONTEND_DIST=self.dist):
            with self.assertRaises(Http404):
                aplicacion(request, "../secreto.txt")

    def test_la_api_no_cae_en_la_aplicacion(self) -> None:
        self.assertEqual(resolve("/api/salud/").url_name, "salud")
        self.assertEqual(resolve("/").url_name, "aplicacion")
        self.assertEqual(resolve("/entrar").url_name, "aplicacion")


class LandingEnRaizTests(SimpleTestCase):
    """La landing va en / y la app de Flutter en sus rutas."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.app = raiz / "web"
        self.app.mkdir()
        (self.app / "index.html").write_text("<title>app</title>", encoding="utf-8")
        (self.app / "main.dart.js").write_text("app()", encoding="utf-8")
        self.landing = raiz / "landing"
        (self.landing / "_astro").mkdir(parents=True)
        (self.landing / "index.html").write_text("<title>landing</title>", encoding="utf-8")
        (self.landing / "_astro" / "sitio.css").write_text("body{}", encoding="utf-8")
        (self.landing / "main.dart.js").write_text("landing()", encoding="utf-8")
        self.client = Client()

    def _get(self, ruta: str):
        with override_settings(FRONTEND_DIST=self.app, LANDING_DIST=self.landing):
            return self.client.get(ruta)

    def test_la_raiz_entrega_la_landing(self) -> None:
        respuesta = self._get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/html", respuesta["Content-Type"])
        self.assertContains(respuesta, "<title>landing</title>")

    def test_las_rutas_de_la_app_siguen_en_flutter(self) -> None:
        for ruta in ("/entrar", "/inicio", "/venta/nueva"):
            with self.subTest(ruta=ruta):
                self.assertContains(self._get(ruta), "<title>app</title>")

    def test_los_archivos_de_la_landing_se_entregan(self) -> None:
        respuesta = self._get("/_astro/sitio.css")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(b"".join(respuesta.streaming_content), b"body{}")

    def test_un_archivo_de_flutter_gana_al_de_la_landing(self) -> None:
        respuesta = self._get("/main.dart.js")
        self.assertEqual(b"".join(respuesta.streaming_content), b"app()")

    def test_un_archivo_que_no_esta_en_ninguno_es_404(self) -> None:
        self.assertEqual(self._get("/_astro/no-existe.js").status_code, 404)

    def test_no_sale_de_la_landing(self) -> None:
        self.assertEqual(self._get("/../secreto.txt").status_code, 404)

    def test_sin_landing_la_raiz_es_la_app(self) -> None:
        with override_settings(FRONTEND_DIST=self.app, LANDING_DIST=Path(self.tmp.name) / "nada"):
            respuesta = self.client.get("/")
        self.assertContains(respuesta, "<title>app</title>")
