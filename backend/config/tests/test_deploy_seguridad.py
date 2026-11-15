import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR).parent


class DeploySeguridadTests(SimpleTestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.codi = self.raiz / "codi"
        self.destino = self.codi / "prod"
        for carpeta in (
            "backend/.venv/bin",
            "scripts/ci",
            "deploy",
            "frontend",
            "landing",
        ):
            (self.destino / carpeta).mkdir(parents=True, exist_ok=True)
        for nombre in ("deploy-guard.sh", "deploy-remoto.sh"):
            contenido = (RAIZ / "scripts/ci" / nombre).read_text()
            contenido = contenido.replace("/opt/codi", str(self.codi))
            (self.destino / "scripts/ci" / nombre).write_text(contenido)
        for nombre in ("cody.service.in", "cody-canal.service.in"):
            shutil.copy(RAIZ / "deploy" / nombre, self.destino / "deploy" / nombre)
        (self.destino / "backend/.env.incoming").write_text("POSTGRES_PORT=5435\n")
        self.bin = self.raiz / "bin"
        self.bin.mkdir()
        self.log = self.raiz / "log"
        self.entorno = os.environ.copy()
        self.entorno.update(
            PATH=f"{self.bin}:{os.environ['PATH']}",
            HOME=str(self.raiz),
            LOG=str(self.log),
            UNITS=str(self.raiz / "units"),
        )
        self.stub(
            "docker",
            """echo "docker $*" >> "$LOG"
case "$*" in
  *State.Running*) echo "${IDENTIDAD:-true codi postgres}" ;;
  *) echo "127.0.0.1:5435" ;;
esac""",
        )
        self.stub("sudo", 'shift; "$@"')
        self.stub("systemctl", 'echo "systemctl $*" >> "$LOG"; exit 0')
        self.stub(
            "install",
            """echo "install $*" >> "$LOG"
if [[ "$4" == /etc/systemd/system/* ]]; then
  mkdir -p "$UNITS"; cp "$3" "$UNITS/$(basename "$4")"
else
  cp "$3" "$4"
fi""",
        )
        python = self.destino / "backend/.venv/bin/python"
        python.write_text("""#!/bin/bash
if [[ "$1" == - ]]; then exit "${DB_ERROR:-0}"; fi
if [[ "$1" == -c ]]; then
  case "$2" in
    *urllib.request*) echo 200 ;;
    *datetime*) echo 2026-01-01T00:00:00Z ;;
  esac
fi
exit 0
""")
        python.chmod(0o755)
        pip = python.parent / "pip"
        pip.write_text("#!/bin/sh\nexit 0\n")
        pip.chmod(0o755)

    def stub(self, nombre: str, cuerpo: str) -> None:
        archivo = self.bin / nombre
        archivo.write_text(f"#!/bin/bash\n{cuerpo}\n")
        archivo.chmod(0o755)

    def guard(self, scope: str, ruta: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "bash",
                str(self.destino / "scripts/ci/deploy-guard.sh"),
                "check",
                scope,
                str(ruta),
            ],
            env=self.entorno,
            capture_output=True,
            check=False,
        )

    def remoto(self, **variables: str) -> subprocess.CompletedProcess:
        entorno = {**self.entorno, **variables}
        guard = subprocess.Popen(
            [
                "bash",
                str(self.destino / "scripts/ci/deploy-guard.sh"),
                "lock",
                "prod",
                str(self.destino),
            ],
            env=entorno,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            token = guard.stdout.readline().strip().split()[1]
            return subprocess.run(
                [
                    "bash",
                    str(self.destino / "scripts/ci/deploy-remoto.sh"),
                    "prod",
                    str(self.destino),
                    "/bin/true",
                    "cody",
                    "localhost",
                    "8000",
                    "cody",
                    token,
                ],
                env=entorno,
                capture_output=True,
                check=False,
            )
        finally:
            guard.communicate(input="fin\n", timeout=5)

    def test_rechaza_destinos_scope_y_symlink(self) -> None:
        hermano = self.codi / "waha-prod"
        hermano.mkdir()
        centinela = hermano / "centinela"
        centinela.write_text("intacto")
        for scope, ruta in (
            ("prod", self.codi),
            ("prod", hermano),
            ("test", self.destino),
            ("prod", self.codi / "test"),
        ):
            self.assertNotEqual(self.guard(scope, ruta).returncode, 0)
        shutil.rmtree(self.destino / "frontend")
        (self.destino / "frontend").symlink_to(hermano, target_is_directory=True)
        self.assertNotEqual(self.guard("prod", self.destino).returncode, 0)
        self.assertEqual(centinela.read_text(), "intacto")
        self.assertFalse(self.log.exists())

    def test_candado_y_mantenimiento(self) -> None:
        comando = [
            "bash",
            str(self.destino / "scripts/ci/deploy-guard.sh"),
            "lock",
            "prod",
            str(self.destino),
        ]
        proceso = subprocess.Popen(
            comando,
            env=self.entorno,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertTrue(proceso.stdout.readline().startswith("READY "))
            self.assertNotEqual(
                subprocess.run(
                    comando, env=self.entorno, capture_output=True, check=False
                ).returncode,
                0,
            )
        finally:
            proceso.communicate(input="fin\n", timeout=5)
        (self.codi / ".maintenance").touch()
        self.assertNotEqual(
            subprocess.run(
                comando, env=self.entorno, capture_output=True, check=False
            ).returncode,
            0,
        )

    def test_remoto_directo_sin_candado_se_rechaza(self) -> None:
        resultado = subprocess.run(
            [
                "bash",
                str(self.destino / "scripts/ci/deploy-remoto.sh"),
                "prod",
                str(self.destino),
                "/bin/true",
                "cody",
                "localhost",
                "8000",
                "cody",
            ],
            env=self.entorno,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(resultado.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_bd_fallida_no_para_ni_modifica_contenedores(self) -> None:
        for variables in ({"IDENTIDAD": "false codi postgres"}, {"DB_ERROR": "1"}):
            with self.subTest(variables=variables):
                self.assertNotEqual(self.remoto(**variables).returncode, 0)
                acciones = self.log.read_text()
                self.assertNotIn("systemctl", acciones)
                self.assertNotIn("docker up", acciones)
                self.assertTrue((self.destino / "backend/.env.incoming").exists())

    def test_deploy_correcto_renderiza_units_sin_mutar_docker(self) -> None:
        resultado = self.remoto()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        self.assertIn("systemctl restart cody-canal", acciones)
        self.assertTrue(
            all(
                "docker inspect" in x
                for x in acciones.splitlines()
                if x.startswith("docker")
            )
        )
        for nombre in ("cody.service", "cody-canal.service"):
            unit = (self.raiz / "units" / nombre).read_text()
            self.assertIn(f"WorkingDirectory={self.destino}/backend", unit)
            self.assertIn(f"ReadWritePaths={self.destino}", unit)
            self.assertNotIn("@DEPLOY", unit)
        canal = (self.raiz / "units/cody-canal.service").read_text()
        self.assertIn(f"EnvironmentFile={self.destino}/backend/.env.canal", canal)
        self.assertIn(f"ExecStart={self.destino}/backend/.venv/bin/python", canal)

    def test_transferencias_bajo_candado_con_ssh_y_rsync_simulados(self) -> None:
        checkout = self.raiz / "checkout"
        (checkout / "scripts/ci").mkdir(parents=True)
        (checkout / "backend").mkdir()
        (checkout / "frontend/build/web").mkdir(parents=True)
        (checkout / "landing/dist").mkdir(parents=True)
        (checkout / "landing/dist/index.html").touch()
        for nombre in ("deploy.sh", "deploy-guard.sh"):
            texto = (RAIZ / "scripts/ci" / nombre).read_text()
            (checkout / "scripts/ci" / nombre).write_text(
                texto.replace("/opt/codi", str(self.codi))
            )
        texto = (RAIZ / "scripts/ci-install-env.sh").read_text()
        (checkout / "scripts/ci-install-env.sh").write_text(
            texto.replace("/opt/codi", str(self.codi))
        )
        env_file = self.raiz / "entrada"
        claves = (
            "POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT "
            "DJANGO_SECRET_KEY DEBUG ALLOWED_HOSTS WEBHOOK_BASE_URL PEY_API_KEY "
            "PEY_WEBHOOK_SECRET DEMO_MODE NUCLEO_ADAPTADOR POLITICA_COBRO_VERSION "
            "PEDIDOS_COBRO_HABILITADO WAHA_INSTANCIA WAHA_BASE_URL WAHA_API_KEY "
            "WAHA_WEBHOOK_SECRET"
        ).split()
        valores = dict.fromkeys(claves, "x")
        valores.update(
            DEBUG="False",
            ALLOWED_HOSTS="localhost",
            DEMO_MODE="false",
            NUCLEO_ADAPTADOR="real",
            PEDIDOS_COBRO_HABILITADO="false",
        )
        env_file.write_text("".join(f"{k}={v}\n" for k, v in valores.items()))
        self.entorno.update(
            PROD_ENV_FILE=str(env_file),
            PROD_PYTHON="/bin/true",
            PROD_DEPLOY_HOST="x",
            PROD_DEPLOY_USER="cody",
            PROD_DEPLOY_PORT="22",
            PROD_DEPLOY_PATH=str(self.destino),
            PROD_SSH_PRIVATE_KEY="UFJJVkFURSBLRVk=",
            LOCK=str(self.codi / ".deploy.lock"),
        )
        self.stub("ssh-keyscan", 'echo "host key"')
        self.stub(
            "ssh",
            """while [[ "$1" == -* ]]; do shift 2; done
shift
if [[ $# == 1 ]]; then exec bash -c "$1"; fi
exec "$@"
""",
        )
        self.stub(
            "rsync",
            """echo rsync >> "$LOG"
if flock -n "$LOCK" true; then exit 1; fi
exit 0""",
        )
        self.stub(
            "scp",
            """echo scp >> "$LOG"
if flock -n "$LOCK" true; then exit 1; fi
while [[ "$1" == -* ]]; do shift 2; done
cp "$1" "${2#*:}"
""",
        )
        resultado = subprocess.run(
            ["bash", str(checkout / "scripts/ci/deploy.sh"), "prod"],
            env=self.entorno,
            capture_output=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        self.assertLess(acciones.index("rsync"), acciones.index("scp"))
        self.assertLess(acciones.index("scp"), acciones.index("systemctl restart cody"))
        self.assertEqual(
            subprocess.run(
                ["flock", "-n", str(self.codi / ".deploy.lock"), "true"], check=False
            ).returncode,
            0,
        )
