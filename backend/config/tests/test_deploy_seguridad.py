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
        self.stt = self.raiz / "stt"
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
                ("/var/lib/codi/stt", self.stt),
                ("/run/lock/codi-deploy.lock", self.lock),
                ("/run/codi-maintenance", self.maintenance),
                ("/etc/systemd/system", self.units),
            ):
                contenido = contenido.replace(origen, str(destino))
            (self.destino / "scripts/ci" / nombre).write_text(contenido)
        for nombre in ("cody.service.in", "cody-canal.service.in",
                       "cody-cobros.service.in", "cody-stt.service.in"):
            shutil.copy(RAIZ / "deploy" / nombre, self.destino / "deploy" / nombre)
        self.entrada = self.destino / "backend/.env.incoming"
        self.activo = self.destino / "backend/.env"
        self.canal = self.destino / "backend/.env.canal"
        self.entrada.write_text(
            "POSTGRES_USER=cody\nPOSTGRES_DB=cody_test\n"
            "POSTGRES_PASSWORD=clave-ficticia-secreta\n"
            "POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=5435\nWAHA_BASE_URL=http://127.0.0.1:3004\n"
            "WAHA_API_KEY=ficticia\nWAHA_INSTANCIA=waha\n"
            "AGENTE_PEDIDOS_API_KEY=ficticia-modelo\n"
            "AGENTE_PEDIDOS_MODELO=modelo-prueba\n"
            "AGENTE_PEDIDOS_TIMEOUT_S=25\n"
            "PEY_API_KEY=ficticia\nPEY_WEBHOOK_SECRET=ficticio\n"
            "NUCLEO_ADAPTADOR=real\nPEDIDOS_COBRO_HABILITADO=true\n"
            "WAHA_WEBHOOK_SECRET=ficticio\nEMAIL_HOST_PASSWORD=ficticia\n"
        )
        self.activo.write_text("ANTERIOR=1\n")
        self.canal.write_text("CANAL_ANTERIOR=1\n")
        (self.raiz / "web-activa").touch()
        (self.raiz / "web-entorno").write_text("ANTERIOR=1\n")
        (self.units / "cody.service").write_text("unit web previa\n")
        (self.units / "cody-canal.service").write_text("unit canal previa\n")
        self.entorno = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "LOG": str(self.log),
            "DEST": str(self.destino),
            "UNITS": str(self.units),
            "STARTED": str(self.raiz / "canal-arrancado"),
            "HOME": str(self.raiz),
            "MIGRATED": str(self.raiz / "migrado"),
            "WEB_ACTIVA": str(self.raiz / "web-activa"),
            "WEB_ENTORNO": str(self.raiz / "web-entorno"),
            "WEB_HISTORIAL": str(self.raiz / "web-historial"),
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
if [[ "$2" == cody.service ]]; then
  case "$1" in
    stop) rm -f "$WEB_ACTIVA" ;;
    start|restart)
      if [[ "$1" == restart && -n "${WEB_FALLA:-}" ]]; then
        rm -f "$WEB_ACTIVA"
        touch "$WEB_ACTIVA.fallo"
        if [[ "$WEB_FALLA" != inactiva ]]; then exit 1; fi
        exit 0
      fi
      if [[ "$1" == start && "${WEB_FALLA:-}" == persistente &&
            -e "$WEB_ACTIVA.fallo" ]]; then exit 1; fi
      if [[ "$1" == restart || ! -e "$WEB_ACTIVA" ]]; then
        cp "$DEST/backend/.env" "$WEB_ENTORNO"
        cat "$DEST/backend/.env" >> "$WEB_HISTORIAL"
        touch "$WEB_ACTIVA"
      fi ;;
    is-active) [[ -e "$WEB_ACTIVA" ]] || exit 1 ;;
  esac
fi
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
  *pg_dump*)
    if [[ "${EXPECT_NO_PASSWORD:-0}" == 1 ]]; then
      [[ "$*" == "exec codi-postgres pg_dump -U cody -Fc cody_test" &&
         ! -v PGPASSWORD ]] || exit 2
    else
      [[ "$*" == "exec -e PGPASSWORD codi-postgres pg_dump -U cody -Fc cody_test" &&
         "${PGPASSWORD:-}" == clave-ficticia-secreta ]] || exit 2
    fi
    if [[ "${DUMP_INTERRUPT:-0}" == 1 ]]; then
      printf PGDMP
      kill -TERM "$PPID"
      exit 1
    fi
    [[ "${DUMP_ERROR:-0}" == 0 ]] || exit 1
    [[ "${DUMP_EMPTY:-0}" == 1 ]] || printf 'PGDMP contenido ficticio'
    ;;
  "exec -i codi-postgres pg_restore --list")
    contenido="$(cat)"
    [[ "$contenido" == 'PGDMP contenido ficticio' ]] || exit 2
    exit "${RESTORE_ERROR:-0}" ;;
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
            '  migrate) case "$3" in\n'
            '    --plan) echo "pedidos.0001_inicial"; exit "${PLAN_ERROR:-0}" ;;\n'
            '    --noinput) [[ "${MIGRATE_ERROR:-0}" == 0 ]] || exit 1; '
            'touch "$MIGRATED" ;;\n'
            '    --check) [[ -f "$MIGRATED" && "${MIGRATIONS_PENDING:-0}" == 0 ]] '
            '|| exit 1 ;;\n'
            '    *) exit 99 ;; esac ;;\n'
            '  collectstatic) exit "${STATIC_ERROR:-0}" ;;\n'
            '  estado_canal) [[ "$*" == *"--desde 2026-01-01T00:00:00Z"* ]] '
            '|| exit 2; [[ -z "${FALLA_PROCESO:-}" || '
            '"$*" != *"--proceso $FALLA_PROCESO"* ]] '
            '|| exit 1; exit "${LATIDO_ANTERIOR:-0}" ;;\n'
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
            "PIP_ERROR", "DUMP_ERROR", "DUMP_EMPTY", "RESTORE_ERROR",
            "PLAN_ERROR", "MIGRATE_ERROR", "MIGRATIONS_PENDING", "CHECK_ERROR",
            "STATIC_ERROR", "VERIFY_ERROR",
        ):
            with self.subTest(variable=variable):
                self.log.unlink(missing_ok=True)
                (self.raiz / "migrado").unlink(missing_ok=True)
                shutil.rmtree(self.raiz / "respaldos", ignore_errors=True)
                self.entrada.write_text(contenido)
                resultado = self.remoto(**{variable: "1"})
                self.assertNotEqual(resultado.returncode, 0)
                acciones = self.log.read_text()
                for accion in ("systemctl stop", "systemctl restart", "systemctl start",
                               "install -m 644"):
                    self.assertNotIn(accion, acciones)
                if variable in ("DUMP_ERROR", "DUMP_EMPTY", "RESTORE_ERROR"):
                    self.assertNotIn("manage manage.py migrate", acciones)
                    self.assertIn(b"Respaldo fallido", resultado.stderr)
                    self.assertFalse(list((self.raiz / "respaldos").rglob("*.partial")))
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_threads_con_stt_apagado_y_entorno_intacto(self) -> None:
        base = self.entrada.read_text() + "STT_HABILITADO=0\n"
        for valor in ("", "abc", "2 # comentario"):
            with self.subTest(valor=valor):
                self.log.unlink(missing_ok=True)
                contenido = base + f"STT_CPU_THREADS={valor}\n"
                self.entrada.write_text(contenido)
                resultado = self.remoto()
                self.assertNotEqual(resultado.returncode, 0)
                acciones = self.log.read_text()
                for accion in ("pg_dump", "manage manage.py migrate", "systemctl stop"):
                    self.assertNotIn(accion, acciones)
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")
                self.assertEqual(self.entrada.read_text(), contenido)
        for linea in ("", "STT_CPU_THREADS=2\n"):
            with self.subTest(linea=linea):
                shutil.rmtree(self.raiz / "respaldos", ignore_errors=True)
                self.entrada.write_text(base + linea)
                resultado = self.remoto()
                self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())

    def test_stt_flag_invalido_no_detiene_servicios(self) -> None:
        with self.entrada.open("a") as archivo:
            archivo.write("STT_HABILITADO=2\n")
        self.assertNotEqual(self.remoto().returncode, 0)
        self.assertNotIn("systemctl stop", self.log.read_text())
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_rol_web_invalido_no_detiene_servicios(self) -> None:
        with self.entrada.open("a") as archivo:
            archivo.write("CODY_ROL=canal\n")
        self.assertNotEqual(self.remoto().returncode, 0)
        self.assertNotIn("systemctl stop", self.log.read_text())
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_waha_puerto_anterior_no_detiene_servicios(self) -> None:
        with self.entrada.open("a") as archivo:
            archivo.write("WAHA_BASE_URL=http://127.0.0.1:3000\n")
        self.assertNotEqual(self.remoto().returncode, 0)
        self.assertNotIn("systemctl stop", self.log.read_text())
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_env_worker_symlink_rechazado(self) -> None:
        hermano = self.raiz / "hermano"
        hermano.write_text("intacto")
        for rol in ("cobros", "stt"):
            with self.subTest(rol=rol):
                enlace = self.destino / f"backend/.env.{rol}"
                enlace.symlink_to(hermano)
                self.assertNotEqual(self.preflight().returncode, 0)
                self.assertNotEqual(self.remoto().returncode, 0)
                self.assertEqual(hermano.read_text(), "intacto")
                enlace.unlink()

    def test_fallo_de_latido_por_proceso_restaura_servicios(self) -> None:
        contenido = self.entrada.read_text()
        for proceso in ("procesar_canal", "procesar_cobros"):
            with self.subTest(proceso=proceso):
                shutil.rmtree(self.raiz / "respaldos", ignore_errors=True)
                self.entrada.write_text(contenido)
                resultado = self.remoto(FALLA_PROCESO=proceso)
                self.assertNotEqual(resultado.returncode, 0)
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")
                self.assertEqual(self.canal.read_text(), "CANAL_ANTERIOR=1\n")

    def test_stt_sin_modelo_no_detiene_servicios(self) -> None:
        with self.entrada.open("a") as archivo:
            archivo.write("STT_HABILITADO=1\n")
        resultado = self.remoto()
        self.assertNotEqual(resultado.returncode, 0)
        acciones = self.log.read_text()
        for accion in ("pg_dump", "manage manage.py migrate", "systemctl stop"):
            self.assertNotIn(accion, acciones)
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
        orden = ["manage manage.py check", "pg_dump", "manage manage.py migrate --plan",
                 "manage manage.py migrate --noinput",
                 "manage manage.py migrate --check --noinput",
                 "manage manage.py collectstatic", "systemctl stop"]
        posiciones = [acciones.index(paso) for paso in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        respaldos = list((self.raiz / "respaldos/codi").glob("*.dump"))
        self.assertEqual(len(respaldos), 1)
        self.assertEqual(respaldos[0].read_bytes(), b"PGDMP contenido ficticio")
        self.assertNotIn(b"clave-ficticia-secreta", resultado.stdout + resultado.stderr)
        self.assertNotIn(b"ficticia-modelo", resultado.stdout + resultado.stderr)
        self.assertLess(acciones.index("systemctl start cody.service"),
                        acciones.index("systemctl restart cody-canal.service"))
        self.assertIn("--desde 2026-01-01T00:00:00Z", acciones)
        for nombre, ejecutable in (
            ("cody", "gunicorn"), ("cody-canal", "python manage.py procesar_canal"),
            ("cody-cobros", "python manage.py procesar_cobros"),
        ):
            unit = (self.units / f"{nombre}.service").read_text()
            self.assertNotIn("@", unit)
            self.assertIn(f"WorkingDirectory={self.destino}/backend", unit)
            self.assertIn(f"ExecStart={self.python.parent}/{ejecutable}", unit)
        contenido = self.canal.read_text()
        self.assertIn("WAHA_INSTANCIA=waha\n", contenido)
        self.assertIn("WAHA_BASE_URL=http://127.0.0.1:3004\n", contenido)
        self.assertIn("WAHA_API_KEY=ficticia\n", contenido)
        self.assertIn("AGENTE_PEDIDOS_API_KEY=ficticia-modelo\n", contenido)
        self.assertIn("AGENTE_PEDIDOS_MODELO=modelo-prueba\n", contenido)
        self.assertIn("AGENTE_PEDIDOS_TIMEOUT_S=25\n", contenido)
        for secreto in (
            "PEY_API_KEY", "PEY_WEBHOOK_SECRET", "WAHA_WEBHOOK_SECRET",
            "EMAIL_HOST_PASSWORD",
        ):
            self.assertNotIn(secreto, contenido)
        self.assertEqual(self.canal.stat().st_mode & 0o777, 0o600)
        cobros = (self.destino / "backend/.env.cobros").read_text()
        stt = (self.destino / "backend/.env.stt").read_text()
        self.assertIn("PEY_API_KEY=ficticia", cobros)
        self.assertNotIn("WAHA_API_KEY", cobros)
        self.assertNotIn("PEY_WEBHOOK_SECRET", cobros)
        self.assertIn("WAHA_API_KEY=ficticia", stt)
        self.assertNotIn("PEY_API_KEY", stt)
        self.assertNotIn("AGENTE_PEDIDOS_API_KEY", stt)
        self.assertNotIn("AGENTE_PEDIDOS_API_KEY", cobros)
        for rol in ("canal", "cobros", "stt"):
            entorno = self.destino / f"backend/.env.{rol}"
            self.assertEqual(entorno.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("CODY_ROL=", entorno.read_text())
        unit = (self.units / "cody-stt.service").read_text()
        self.assertIn(
            f"ExecStart={self.stt}/venv/bin/python manage.py procesar_audio", unit
        )
        self.assertIn(f"ReadWritePaths={self.destino} {self.stt}", unit)
        self.assertIn("systemctl disable --now cody-stt.service", acciones)
        for proceso in ("procesar_canal", "procesar_cobros"):
            self.assertIn(f"--proceso {proceso}", acciones)


    def test_stt_precargado_antes_del_corte_y_latido(self) -> None:
        (self.stt / "venv/bin").mkdir(parents=True)
        (self.stt / "modelos").mkdir()
        python = self.stt / "venv/bin/python"
        python.write_text(
            "#!/bin/bash\n"
            f"echo stt-preflight >> '{self.log}'\n"
            '[[ "$HF_HUB_OFFLINE" == 1 && "$CODY_ROL" == stt ]]\n'
        )
        python.chmod(0o755)
        self.stub("ffmpeg", "exit 0")
        self.stub("ffprobe", "exit 0")
        with self.entrada.open("a") as archivo:
            archivo.write("STT_HABILITADO=1\nSTT_CPU_THREADS=2\n")
        resultado = self.remoto()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        acciones = self.log.read_text()
        self.assertLess(
            acciones.index("stt-preflight"), acciones.index("pg_dump")
        )
        self.assertIn("systemctl enable --now cody-stt.service", acciones)
        self.assertIn("--proceso procesar_audio", acciones)

    def test_modelo_offline_invalido_no_respalda_ni_migra(self) -> None:
        (self.stt / "venv/bin").mkdir(parents=True)
        (self.stt / "modelos").mkdir()
        python = self.stt / "venv/bin/python"
        python.write_text("#!/bin/sh\nexit 1\n")
        python.chmod(0o755)
        self.stub("ffmpeg", "exit 0")
        self.stub("ffprobe", "exit 0")
        with self.entrada.open("a") as archivo:
            archivo.write("STT_HABILITADO=1\nSTT_CPU_THREADS=2\n")
        resultado = self.remoto()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(b"modelo STT no disponibles", resultado.stderr)
        acciones = self.log.read_text()
        for accion in ("pg_dump", "manage manage.py migrate", "systemctl stop"):
            self.assertNotIn(accion, acciones)
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_recuperacion_reinicia_web_con_entorno_anterior(self) -> None:
        resultado = self.remoto(FALLA_PROCESO="procesar_cobros")
        self.assertNotEqual(resultado.returncode, 0)
        historial = (self.raiz / "web-historial").read_text()
        self.assertIn("WAHA_API_KEY=ficticia", historial)
        self.assertEqual((self.raiz / "web-entorno").read_text(), "ANTERIOR=1\n")
        self.assertTrue((self.raiz / "web-activa").exists())

    def test_reintenta_arranque_web_si_falla_reinicio_de_recuperacion(self) -> None:
        resultado = self.remoto(
            FALLA_PROCESO="procesar_cobros", WEB_FALLA="transitoria"
        )
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(b"procesar_cobros", resultado.stderr)
        acciones = self.log.read_text()
        reinicio = acciones.index("systemctl restart cody.service")
        self.assertIn("systemctl start cody.service", acciones[reinicio:])
        self.assertEqual((self.raiz / "web-entorno").read_text(), "ANTERIOR=1\n")
        self.assertTrue((self.raiz / "web-activa").exists())
        self.assertNotIn("recuperación web fallida".encode(), resultado.stderr)

    def test_fallo_persistente_web_se_reporta_y_recupera_workers(self) -> None:
        (self.units / "cody-cobros.service").write_text("unit cobros previa\n")
        (self.destino / "backend/.env.cobros").write_text("cobros=anterior\n")
        resultado = self.remoto(
            FALLA_PROCESO="procesar_cobros", WEB_FALLA="persistente"
        )
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("recuperación web fallida".encode(), resultado.stderr)
        self.assertFalse((self.raiz / "web-activa").exists())
        acciones = self.log.read_text()
        self.assertIn("systemctl start cody-canal.service", acciones)
        self.assertIn("systemctl start cody-cobros.service", acciones)
        self.assertEqual((self.destino / "backend/.env.cobros").read_text(),
                         "cobros=anterior\n")

    def test_reinicio_exitoso_con_web_inactiva_se_reporta(self) -> None:
        resultado = self.remoto(FALLA_PROCESO="procesar_cobros", WEB_FALLA="inactiva")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("recuperación web fallida".encode(), resultado.stderr)
        self.assertIn("systemctl start cody-canal.service", self.log.read_text())

    def test_fallo_restablece_cobros_y_stt_previos(self) -> None:
        for rol in ("cobros", "stt"):
            (self.units / f"cody-{rol}.service").write_text(f"unit {rol} previa\n")
            (self.destino / f"backend/.env.{rol}").write_text(f"{rol}=anterior\n")
        resultado = self.remoto(LATIDO_ANTERIOR="1")
        self.assertNotEqual(resultado.returncode, 0)
        for rol in ("cobros", "stt"):
            self.assertEqual((self.units / f"cody-{rol}.service").read_text(),
                             f"unit {rol} previa\n")
            self.assertEqual((self.destino / f"backend/.env.{rol}").read_text(),
                             f"{rol}=anterior\n")
            self.assertIn(f"systemctl start cody-{rol}.service", self.log.read_text())

    def test_retencion_conserva_diez_y_archivo_ajeno(self) -> None:
        carpeta = self.raiz / "respaldos/codi"
        carpeta.mkdir(parents=True)
        for numero in range(12):
            (carpeta / f"codi-pre-deploy-20200101-{numero:06d}.dump").write_bytes(b"x")
        ajeno = carpeta / "otro.dump"
        ajeno.write_bytes(b"intacto")
        notas = carpeta / "codi-pre-deploy-000-notas.dump"
        notas.write_bytes(b"notas")
        enlace = carpeta / "codi-pre-deploy-19990101-000000.dump"
        enlace.symlink_to(ajeno)
        resultado = self.remoto()
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        nuevo = next(p for p in carpeta.glob("*.dump")
                     if p.read_bytes() == b"PGDMP contenido ficticio")
        esperados = {f"codi-pre-deploy-20200101-{numero:06d}.dump"
                     for numero in range(3, 12)} | {nuevo.name}
        conservados = {p.name for p in carpeta.glob("codi-pre-deploy-*.dump")
                       if p.is_file() and not p.is_symlink()
                       and p.name != "codi-pre-deploy-000-notas.dump"}
        self.assertEqual(conservados, esperados)
        self.assertEqual(ajeno.read_bytes(), b"intacto")
        self.assertEqual(notas.read_bytes(), b"notas")
        self.assertTrue(enlace.is_symlink())

    def test_respaldo_fallido_no_borra_respaldo_anterior(self) -> None:
        carpeta = self.raiz / "respaldos/codi"
        carpeta.mkdir(parents=True)
        previo = carpeta / "codi-pre-deploy-20200101-000000.dump"
        previo.write_bytes(b"anterior")
        resultado = self.remoto(RESTORE_ERROR="1")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertEqual(previo.read_bytes(), b"anterior")
        self.assertEqual(list(carpeta.glob("*.dump")), [previo])

    def test_respaldo_sin_password_no_pasa_pgpassword(self) -> None:
        self.entrada.write_text(self.entrada.read_text() + "POSTGRES_PASSWORD=\n")
        resultado = self.remoto(PGPASSWORD="no-heredar", EXPECT_NO_PASSWORD="1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode())
        self.assertIn("docker exec codi-postgres pg_dump", self.log.read_text())
        self.assertNotIn(b"no-heredar", resultado.stdout + resultado.stderr)

    def test_host_remoto_aborta_sin_mostrar_valor(self) -> None:
        self.entrada.write_text(
            self.entrada.read_text() + "POSTGRES_HOST=servidor-ajeno\n"
        )
        resultado = self.remoto()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertNotIn(b"servidor-ajeno", resultado.stdout + resultado.stderr)
        acciones = self.log.read_text()
        for accion in ("pg_dump", "manage manage.py migrate", "systemctl stop",
                       "systemctl restart", "systemctl start", "install -m 644"):
            self.assertNotIn(accion, acciones)
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_interrupcion_dump_limpia_parcial(self) -> None:
        resultado = self.remoto(DUMP_INTERRUPT="1")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertFalse(list((self.raiz / "respaldos").rglob("*.partial")))
        self.assertNotIn("manage manage.py migrate", self.log.read_text())
        self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_stub_rechaza_comandos_dump_incorrectos(self) -> None:
        script = self.destino / "scripts/ci/deploy-remoto.sh"
        original = script.read_text()
        cambios = (
            ('-Fc "$POSTGRES_DB"', '"$POSTGRES_DB"'),
            ('-U "$POSTGRES_USER"', '-U otro_usuario'),
            ('-Fc "$POSTGRES_DB"', '-Fc otra_base'),
            ('-Fc "$POSTGRES_DB"', '-Fc "$POSTGRES_DB" "$POSTGRES_PASSWORD"'),
        )
        entrada = self.entrada.read_text()
        for antes, despues in cambios:
            with self.subTest(cambio=despues):
                script.write_text(original.replace(antes, despues))
                self.entrada.write_text(entrada)
                self.log.unlink(missing_ok=True)
                resultado = self.remoto()
                self.assertNotEqual(resultado.returncode, 0)
                self.assertNotIn("manage manage.py migrate", self.log.read_text())
                self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_usuario_y_base_invalidos_abortan(self) -> None:
        original = self.entrada.read_text()
        for clave in ("POSTGRES_USER", "POSTGRES_DB"):
            for valor in ("", "invalido;comando"):
                with self.subTest(clave=clave, valor=valor):
                    self.entrada.write_text(original + f"{clave}={valor}\n")
                    self.log.unlink(missing_ok=True)
                    resultado = self.remoto()
                    self.assertNotEqual(resultado.returncode, 0)
                    acciones = self.log.read_text()
                    for accion in ("pg_dump", "manage manage.py migrate",
                                   "systemctl stop", "systemctl restart",
                                   "systemctl start", "install -m 644"):
                        self.assertNotIn(accion, acciones)
                    self.assertEqual(self.activo.read_text(), "ANTERIOR=1\n")

    def test_latido_viejo_o_unit_inactiva_restaura_ambos(self) -> None:
        contenido = self.entrada.read_text()
        for variable in ("LATIDO_ANTERIOR", "CANAL_INACTIVO", "HEALTH_CODE"):
            with self.subTest(variable=variable):
                self.entrada.write_text(contenido)
                self.log.unlink(missing_ok=True)
                (self.raiz / "canal-arrancado").unlink(missing_ok=True)
                shutil.rmtree(self.raiz / "respaldos", ignore_errors=True)
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
