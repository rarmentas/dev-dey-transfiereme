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
| `GET` | `/api/movimientos/<id>/` | Sesión activa |

Sin sesión: `403` con `{"detail": "Debe iniciar sesión."}` (middleware, igual que el resto de `/api/`).

Listado `200`: arreglo JSON ordenado por fecha de creación descendente. Cada elemento incluye `id`, `monto` (cadena decimal), `concepto_visible`, `canal`, `estado`, `origen` y `creado_en`. Solo aparecen movimientos del comercio de la sesión.

Detalle propio: `200` con el mismo objeto. Id de otro comercio o inexistente en su ámbito: `404` con `{"detail": "No encontrado."}` (no `403`).

Query con `comercio` o `comercio_id`: `400` con el mensaje de ámbito que indica que el servidor fija el comercio por membresía.

Usuario autenticado sin membresía: `403` con el mensaje de `SinAmbitoError`.
