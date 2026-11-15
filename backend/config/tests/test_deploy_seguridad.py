import os
import shutil
import subprocess
import tempfile
import time
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
        pip.write_text("""#!/bin/bash
echo "pip $*" >> "$LOG"
if [[ -n "${ESPERA:-}" ]]; then
  touch "$ESPERA.dentro"
  while [[ ! -e "$ESPERA" ]]; do sleep 0.05; done
fi
exit "${PIP_ERROR:-0}"
""")
        pip.chmod(0o755)
        self.lock = self.codi / ".deploy.lock"
        self.entorno["LOCK"] = str(self.lock)
        # Simula el receptor remoto: ejecuta --rsync-path como lo haría el VPS.
        self.stub(
            "rsync",
            """if [[ "$1" == --server ]]; then
  echo "rsync servidor" >> "$LOG"
  if [[ -n "${ESPERA:-}" ]]; then
    touch "$ESPERA.dentro"
    while [[ ! -e "$ESPERA" ]]; do sleep 0.05; done
  fi
  if flock -n "$LOCK" true; then exit 1; fi
  exit 0
fi
echo rsync >> "$LOG"
while [[ $# -gt 0 && "$1" != --rsync-path ]]; do shift; done
eval "$2 --server ."
""",
        )

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

    def bloquear(self) -> tuple[subprocess.Popen, str]:
        guard = subprocess.Popen(
            [
                "bash",
                str(self.destino / "scripts/ci/deploy-guard.sh"),
                "lock",
                "prod",
                str(self.destino),
            ],
            env=self.entorno,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        linea = guard.stdout.readline().strip().split()
        if linea[:1] != ["READY"]:
            guard.communicate(input="fin\n", timeout=5)
            self.fail(f"el guard no tomó el candado: {linea}")
        return guard, linea[1]

    def comando_remoto(self, token: str) -> list[str]:
        return [
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
        ]

    def remoto(self, **variables: str) -> subprocess.CompletedProcess:
        guard, token = self.bloquear()
        try:
            return subprocess.run(
                self.comando_remoto(token),
                env={**self.entorno, **variables},
                capture_output=True,
                check=False,
            )
        finally:
            guard.communicate(input="fin\n", timeout=5)

    def esperar(self, archivo: Path, proceso: subprocess.Popen) -> None:
        limite = time.monotonic() + 15
        while not archivo.exists():
            self.assertIsNone(proceso.poll(), "la operación terminó antes de tiempo")
            self.assertLess(time.monotonic(), limite, f"no apareció {archivo}")
            time.sleep(0.05)

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

    def test_pip_fallido_no_para_servicios_ni_reemplaza_env(self) -> None:
        activo = self.destino / "backend/.env"
        activo.write_text("ANTERIOR=1\n")
        self.assertNotEqual(self.remoto(PIP_ERROR="1").returncode, 0)
        acciones = self.log.read_text()
        self.assertIn("pip install", acciones)
        self.assertNotIn("systemctl stop", acciones)
        self.assertEqual(activo.read_text(), "ANTERIOR=1\n")
        self.assertEqual(
            (self.destino / "backend/.env.incoming").read_text(),
            "POSTGRES_PORT=5435\n",
        )

    def test_operacion_activa_retiene_candado_sin_guard(self) -> None:
        guard_sh = str(self.destino / "scripts/ci/deploy-guard.sh")
        espera = self.raiz / "soltar"
        dentro = self.raiz / "soltar.dentro"
        entrante = self.destino / "backend/.env.incoming"
        entorno = {**self.entorno, "ESPERA": str(espera)}

        def iniciar(modo: str, token: str) -> subprocess.Popen:
            if modo == "remoto":
                comando = self.comando_remoto(token)
            else:
                comando = ["bash", guard_sh, modo, "prod", str(self.destino), token]
                if modo == "rsync":
                    comando += ["--server", "."]
            return subprocess.Popen(
                comando,
                env=entorno,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

        for modo in ("rsync", "env", "remoto"):
            with self.subTest(modo=modo):
                espera.unlink(missing_ok=True)
                dentro.unlink(missing_ok=True)
                if modo == "env":
                    entrante.unlink(missing_ok=True)
                else:
                    entrante.write_text("POSTGRES_PORT=5435\n")
                marca = entrante if modo == "env" else dentro
                guard, token = self.bloquear()
                operacion = iniciar(modo, token)
                try:
                    self.esperar(marca, operacion)
                    # Termina solo la conexión del guard.
                    guard.communicate(input="fin\n", timeout=5)
                    segundo = subprocess.run(
                        ["bash", guard_sh, "lock", "prod", str(self.destino)],
                        env=self.entorno,
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )
                    self.assertNotEqual(segundo.returncode, 0)
                    self.assertIn(b"Ya hay un deploy en curso", segundo.stderr)
                    mantenimiento = subprocess.run(
                        ["flock", "-n", "-x", str(self.lock), "true"], check=False
                    )
                    self.assertNotEqual(mantenimiento.returncode, 0)
                finally:
                    espera.touch()
                    _, error = operacion.communicate(input=b"NUEVO=1\n", timeout=20)
                    if guard.poll() is None:
                        guard.communicate(input="fin\n", timeout=5)
                self.assertEqual(operacion.returncode, 0, error.decode())
                if modo == "env":
                    self.assertEqual(entrante.read_text(), "NUEVO=1\n")

                # Otro deploy toma el candado; el token anterior queda rechazado.
                espera.unlink()
                dentro.unlink(missing_ok=True)
                entrante.write_text("POSTGRES_PORT=5435\n")
                nuevo, token_nuevo = self.bloquear()
                try:
                    self.assertNotEqual(token_nuevo, token)
                    viejo = iniciar(modo, token)
                    _, error = viejo.communicate(input=b"VIEJO=1\n", timeout=20)
                    self.assertNotEqual(viejo.returncode, 0)
                    self.assertIn(b"Falta la protecci", error)
                    self.assertFalse(dentro.exists())
                    self.assertEqual(entrante.read_text(), "POSTGRES_PORT=5435\n")
                finally:
                    nuevo.communicate(input="fin\n", timeout=5)

    def test_deploy_correcto_renderiza_units_sin_mutar_docker(self) -> None:
        resultado = self.remoto()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        self.assertIn("systemctl restart cody-canal", acciones)
        self.assertLess(acciones.index("pip install"), acciones.index("systemctl stop"))
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
        self.stub("scp", 'echo scp >> "$LOG"; exit 1')
        (self.destino / "backend/.env.incoming").unlink()
        resultado = subprocess.run(
            ["bash", str(checkout / "scripts/ci/deploy.sh"), "prod"],
            env=self.entorno,
            capture_output=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        self.assertNotIn("scp", acciones)
        self.assertLess(
            acciones.index("rsync servidor"), acciones.index("systemctl restart cody")
        )
        self.assertEqual(
            (self.destino / "backend/.env").read_text(),
            (checkout / "backend/.env").read_text(),
        )
        self.assertEqual(
            subprocess.run(
                ["flock", "-n", str(self.lock), "true"], check=False
            ).returncode,
            0,
        )
