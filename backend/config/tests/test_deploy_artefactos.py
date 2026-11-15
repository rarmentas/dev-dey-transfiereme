import os
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR).parent
SCRIPTS = (
    "scripts/ci/deploy.sh",
    "scripts/ci/deploy-remoto.sh",
    "scripts/ci-install-env.sh",
    "scripts/ci/deploy-guard.sh",
)


class DeployArtefactosTests(SimpleTestCase):
    def test_sintaxis_de_scripts(self) -> None:
        for ruta in SCRIPTS:
            with self.subTest(ruta=ruta):
                resultado = subprocess.run(
                    ["bash", "-n", str(RAIZ / ruta)],
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    resultado.returncode, 0, resultado.stderr.decode()
                )

    def test_unit_canal_y_aislamiento(self) -> None:
        unit = (RAIZ / "deploy/cody-canal.service.in").read_text()
        for valor in ("procesar_canal", "Restart=always", ".env.canal"):
            self.assertIn(valor, unit)
        self.assertNotIn("PEY", unit)
        remoto = (RAIZ / SCRIPTS[1]).read_text()
        for clave in ("PEY_API_KEY", "PEY_WEBHOOK_SECRET", "WAHA_WEBHOOK_SECRET"):
            filtro = remoto.split("# Solo las variables", 1)[1].split("chmod 600", 1)[0]
            self.assertNotIn(clave, filtro)
        self.assertIn('chmod 600 "$canal_env"', remoto)

    def test_compose_solo_postgres(self) -> None:
        compose = (RAIZ / "deploy/compose.yaml").read_text()
        self.assertIn("name: codi", compose)
        self.assertIn("container_name: codi-postgres", compose)
        self.assertIn('"127.0.0.1:5435:5432"', compose)
        self.assertIn("/var/lib/codi/postgres:/var/lib/postgresql/data", compose)
        self.assertNotIn("WAHA", compose)
        self.assertNotIn("  waha:", compose)

    def test_deploy_y_ci_incluyen_canal(self) -> None:
        deploy = (RAIZ / SCRIPTS[0]).read_text()
        self.assertIn("--exclude '.plan/'", deploy)
        self.assertIn("--exclude 'backend/.env.canal'", deploy)
        remoto = (RAIZ / SCRIPTS[1]).read_text()
        self.assertLess(
            remoto.index('"${unit_base}-canal" "$unit_base"'),
            remoto.index("manage.py migrate"),
        )
        self.assertLess(
            remoto.index("manage.py migrate"),
            remoto.index('systemctl restart "${unit_base}-canal"'),
        )
        self.assertLess(
            remoto.index("inicio_canal="),
            remoto.index('systemctl restart "${unit_base}-canal"'),
        )
        self.assertIn('--max-edad 30 --desde "$inicio_canal"', remoto)
        ci = (RAIZ / ".gitlab-ci.yml").read_text()
        self.assertIn("pedidos.tests canales.tests", ci)
        self.assertIn("makemigrations --check --dry-run", ci)
        self.assertIn(
            "flutter test test/widget_smoke_test.dart test/features/pedidos", ci
        )

    def test_arranque_fallido_no_acepta_latido_anterior(self) -> None:
        remoto = (RAIZ / SCRIPTS[1]).read_text()
        bloque = remoto[remoto.index("inicio_canal=") :]
        with tempfile.TemporaryDirectory() as directorio:
            backend = Path(directorio) / "backend"
            python = backend / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = -c ]; then echo 2026-01-01T00:00:00Z; exit 0; fi\n'
                'case " $* " in *" --desde 2026-01-01T00:00:00Z "*) '
                'exit "$LATIDO_ANTERIOR";; *) exit 2;; esac\n'
            )
            python.chmod(0o755)
            script = (
                'dest="$1"; unit_base=cody\n'
                'as_root() { if [[ "$2" == is-active ]]; then '
                'return "$UNIT_INACTIVA"; fi; return 0; }\n'
                "sleep() { :; }\n" + bloque
            )
            for latido, inactiva, esperado in (
                (1, 1, 1),
                (1, 0, 1),
                (0, 1, 1),
                (0, 0, 0),
            ):
                with self.subTest(latido=latido, inactiva=inactiva):
                    entorno = os.environ.copy()
                    entorno.update(
                        LATIDO_ANTERIOR=str(latido), UNIT_INACTIVA=str(inactiva)
                    )
                    resultado = subprocess.run(
                        ["bash", "-c", script, "prueba", directorio],
                        env=entorno,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(resultado.returncode, esperado)

    def test_instancia_waha_obligatoria(self) -> None:
        script = (RAIZ / SCRIPTS[2]).read_text()
        bloque = script.split("required=(", 1)[1].split(")", 1)[0]
        self.assertIn("WAHA_INSTANCIA", bloque.split())

    def test_validacion_de_entorno_y_casos_vacios(self) -> None:
        valores = {
            clave: "x"
            for clave in (
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
                "POSTGRES_HOST",
                "POSTGRES_PORT",
                "DJANGO_SECRET_KEY",
                "DEBUG",
                "ALLOWED_HOSTS",
                "WEBHOOK_BASE_URL",
                "PEY_API_KEY",
                "PEY_WEBHOOK_SECRET",
                "POLITICA_COBRO_VERSION",
                "WAHA_INSTANCIA",
                "WAHA_BASE_URL",
                "WAHA_API_KEY",
                "WAHA_WEBHOOK_SECRET",
            )
        }
        valores.update(
            DEMO_MODE="false", NUCLEO_ADAPTADOR="real", PEDIDOS_COBRO_HABILITADO="false"
        )
        with tempfile.TemporaryDirectory() as directorio:
            archivo = Path(directorio) / "entrada"
            destino = Path(directorio) / "salida"
            entorno = os.environ.copy()
            entorno.update(
                TEST_ENV_FILE=str(archivo),
                TEST_DEPLOY_HOST="x",
                TEST_DEPLOY_USER="x",
                TEST_DEPLOY_PATH="/opt/codi/test",
                TEST_DEPLOY_PORT="22",
                TEST_SSH_PRIVATE_KEY="UFJJVkFURSBLRVk=",
            )

            def ejecutar(datos: dict[str, str]) -> subprocess.CompletedProcess:
                archivo.write_text("".join(f"{k}={v}\n" for k, v in datos.items()))
                return subprocess.run(
                    ["bash", str(RAIZ / SCRIPTS[2]), "test", str(destino)],
                    env=entorno,
                    capture_output=True,
                    check=False,
                )

            self.assertEqual(ejecutar(valores).returncode, 0)
            sin_instancia = {k: v for k, v in valores.items() if k != "WAHA_INSTANCIA"}
            self.assertNotEqual(ejecutar(sin_instancia).returncode, 0)
            for clave in valores:
                with self.subTest(clave=clave):
                    self.assertNotEqual(ejecutar({**valores, clave: ""}).returncode, 0)
            with archivo.open("w") as salida:
                salida.write("".join(f"{k}={v}\n" for k, v in valores.items()))
                salida.write("WAHA_API_KEY=\n")
            duplicado = subprocess.run(
                ["bash", str(RAIZ / SCRIPTS[2]), "test", str(destino)],
                env=entorno,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(duplicado.returncode, 0)
            for clave, valor in (
                ("DEMO_MODE", "otro"),
                ("NUCLEO_ADAPTADOR", "stub"),
                ("PEDIDOS_COBRO_HABILITADO", "true"),
            ):
                with self.subTest(clave=clave, valor=valor):
                    self.assertNotEqual(
                        ejecutar({**valores, clave: valor}).returncode, 0
                    )
            self.assertNotEqual(
                ejecutar({**valores, "DEMO_MODE": "true"}).returncode, 0
            )
            self.assertEqual(
                ejecutar(
                    {**valores, "DEMO_MODE": "true", "DEMO_PEY_BANK_ACCOUNT_ID": "x"}
                ).returncode,
                0,
            )

            archivo.write_text("".join(f"{k}={v}\n" for k, v in valores.items()))
            entorno.update(
                PROD_ENV_FILE=str(archivo), PROD_DEPLOY_HOST="x", PROD_DEPLOY_USER="x",
                PROD_DEPLOY_PORT="22", PROD_SSH_PRIVATE_KEY="UFJJVkFURSBLRVk=",
            )
            for ruta in ("/opt/codi", "/opt/codi/test", "/opt/codi/waha-prod",
                         "/opt/codi/prod/", "/opt/codi/prod"):
                entorno["PROD_DEPLOY_PATH"] = ruta
                resultado = subprocess.run(
                    ["bash", str(RAIZ / SCRIPTS[2]), "prod", str(destino)],
                    env=entorno, capture_output=True, check=False,
                )
                self.assertEqual(resultado.returncode == 0, ruta == "/opt/codi/prod")
