import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from config.modo import validar_configuracion

RAIZ = Path(settings.BASE_DIR).parent
SCRIPTS = (
    "scripts/ci/deploy.sh",
    "scripts/ci/deploy-remoto.sh",
    "scripts/ci-install-env.sh",
    "scripts/ci/preflight-remoto.sh",
    "scripts/ci/test-deploy-seguridad.sh",
)


class DeployArtefactosTests(SimpleTestCase):
    def test_sintaxis_de_scripts(self) -> None:
        for ruta in SCRIPTS:
            with self.subTest(ruta=ruta):
                resultado = subprocess.run(
                    ["bash", "-n", str(RAIZ / ruta)], capture_output=True,
                    check=False,
                )
                self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())

    def test_unit_canal_y_aislamiento(self) -> None:
        unit = (RAIZ / "deploy/cody-canal.service.in").read_text()
        for valor in ("procesar_canal", "Restart=always", ".env.canal"):
            self.assertIn(valor, unit)
        self.assertNotIn("PEY", unit)
        self.assertIn("CODY_ROL=canal", unit)

    def test_compose_solo_postgres(self) -> None:
        compose = (RAIZ / "deploy/compose.yaml").read_text()
        for valor in ("name: codi", "container_name: codi-postgres",
                      '"127.0.0.1:5435:5432"',
                      "/var/lib/codi/postgres:/var/lib/postgresql/data"):
            self.assertIn(valor, compose)
        self.assertNotIn("WAHA", compose)
        self.assertNotIn("  waha:", compose)

    def test_deploy_y_ci_master_con_canal(self) -> None:
        deploy = (RAIZ / SCRIPTS[0]).read_text()
        for valor in ("guardian_alive", "flock -n -x 9", "PROD_DEPLOY_PATH",
                      "StrictHostKeyChecking=yes", "known_hosts.prod",
                      "--exclude '/backend/.env.canal'"):
            self.assertIn(valor, deploy)
        self.assertNotIn("coproc", deploy)
        remoto = (RAIZ / SCRIPTS[1]).read_text()
        orden = ("pg_dump", "migrate --plan", "migrate --noinput",
                 "migrate --check --noinput", "collectstatic --noinput", "stopped=1")
        posiciones = [remoto.index(paso) for paso in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertLess(remoto.index("inicio_canal="),
                        remoto.index("systemctl restart cody-canal.service"))
        self.assertIn('--max-edad 30 --desde "$inicio_canal"', remoto)
        for texto in (deploy, remoto):
            self.assertNotIn("instalar-waha-prod.sh", texto)
            self.assertNotIn("docker compose", texto)
        ci = (RAIZ / ".gitlab-ci.yml").read_text()
        for valor in ("requirements-canal.txt", "pedidos.tests canales.tests",
                      "asistente_pedidos.tests",
                      "makemigrations --check --dry-run", "resource_group: codi-vps",
                      "when: never", "when: manual",
                      "flutter test test/widget_smoke_test.dart test/features/pedidos"):
            self.assertIn(valor, ci)

    def test_instancia_y_api_waha_por_defecto(self) -> None:
        entorno = {**os.environ, "WAHA_INSTANCIA": ""}
        entorno.pop("WAHA_BASE_URL", None)
        resultado = subprocess.run(
            [sys.executable, "-c", "from config.settings import "
             "WAHA_INSTANCIA, WAHA_BASE_URL; print(WAHA_INSTANCIA, WAHA_BASE_URL)"],
            cwd=RAIZ / "backend", env=entorno, capture_output=True, check=False,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        self.assertEqual(resultado.stdout.strip(), b"waha http://127.0.0.1:3004")

    def test_clave_openai_es_respaldo_de_clave_del_agente(self) -> None:
        entorno = {**os.environ, "OPENAI_API_KEY": "clave-falsa-openai"}
        entorno.pop("AGENTE_PEDIDOS_API_KEY", None)
        comando = [sys.executable, "-c",
                   "from config.settings import AGENTE_PEDIDOS_API_KEY; print(AGENTE_PEDIDOS_API_KEY)"]
        resultado = subprocess.run(comando, cwd=RAIZ / "backend", env=entorno,
                                   capture_output=True, check=False)
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        self.assertEqual(resultado.stdout.strip(), b"clave-falsa-openai")
        entorno["AGENTE_PEDIDOS_API_KEY"] = "clave-falsa-especifica"
        resultado = subprocess.run(comando, cwd=RAIZ / "backend", env=entorno,
                                   capture_output=True, check=False)
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        self.assertEqual(resultado.stdout.strip(), b"clave-falsa-especifica")

    def test_helper_master_conserva_entorno_y_exige_llave_v2(self) -> None:
        script = (RAIZ / SCRIPTS[2]).read_text()
        required = script.split("required=(", 1)[1].split(")", 1)[0].split()
        self.assertNotIn("WAHA_IMAGE", required)
        valores = dict.fromkeys(required, "ficticio")
        valores.update(WAHA_INSTANCIA="waha", WAHA_API_KEY="ficticia",
                       WAHA_WEBHOOK_SECRET="ficticio",
                       WAHA_BASE_URL="http://127.0.0.1:3004",
                       NUCLEO_ADAPTADOR="real", PEDIDOS_COBRO_HABILITADO="false")
        with tempfile.TemporaryDirectory() as directorio:
            carpeta = Path(directorio)
            entrada = carpeta / "entrada"
            destino = carpeta / "salida"
            entorno = {
                **os.environ,
                "TMPDIR": directorio,
                "PROD_ENV_FILE": str(entrada),
                "PROD_DEPLOY_HOST": "100.120.112.112",
                "PROD_DEPLOY_USER": "cody",
                "PROD_DEPLOY_PORT": "30022",
                "PROD_DEPLOY_PATH": "/opt/codi/prod",
                "PROD_SSH_PRIVATE_KEY_V2": "UFJJVkFURSBLRVk=",
            }
            entorno.pop("OPENAI_API_KEY", None)

            def ejecutar(datos, env=None):
                entrada.write_text("".join(f"{k}={v}\n" for k, v in datos.items()))
                return subprocess.run(
                    ["bash", str(RAIZ / SCRIPTS[2]), "prod", str(destino)],
                    env=env or entorno, capture_output=True, check=False,
                )

            resultado = ejecutar(valores)
            self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
            self.assertEqual(destino.read_text(), entrada.read_text())
            self.assertEqual(destino.stat().st_mode & 0o777, 0o600)
            con_clave = {**entorno, "OPENAI_API_KEY": "ficticia-openai"}
            resultado = ejecutar(valores, con_clave)
            self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
            self.assertIn("OPENAI_API_KEY=ficticia-openai\n", destino.read_text())
            self.assertNotIn(b"ficticia-openai", resultado.stdout + resultado.stderr)
            resultado = ejecutar({**valores, "OPENAI_API_KEY": "clave-archivo"}, con_clave)
            self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
            self.assertEqual(destino.read_text().count("OPENAI_API_KEY="), 1)
            self.assertIn("OPENAI_API_KEY=clave-archivo", destino.read_text())
            for clave in required:
                with self.subTest(clave=clave):
                    self.assertNotEqual(ejecutar({**valores, clave: ""}).returncode, 0)
            self.assertNotEqual(
                ejecutar({**valores, "DEPLOY_HOST": "ficticio"}).returncode, 0
            )
            for valor in ("", "abc", "2 # comentario"):
                with self.subTest(threads=valor):
                    datos = {**valores, "STT_HABILITADO": "0", "STT_CPU_THREADS": valor}
                    self.assertNotEqual(ejecutar(datos).returncode, 0)
            for valor in ("2", "1_0"):
                self.assertEqual(ejecutar({**valores, "STT_HABILITADO": "0",
                                           "STT_CPU_THREADS": valor}).returncode, 0)
            datos = {**valores, "PEDIDOS_COBRO_HABILITADO": "true"}
            self.assertEqual(ejecutar(datos).returncode, 0)
            vieja = {**entorno, "PROD_SSH_PRIVATE_KEY": entorno[
                "PROD_SSH_PRIVATE_KEY_V2"]}
            vieja.pop("PROD_SSH_PRIVATE_KEY_V2")
            resultado = ejecutar(valores, vieja)
            self.assertNotEqual(resultado.returncode, 0)
            self.assertIn(b"PROD_SSH_PRIVATE_KEY_V2", resultado.stderr)

    @override_settings(DEBUG=False, NUCLEO_ADAPTADOR="real", PEY_ADAPTADOR="produccion",
                       PEDIDOS_COBRO_HABILITADO=True, PEY_API_KEY="clave")
    def test_configuracion_por_rol(self) -> None:
        for rol in ("web", "cobros"):
            with self.subTest(rol=rol), override_settings(CODY_ROL=rol):
                validar_configuracion()
                with override_settings(PEY_API_KEY=""):
                    with self.assertRaises(ImproperlyConfigured):
                        validar_configuracion()
        for rol in ("canal", "stt"):
            with self.subTest(rol=rol), override_settings(CODY_ROL=rol):
                with self.assertRaises(ImproperlyConfigured):
                    validar_configuracion()
                with override_settings(PEY_API_KEY=""):
                    validar_configuracion()
