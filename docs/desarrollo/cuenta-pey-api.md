# API cuenta pey (estado, registro y sincronización)

Rutas bajo `/api/cuenta/pey/`. El comercio sale de la sesión del vendedor (`requerir_comercio` / `preparar_operacion_cobro`). No se acepta `comercio`, `comercio_id` ni otros identificadores de comercio en el cuerpo: responde `400` con el mensaje de ámbito (`ComercioEnCuerpoError`). Sin cookie de sesión válida, el middleware responde `403` con `{"detail": "Debe iniciar sesión."}`.

La CLABE se guarda aparte (`POST /api/cuenta/clabe/`; véase [sesion-api.md](sesion-api.md)). Estos endpoints leen la CLABE ya persistida y el vínculo local con pey (`pey_bank_account_id`, `pey_codi_status`).

`puede_cobrar` en el JSON de estado es el mismo criterio que el servidor usa para altas de cobro (`cuenta_esta_active`): cuenta `ACTIVE` en pey, o en desarrollo la semilla `semilla_active_dev` cuando aplica.

## `GET /api/cuenta/pey/estado/`

Sesión activa. Sin membresía de comercio: `403`.

Respuesta `200` (ejemplo):

```json
{
  "fase": "pendiente_activacion",
  "paso": 3,
  "codi_status": "pending",
  "puede_cobrar": false,
  "clabe_enmascarada": "**************5713",
  "tiene_cuenta_pey": true,
  "pey_bank_account_id_sufijo": "Q0P",
  "actualizado_en": "2026-11-08T17:06:00+00:00"
}
```

| Campo | Valores |
| --- | --- |
| `fase` | `sin_clabe`, `pendiente_registro`, `pendiente_activacion`, `activa` |
| `paso` | `1`, `2`, `3` o `null` (null cuando `activa`) |
| `codi_status` | `pending` o `active` (lo persistido en Django) |
| `clabe_enmascarada` | vacío o 14 asteriscos + 4 últimos dígitos |
| `pey_bank_account_id_sufijo` | últimos 4 caracteres del ULID o vacío |

La respuesta no incluye la CLABE completa ni el ULID completo.

## `POST /api/cuenta/pey/registro/`

Registra en pey la CLABE guardada del comercio de la sesión. Cuerpo JSON:

```json
{
  "nombre": "Ana López",
  "entidad": "PERSON",
  "alias": "Tienda opcional",
  "reemplazar": false
}
```

`entidad` debe ser `PERSON` o `BUSINESS`. `reemplazar` por defecto es falso. Solo con **`reemplazar: true`** (o equivalentes `true`, `1`, `si`, `sí` en string) se vuelve a llamar a pey si ya hay `pey_bank_account_id`. Si ya existe id y no se envía `reemplazar: true`, responde **`409`** con `codigo` `CUENTA_PEY_YA_REGISTRADA` y `detail` «El comercio ya tiene cuenta en pey. Envíe reemplazar: true para registrar otra.» La app debe pedir confirmación explícita al usuario antes de mandar `reemplazar: true`.

Éxito: `200` con el mismo cuerpo que `GET …/estado/` tras persistir id y estado.

| HTTP | Cuerpo (resumen) |
| --- | --- |
| `400` | Sin CLABE válida: `codigo` `SIN_CLABE`. Validación de nombre/entidad/alias. `comercio` en cuerpo: ámbito. |
| `403` | Sin membresía. |
| `409` | Cuenta ya registrada sin `reemplazar: true` (`CUENTA_PEY_YA_REGISTRADA`). |
| `502` | pey no registró: `detail`, `tipo`, `request_id`. |
| `503` | Adaptador distinto de producción: `codigo` `ADAPTADOR_NO_PRODUCCION`, `detail` «El registro en pey no está disponible en este entorno.» En local con `PEY_ADAPTADOR=desarrollo` la app **no** puede registrar por API; use el comando en el servidor. |
| `503` | Timeout o error incierto tras posible alta: `codigo` `PEY_INCIERTO`, `tipo`, `request_id` (puede ser null). |

El registro desde la app solo opera con **`PEY_ADAPTADOR=produccion`** (misma regla que el comando). El servicio serializa altas concurrentes con `select_for_update` en el comercio antes de llamar a pey.

Estados de pey distintos de `ACTIVE` (p. ej. `PROCESSING`) se guardan como `pending` y la UI muestra paso 3.

## `POST /api/cuenta/pey/sincronizar/`

Sin cuerpo obligatorio. Si el cuerpo trae `comercio_id` u otro identificador de comercio: `400` (misma regla que registro). Consulta pey por la CLABE del comercio y actualiza `pey_codi_status` y `pey_bank_account_id` local.

Éxito: `200` con el mismo JSON que `GET …/estado/`.

| HTTP | Cuerpo (resumen) |
| --- | --- |
| `403` | Sin sesión o sin membresía. |
| `429` | Menos de **30 s** desde la última sincronización manual (o desde la ventana reservada al iniciar sync): `detail` «Espere antes de volver a sincronizar.», `reintento_en_segundos` (entero ≥ 1). El tope usa `select_for_update` en el comercio. |
| `200` | Error pey distinto de `BANK_ACCOUNT_NOT_FOUND`: no cambia el estado persistido (no `500`). |
| `200` | `BANK_ACCOUNT_NOT_FOUND`: limpia el ULID local y el comercio vuelve a paso 2. |

El botón «Revisar estado» en la app usa esta ruta.

## Comando `registrar_cuenta_pey`

Sin cambios de contrato respecto a master: mismos argumentos (`--correo`, `--nombre`, `--entidad`, `--alias`, `--confirmar`, `--reemplazar`), misma salida previa al POST (CLABE enmascarada), y con `--confirmar` imprime `Cuenta registrada id=<ULID> codiStatus=<valor crudo de pey>` (p. ej. `PROCESSING` aunque en base quede `pending`). Solo corre con **`PEY_ADAPTADOR=produccion`**; en otro modo: `CommandError` «Este comando solo corre con PEY_ADAPTADOR=produccion.» La lógica de registro delega en `ambito.cuenta_pey_servicio.registrar_cuenta_en_pey` (compartida con la API).

Pruebas locales del comando y del diagnóstico: [gates-pey.md](gates-pey.md) (sección 1.8).
