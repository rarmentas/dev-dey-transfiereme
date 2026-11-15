# WAHA de producción de CoDi

Definición separada del release Django. Proyecto Compose `codi-waha-prod`,
servicio `waha`, contenedor `codi-waha-prod`, puerto `127.0.0.1:3004`.
Instalar después de aceptar el traslado de CoDi a `/opt/codi/prod`; este
documento no implica que exista una sesión vinculada.

## Imagen y datos

La imagen `devlikeapro/waha:gows-2026.10.1` ya estaba disponible en
`intec-vps-001` durante el inventario. El Compose usa su digest observado
`sha256:1f7faeb0227ad5edb5711f7058bfce807ea65e5f92234af0778e4db140f6eb46`
para evitar resolver `latest` durante el corte. WAHA Core incluye GOWS y
almacenamiento local en versiones posteriores a 2026.6.1. Revisar el digest
contra la plataforma antes de instalarlo en otro host.

Las sesiones viven en `/var/lib/codi/waha-prod/sessions` y la media en
`/var/lib/codi/waha-prod/media`, montadas respectivamente en `/app/.sessions`
y `/app/.media`. El instalador crea esas rutas con propiedad del operador
local y modo `700`; se debe confirmar el UID/GID efectivo de la imagen y la
capacidad de escritura antes de vincular un número. La media se conserva
(`WHATSAPP_FILES_LIFETIME=0`), por lo que hay que medir crecimiento y preparar
su respaldo y retención. No montar datos de Denti ni PostgreSQL de CoDi.

## Instalación

El script `scripts/infra/instalar-waha-prod.sh` se ejecuta **en el VPS** desde
un paquete revisado de esta rama, transferido a un staging privado. WAHA se
instala antes del primer deploy nuevo, por lo que el release antiguo copiado a
`/opt/codi/prod` todavía no contiene este script. El instalador exige que `/opt/codi/waha-prod` y
`/var/lib/codi/waha-prod` no existan, que el puerto 3004 y el nombre de
contenedor estén libres, que la imagen fijada esté descargada y que CoDi y
PostgreSQL estén sanos. No hace pull ni recrea PostgreSQL.

Preparar en el VPS un staging con la misma estructura `scripts/infra/` y
`deploy/waha-prod/`, copiando solo el script y `compose.yaml` revisados.
Después de verificar sus hashes frente al checkout, ejecutarlo allí; por
ejemplo, si se preparó en `/tmp/codi-preparacion`:

```bash
bash /tmp/codi-preparacion/scripts/infra/instalar-waha-prod.sh
```

Instala `/opt/codi/waha-prod/compose.yaml` y genera dos archivos privados:
`.env` con el hash SHA-512 de la clave API, y `.api-key` con la clave en claro
para el operador. Ambos tienen modo `600` y quedan fuera del rsync de Django.
El dashboard, Swagger y QR en logs quedan deshabilitados. El servicio solo
escucha en loopback; administrar por túnel SSH si hace falta.

El instalador levanta únicamente `waha` con `--no-deps --pull never`, comprueba
que la API rechaza peticiones sin clave o con una incorrecta (401), acepta la
correcta (200), y que CoDi y el ID/StartedAt/imagen de PostgreSQL siguen
intactos. Suprime los cuerpos de respuesta para no mostrar sesiones,
teléfonos ni mensajes. Ante fallo detiene solo `codi-waha-prod` y conserva
configuración, sesiones y media para diagnóstico. No usar `down -v`.

La clave en `.api-key` es administrativa; no colocarla en URL, logs, Git ni
artefactos. Para la futura integración Django, crear una clave con permisos
acotados y transferirla por canal privado. La instalación no crea webhooks ni
envía mensajes. Vincular un número exige al titular y una prueba posterior de
persistencia tras reinicio controlado.

Fuentes: [seguridad](https://waha.devlike.pro/docs/how-to/security/),
[almacenamiento](https://waha.devlike.pro/docs/how-to/storages/) y
[ediciones actuales](https://waha.devlike.pro/docs/overview/faq/).
