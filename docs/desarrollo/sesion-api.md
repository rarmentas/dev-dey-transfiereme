# API de sesión

La sesión es la cookie de Django (sin JWT). El vendedor entra con correo y contraseña; el servidor no acepta comercio en el cuerpo del login.

## Cierre de `/api/` sin sesión

El middleware `CierraApiSinSesionMiddleware` responde `403` con `{"detail": "Debe iniciar sesión."}` a cualquier ruta bajo `/api/` si no hay cookie de sesión válida, **salvo** estas excepciones:

| Ruta / prefijo | Método | Motivo |
| --- | --- | --- |
| `/api/sesion/entrar/` | `POST` | Inicio de sesión |
| `/api/sesion/estado/` | Cualquiera | El propio endpoint devuelve `403` sin sesión |
| `/api/webhooks/` | Cualquiera | Avisos firmados de pey (sin login). La ruta concreta es `POST /api/webhooks/pey/` |
| `/api/salud/` | `GET` | Comprobación de despliegue y base de datos |

Cualquier otra ruta de la API (por ejemplo `POST /api/cobro/`) requiere sesión activa antes de ejecutar la vista.

| Método | Ruta | Autenticación |
|--------|------|----------------|
| `POST` | `/api/sesion/entrar/` | No requiere sesión previa |
| `POST` | `/api/sesion/salir/` | Sesión activa |
| `GET` | `/api/sesion/estado/` | Sesión activa |

## Webhook de pey

`POST /api/webhooks/pey/` no pide sesión ni CSRF. Verifica la firma Standard Webhooks sobre el cuerpo crudo con `PEY_WEBHOOK_SECRET`. Si el secreto está vacío o la firma no es válida, responde `401` con `{"detalle": "firma inválida"}` y no escribe nada. Un aviso legible responde `200` con `{"estado": ...}`: `aplicado`, `duplicado` (mismo `webhook-id`), `duplicado_transaccion`, `sin_cobro`, `transicion_invalida` o `tipo_desconocido`. La misma ruta recibe `codi.qr.payment_received` y `codi.pn.payment_received`.

## Entrar

Cuerpo JSON:

```json
{ "correo": "vendedor@ejemplo.mx", "contraseña": "su-clave" }
```

Respuesta `200`: `{ "usuario": "..." }`. Credenciales inválidas: `403` con `{"detail": "Revise el correo y la contraseña."}`.

## Estado

Respuesta `200` con `usuario`, `correo`, `nombre`, `apellidos` y `comercio` (`id`, `nombre` según su membresía, o `null` si no tiene). Sin sesión: `403`.

## Salir

Respuesta `200` con cuerpo vacío `{}`. Basta la cookie de sesión; no hace falta encabezado CSRF (la vista usa autenticación por sesión sin verificación CSRF en DRF). Tras salir, el estado vuelve a responder `403`.

## Movimientos (lectura, ámbito por sesión)

El servidor determina el comercio por membresía; no acepta `comercio` ni `comercio_id` en la cadena de consulta.

| Método | Ruta | Autenticación |
| --- | --- | --- |
| `GET` | `/api/movimientos/` | Sesión activa |
| `GET` | `/api/movimientos/tablero/` | Sesión activa |
| `GET` | `/api/movimientos/<id>/` | Sesión activa |

Sin sesión: `403` con `{"detail": "Debe iniciar sesión."}` (middleware, igual que el resto de `/api/`).

Listado `200`: arreglo JSON ordenado por fecha de creación descendente. Cada elemento incluye `id`, `monto` (cadena decimal), `concepto_visible`, `canal`, `estado`, `origen`, `creado_en` y `pagado_en` (`null` si todavía no está pagado). Solo aparecen movimientos del comercio de la sesión.

Detalle propio: `200` con el mismo objeto. Id de otro comercio o inexistente en su ámbito: `404` con `{"detail": "No encontrado."}` (no `403`).

Query con `comercio` o `comercio_id`: `400` con el mensaje de ámbito que indica que el servidor fija el comercio por membresía.

Usuario autenticado sin membresía: `403` con el mensaje de `SinAmbitoError`.

## Tablero

`GET /api/movimientos/tablero/` agrupa los movimientos pagados del comercio de la sesión. El ámbito es el del listado: sin sesión `403`, `comercio` o `comercio_id` en la query `400`, usuario sin membresía `403`.

Query opcional `desde` y `hasta` (`YYYY-MM-DD`, días de `America/Mexico_City`, inclusivos). Un formato distinto responde `400` con `{"detail": "Fecha inválida. Use YYYY-MM-DD."}`.

Respuesta `200`:

```json
{
  "zona": "America/Mexico_City",
  "confirmado": {"filas": [], "total": "0.00"},
  "desarrollo": {"filas": [], "total": "0.00"}
}
```

`confirmado` cuenta solo `origen_pey`. `desarrollo` cuenta solo `origen_desarrollo`. Esos totales no se suman entre sí.

Cada fila trae `dia` (`YYYY-MM-DD`), `canal`, `concepto` (concepto visible en minúsculas y con espacios colapsados; si queda vacío, `transferencia`), `etiqueta` (concepto visible del pago más reciente del grupo), `total` (cadena con dos decimales) y `cantidad`.

El día sale de `pagado_en` convertido a `America/Mexico_City`. Orden: día descendente, luego canal, luego concepto. Pendientes y vencidos no entran.

## Cuenta: captura de CLABE

El servidor persiste la CLABE en el comercio de la membresía; no acepta `comercio` ni `comercio_id` en el cuerpo. La respuesta no incluye secretos de plataforma (`PEY_API_KEY`, etc.).

| Método | Ruta | Autenticación |
| --- | --- | --- |
| `POST` | `/api/cuenta/clabe/` | Sesión activa |

Cuerpo JSON: `{ "clabe": "012180015826225713" }` (18 dígitos con dígito verificador válido).

Respuesta `200`: `{ "clabe": "<guardada>" }`. CLABE inválida: `400` con `{"detail": "Indique una CLABE válida de 18 dígitos."}`. Comercio en el cuerpo: `400` (ámbito). Sin sesión: `403` del middleware. Sin membresía: `403` con el mensaje de `SinAmbitoError`.

Tras guardar una CLABE válida, en la misma petición `POST /api/cuenta/clabe/` `GuardarClabeView` llama a `sincronizar_codi_status` antes de responder: el adaptador pey configurado actualiza el `codiStatus` persistido en `pey_codi_status` (`pending` / `active`; en desarrollo, sin red a pey). El alta de QR general usa `preparar_alta_qr_general`, que lee ese campo vía `cuenta_esta_active` y, si la cuenta no está activa, devuelve un error controlado. La respuesta del POST sigue siendo solo `{"clabe": ...}`; no expone secretos de plataforma.

## Semilla de desarrollo

Con `DEBUG` activo:

```bash
cd backend
.venv/bin/python manage.py sembrar_vendedor --contraseña 'una-clave-local'
```

Crea o actualiza `vendedor@demo.mx` en «Comercio demo», marca `semilla_active_dev` y no inserta movimientos. Al entrar, el listado de movimientos queda vacío. Esa marca no cuenta sola como cuenta ACTIVE: `cuenta_esta_active` solo acepta `pey_codi_status=active` tras sincronizar (en el adaptador de desarrollo, hace falta CLABE válida y `semilla_active_dev` para simular ACTIVE). Fuera de desarrollo el comando se niega. No hay alta pública.
