import os
import shutil
import subprocess
import sys
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
        self.units = self.raiz / "units"
        self.units.mkdir()
        self.lock = self.raiz / "codi-deploy.lock"
        self.maintenance = self.raiz / "maintenance"
        self.log = self.raiz / "acciones"
        self.bin = self.raiz / "bin"
        self.bin.mkdir()
        for carpeta in (
            "backend/.venv/bin", "backend/staticfiles", "scripts/ci",
            "deploy", "frontend", "landing",
        ):
            (self.destino / carpeta).mkdir(parents=True, exist_ok=True)
        for nombre in ("preflight-remoto.sh", "deploy-remoto.sh"):
            contenido = (RAIZ / "scripts/ci" / nombre).read_text()
            for origen, destino in (
                ("/opt/codi", self.codi),
                ("/run/lock/codi-deploy.lock", self.lock),
                ("/run/codi-maintenance", self.maintenance),
                ("/etc/systemd/system", self.units),
            ):
                contenido = contenido.replace(origen, str(destino))
            (self.destino / "scripts/ci" / nombre).write_text(contenido)
        for nombre in ("cody.service.in", "cody-canal.service.in"):
            shutil.copy(RAIZ / "deploy" / nombre, self.destino / "deploy" / nombre)
        self.entrada = self.destino / "backend/.env.incoming"
        self.activo = self.destino / "backend/.env"
        self.canal = self.destino / "backend/.env.canal"
        self.entrada.write_text(
            "POSTGRES_PORT=5435\nWAHA_BASE_URL=http://127.0.0.1:3004\n"
            "WAHA_API_KEY=ficticia\nWAHA_INSTANCIA=waha\n"
            "PEY_API_KEY=ficticia\nPEY_WEBHOOK_SECRET=ficticio\n"
            "WAHA_WEBHOOK_SECRET=ficticio\nEMAIL_HOST_PASSWORD=ficticia\n"
        )
        self.activo.write_text("ANTERIOR=1\n")
        self.canal.write_text("CANAL_ANTERIOR=1\n")
        (self.units / "cody.service").write_text("unit web previa\n")
        (self.units / "cody-canal.service").write_text("unit canal previa\n")
        self.entorno = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "LOG": str(self.log),
            "DEST": str(self.destino),
            "UNITS": str(self.units),
            "STARTED": str(self.raiz / "canal-arrancado"),
        }
        self.stub("sudo", '[[ "$1" == -n ]] || exit 2; shift; exec "$@"')
        self.stub("install", 'echo "install $*" >> "$LOG"; /usr/bin/install "$@"')
        self.stub("systemd-analyze", 'exit "${VERIFY_ERROR:-0}"')
        self.stub("curl", 'echo "${HEALTH_CODE:-200}"')
        self.stub("sleep", 'if [[ "$1" != 1 ]]; then /usr/bin/sleep "$@"; fi')
        self.stub("ss", 'echo "127.0.0.1:5435"')
        self.stub("stat", 'echo cody')
        self.stub("systemctl", '''echo "systemctl $*" >> "$LOG"
if [[ "$1" == show ]]; then echo "$DEST/backend"; fi
if [[ "$1 $2" == "restart cody-canal.service" ]]; then touch "$STARTED"; fi
if [[ "$1" == is-active || "$1" == is-enabled ]]; then
  nombre="${@: -1}"
  [[ -f "$UNITS/${nombre%.service}.service" ]] || exit 1
  if [[ "$nombre" == cody-canal.service && -e "$STARTED" &&
        "${CANAL_INACTIVO:-0}" == 1 ]]; then exit 1; fi
fi
exit 0''')
        self.stub("docker", '''echo "docker $*" >> "$LOG"
case "$*" in
  *State.Health.Status*) echo "${PG_HEALTH:-healthy}" ;;
  *State.Running*) echo true ;;
  *com.docker.compose.project*) echo codi ;;
  *com.docker.compose.service*) echo postgres ;;
  *) exit 2 ;;
esac''')
        self.python = self.destino / "backend/.venv/bin/python"
        self.python.write_text(
            '#!/bin/bash\n'
            'if [[ "$1" == -c ]]; then\n'
            '  if [[ "$2" == *"import shlex"* ]]; then\n'
            f'    exec {sys.executable} "$@"\n'
            '  fi\n'
            '  echo 2026-01-01T00:00:00Z; exit 0\n'
            'fi\n'
            'echo "manage $*" >> "$LOG"\n'
            'case "$2" in\n'
            '  check) exit "${CHECK_ERROR:-0}" ;;\n'
            '  migrate) [[ "$3" == --check ]] || exit 99; '
            'exit "${MIGRATIONS_PENDING:-0}" ;;\n'
            '  collectstatic) exit "${STATIC_ERROR:-0}" ;;\n'
            '  estado_canal) [[ "$*" == *"--desde 2026-01-01T00:00:00Z"* ]] '
            '|| exit 2; exit "${LATIDO_ANTERIOR:-0}" ;;\n'
            'esac\n'
        )
        self.python.chmod(0o755)
        pip = self.python.parent / "pip"
        pip.write_text(
            '#!/bin/bash\necho "pip $*" >> "$LOG"\nexit "${PIP_ERROR:-0}"\n'
        )
        pip.chmod(0o755)

    def stub(self, nombre: str, cuerpo: str) -> None:
        archivo = self.bin / nombre
        archivo.write_text(f"#!/bin/bash\n{cuerpo}\n")
        archivo.chmod(0o755)

    def comando_remoto(self, destino=None) -> list[str]:
        return [
            "bash", str(self.destino / "scripts/ci/deploy-remoto.sh"),
            str(destino or self.destino), str(self.python), "cody", "localhost",
            "8000",
        ]

    def remoto(self, **variables: str) -> subprocess.CompletedProcess:
        # El mismo flock exclusivo sostenido por SSH de master, solo en /tmp.
        guardian = subprocess.Popen(
            ["bash", "-c", 'exec 9>"$1"; flock -x 9; echo READY; cat >/dev/null',
             "ensayo", str(self.lock)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(guardian.stdout.readline().strip(), "READY")
            return subprocess.run(
                self.comando_remoto(), env={**self.entorno, **variables},
                capture_output=True, check=False, timeout=15,
            )
        finally:
            guardian.communicate(input="fin\n", timeout=5)

    def preflight(self, destino=None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.destino / "scripts/ci/preflight-remoto.sh"),
             str(destino or self.destino), "cody", str(self.python)],
            env=self.entorno, capture_output=True, check=False,
        )

    def test_preflight_rechaza_padre_hermanos_y_symlink(self) -> None:
        hermano = self.codi / "waha-prod"
        hermano.mkdir()
        centinela = hermano / "centinela"
        centinela.write_text("intacto")
        for destino in (self.codi, hermano, self.codi / "test"):
            self.assertNotEqual(self.preflight(destino).returncode, 0)
        (self.destino / "frontend").rmdir()
        (self.destino / "frontend").symlink_to(hermano, target_is_directory=True)
        self.assertNotEqual(self.preflight().returncode, 0)
        self.assertEqual(centinela.read_text(), "intacto")

    def test_preflight_correcto_y_mantenimiento(self) -> None:
        resultado = self.preflight()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        self.maintenance.touch()
        self.assertNotEqual(self.preflight().returncode, 0)
        self.assertNotEqual(self.remoto().returncode, 0)
        self.assertNotIn("systemctl stop", self.log.read_text())

    def test_remoto_sin_candado_o_destino_invalido_no_modifica(self) -> None:
        for destino in (self.destino, self.codi, self.codi / "test"):
            resultado = subprocess.run(
                self.comando_remoto(destino), env=self.entorno,
                capture_output=True, check=False,
            )
            self.assertNotEqual(resultado.returncode, 0)
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")
        self.assertFalse(self.log.exists())

    def test_preparacion_fallida_no_para_ni_reemplaza_env(self) -> None:
        contenido = self.entrada.read_text()
        for variable in (
            "PIP_ERROR", "MIGRATIONS_PENDING", "CHECK_ERROR", "STATIC_ERROR",
            "VERIFY_ERROR",
        ):
            with self.subTest(variable=variable):
                self.log.unlink(missing_ok=True)
                self.entrada.write_text(contenido)
                resultado = self.remoto(**{variable: "1"})
                self.assertNotEqual(resultado.returncode, 0)
                self.assertNotIn("systemctl stop", self.log.read_text())
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_postgres_no_sano_no_se_repara(self) -> None:
        resultado = self.remoto(PG_HEALTH="unhealthy")
        self.assertNotEqual(resultado.returncode, 0)
        acciones = self.log.read_text()
        self.assertNotIn("systemctl stop", acciones)
        self.assertTrue(all("docker inspect" in linea
                            for linea in acciones.splitlines()
                            if linea.startswith("docker")))

    def test_deploy_correcto_units_env_y_orden(self) -> None:
        resultado = self.remoto()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        primer_stop = acciones.index("systemctl stop")
        self.assertLess(acciones.index("pip install"), primer_stop)
        self.assertIn("requirements-canal.txt", acciones)
        for comando in ("check", "migrate --check --noinput", "collectstatic"):
            self.assertLess(acciones.index("manage manage.py " + comando), primer_stop)
        self.assertLess(acciones.index("systemctl start cody.service"),
                        acciones.index("systemctl restart cody-canal.service"))
        self.assertIn("--desde 2026-01-01T00:00:00Z", acciones)
        self.assertTrue(all("--check" in linea for linea in acciones.splitlines()
                            if "manage.py migrate" in linea))
        self.assertTrue(all("docker inspect" in linea
                            for linea in acciones.splitlines()
                            if linea.startswith("docker")))
        for nombre, ejecutable in (
            ("cody", "gunicorn"), ("cody-canal", "python manage.py procesar_canal"),
        ):
            unit = (self.units / f"{nombre}.service").read_text()
            self.assertNotIn("@", unit)
            self.assertIn(f"WorkingDirectory={self.destino}/backend", unit)
            self.assertIn(f"ExecStart={self.python.parent}/{ejecutable}", unit)
        contenido = self.canal.read_text()
        self.assertIn("WAHA_INSTANCIA=waha\n", contenido)
        self.assertIn("WAHA_BASE_URL=http://127.0.0.1:3004\n", contenido)
        self.assertIn("WAHA_API_KEY=ficticia\n", contenido)
        for secreto in (
            "PEY_API_KEY", "PEY_WEBHOOK_SECRET", "WAHA_WEBHOOK_SECRET",
            "EMAIL_HOST_PASSWORD",
        ):
            self.assertNotIn(secreto, contenido)
        self.assertEqual(self.canal.stat().st_mode & 0o777, 0o600)

    def test_latido_viejo_o_unit_inactiva_restaura_ambos(self) -> None:
        contenido = self.entrada.read_text()
        for variable in ("LATIDO_ANTERIOR", "CANAL_INACTIVO", "HEALTH_CODE"):
            with self.subTest(variable=variable):
                self.entrada.write_text(contenido)
                self.log.unlink(missing_ok=True)
                (self.raiz / "canal-arrancado").unlink(missing_ok=True)
                resultado = self.remoto(**{variable: "503" if variable ==
                                           "HEALTH_CODE" else "1"})
                self.assertNotEqual(resultado.returncode, 0)
                self.assertIn(b"restaurando units y entornos", resultado.stderr)
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")
                self.assertEqual(self.canal.read_text(), "CANAL_ANTERIOR=1\n")
                self.assertEqual((self.units / "cody.service").read_text(),
                                 "unit web previa\n")
                self.assertEqual((self.units / "cody-canal.service").read_text(),
                                 "unit canal previa\n")
                self.assertIn("systemctl start cody-canal.service",
                              self.log.read_text())

    def test_primera_instalacion_fallida_no_deja_canal_nuevo(self) -> None:
        (self.units / "cody-canal.service").unlink()
        self.canal.unlink()
        resultado = self.remoto(LATIDO_ANTERIOR="1")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertFalse(self.canal.exists())
        self.assertFalse((self.units / "cody-canal.service").exists())
        self.assertNotIn("systemctl start cody-canal.service", self.log.read_text())
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")
