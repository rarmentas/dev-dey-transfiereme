# Traslado de CoDi a `/opt/codi/prod`

Procedimiento preparado el 2026-11-14. No ejecutar como un deploy normal.
Inventario: `.temp-inventario-seguridad` en el checkout de preparación.
Release de referencia: pipeline 1517, commit `effbdcd54c625e4ad616eb00eb4cc973b48321fd`.

## Puertas antes de escribir en `/opt/codi`

1. Revisar el diff de la rama `patch/codi-seguridad-preparacion`. No fusionarla a
   `master` ni `test` mientras un job de un commit anterior pueda usar el padre.
2. Completar el respaldo de PostgreSQL y **restaurarlo** en una instancia
   aislada. Guardar la unit, `.env`, release, builds, roles y permisos en
   `/var/backups/codi/production` con `umask 077`. Registrar checksum y hora.
3. Comprobar en GitLab jobs activos y pendientes de CoDi, cancelar/esperar los
   pertinentes y detener reintentos/schedules. Revocar en el VPS la clave SSH
   que usan los jobs antiguos, tras identificar su fingerprint.
   Conservar acceso administrativo independiente y probar que la clave vieja
   ya no entra. Cambiar solo `PROD_DEPLOY_PATH` no protege del job anterior.
4. Con el bloqueo de deploy adquirido, crear el marcador
   `/run/codi-maintenance` administrado por root. El script nuevo lo respeta;
   el script viejo no. Probar el rechazo antes de crear `prod/`.
5. Reconfirmar que el servicio antiguo sigue activo, que PostgreSQL conserva
   ID/StartedAt/imagen/mount, que hay espacio y que no hay cobros en curso sin
   una ruta operativa de seguimiento. Registrar la ventana y su límite de
   reversión. No iniciar el corte si falta cualquiera de estas comprobaciones.

El bloqueo compartido del deploy nuevo es `/run/lock/codi-deploy.lock`. Toda
operación manual de escritura del traslado debe ejecutarse mientras un operador
mantiene `flock -x` sobre ese archivo. El marcador y la revocación de la clave
antigua son controles separados. El padre `/opt/codi` aún es modo `777`: la
revocación efectiva es indispensable.

Después de revocar la clave antigua y confirmar que no hay jobs activos, crear
el marcador mientras se mantiene el lock:

```bash
exec 9>/run/lock/codi-deploy.lock
flock -x 9
sudo install -m 644 /dev/null /run/codi-maintenance
test -f /run/codi-maintenance
# Mantener esta sesión y el descriptor 9 abiertos hasta terminar el staging.
```

Si se cierra la sesión, el lock se libera; el marcador sigue bloqueando el
script nuevo, pero no sustituye la revocación de la clave antigua. Al cerrar
la intervención, retirar el marcador bajo el mismo lock solo después de
aceptar el deploy nuevo y comprobar que los jobs antiguos siguen sin acceso.

## Ensayo de preparación del release

Ensayar en un árbol sintético fuera del VPS productivo antes de usar estos
comandos. Los cinco orígenes explícitos evitan que `rsync` recorra el nuevo
destino, que está dentro del origen. No se usa `--delete`.

```bash
umask 077
sudo install -d -o rarme -g rarme -m 750 /opt/codi/prod

rsync -a --dry-run --itemize-changes \
  --chmod=Du=rwx,Dgo=rx,Fu+rw,Fgo+r,Fgo-w \
  --exclude '.env' --exclude '.env.incoming' --exclude '.venv/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.cache/' \
  --exclude '.dart_tool/' --exclude '.pub-cache/' \
  --exclude 'node_modules/' --exclude '.astro/' \
  /opt/codi/backend /opt/codi/frontend /opt/codi/landing \
  /opt/codi/deploy /opt/codi/scripts /opt/codi/prod/

# Repetir la misma invocación sin --dry-run solo después de revisar el listado.
install -m 600 /opt/codi/backend/.env /opt/codi/prod/backend/.env
/opt/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12 \
  -m venv /opt/codi/prod/backend/.venv
```

Registrar `pip freeze --all` del venv antiguo y preparar los paquetes con
versiones transitivas exactas antes del corte. Instalar ese lock en el venv
nuevo y verificar `pip check`; no mover/copiar el venv antiguo porque contiene
rutas absolutas. Los builds `frontend/build/web` y `landing/dist`, junto con
`backend/staticfiles`, deben estar presentes. Comparar hashes y permisos de
archivos de código y ambos builds con el manifiesto del inventario.

Generar la unit para inspección, sin instalarla:

```bash
sed -e 's|@DEPLOY_PATH@|/opt/codi/prod|g' \
    -e 's|@DEPLOY_USER@|rarme|g' \
    /opt/codi/prod/deploy/cody.service.in > /tmp/cody-prod.service
systemd-analyze verify /tmp/cody-prod.service
```

La unit debe referir a `/opt/codi/prod/backend` en `WorkingDirectory`,
`EnvironmentFile`, `ExecStart` y `ReadWritePaths`. Conservar servicio `cody`,
`RuntimeDirectory=cody` y puerto efectivo 8000. No arrancar una segunda
instancia. Solo para el corte inicial del traslado, no ejecutar `migrate`,
`pip install` ni `docker compose up` como parte de esa fase. El deploy normal
desde el primer deploy nuevo respalda y migra según
[variables de entorno](../desarrollo/variables-entorno.md). Instalar las dependencias del venv nuevo durante
la preparación, con la app antigua todavía activa.

## Corte y reversión

Antes de detener `cody`, registrar el ID, StartedAt, imagen y mount de
`codi-postgres`; confirmar la ausencia de deploys/procesos propios en curso.
Detener productores propios identificados y luego `cody`. Hacer la última
sincronización de archivos mutables identificados, sin copiar PostgreSQL vivo.
Cambiar la variable protegida `PROD_DEPLOY_PATH` a `/opt/codi/prod` en el
ámbito `production`; no copiar secretos a la conversación ni a artefactos CI.
Instalar la unit validada, ejecutar `systemctl daemon-reload` y arrancar `cody`.
No llamar al deploy habitual en esta fase.

Verificar `/api/salud/` con `Host: transfiereme.asware.com.mx`, landing,
Flutter web, assets, login y lectura autorizada; revisar la recepción de
webhooks y cobros pendientes sin crear pagos artificiales. PostgreSQL debe
conservar ID, StartedAt, imagen y mount.

Si falla la app antes de aceptar el corte: bajo el mismo bloqueo, detener
`cody`, restaurar unit y entorno desde el respaldo operativo, restablecer
`PROD_DEPLOY_PATH=/opt/codi/` y arrancar el release conservado en `/opt/codi`.
No restaurar la base de datos para deshacer un cambio de carpetas; podría
descartar cobros posteriores al backup. Mantener el bloqueo hasta comprobar
la salud de la app anterior. La restauración de datos requiere un procedimiento
de incidente aparte.

## Primer deploy nuevo

Este deploy respalda la base y aplica las migraciones antes de detener servicios.

Después de aceptar el corte, fusionar el commit revisado. Crear una clave SSH
nueva y guardar su privada en la variable protegida y oculta
`PROD_SSH_PRIVATE_KEY_V2` con ámbito `production`; instalar solo su pública en
el VPS. Mantener revocada la antigua `PROD_SSH_PRIVATE_KEY`, pues un Retry de
un pipeline anterior todavía ejecuta sus scripts viejos. Con el nuevo pipeline
validado, retirar el marcador de mantenimiento bajo `flock` y lanzar
manualmente `deploy:prod` con `PROD_DEPLOY_PATH=/opt/codi/prod`. Confirmar antes/después
que ni PostgreSQL ni WAHA cambiaron ID, StartedAt, imagen o mounts. `deploy:test`
queda bloqueado. Los jobs antiguos no se reintentan. Solo después de aceptar
el deploy nuevo se retira el release antiguo con lista explícita, sin usar
`/opt/codi/*`, y se restringe la escritura del padre.
