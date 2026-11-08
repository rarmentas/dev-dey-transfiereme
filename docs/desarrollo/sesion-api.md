# API de sesión

La sesión es la cookie de Django (sin JWT). El vendedor entra con correo y contraseña; el servidor no acepta comercio en el cuerpo del login.

## Cierre de `/api/` sin sesión

El middleware `CierraApiSinSesionMiddleware` responde `403` con `{"detail": "Debe iniciar sesión."}` a cualquier ruta bajo `/api/` si no hay cookie de sesión válida, **salvo** estas excepciones:

| Ruta / prefijo | Método | Motivo |
| --- | --- | --- |
| `/api/sesion/entrar/` | `POST` | Inicio de sesión |
| `/api/sesion/alta/` | `POST` | Alta pública (solicitar y confirmar código) |
| `/api/sesion/olvido/` | `POST` | Restablecimiento de contraseña por código |
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

`POST /api/webhooks/pey/` no pide sesión ni CSRF. Verifica la firma Standard Webhooks sobre el cuerpo crudo con `PEY_WEBHOOK_SECRET`. Si el secreto está vacío o la firma no es válida, responde `401` con `{"detalle": "firma inválida"}` y no escribe nada. Un aviso legible responde `200` con `{"estado": ...}`: `aplicado`, `duplicado` (mismo `webhook-id`), `duplicado_transaccion`, `sin_cobro`, `transicion_invalida` o `tipo_desconocido`. La misma ruta recibe `codi.qr.payment_received` y `codi.pn.payment_received`. En QR general, el `codiQrId` del aviso debe coincidir con el `pey_qr_id` del cobro persistido en el alta; el movimiento pagado se crea con ese aviso, no en el `POST /api/cobro/qr-general/`.

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

## Alta pública

Flujo en dos pasos. Los códigos son de seis dígitos, de un solo uso y caducan en 15 minutos. No exigen sesión ni CSRF (mismo patrón que `entrar`).

### Solicitar código

`POST /api/sesion/alta/solicitar/`

```json
{ "correo": "nuevo@ejemplo.mx", "contraseña": "su-clave" }
```

- Correo ya registrado: `400` con `{"detail": "Este correo ya tiene cuenta. Entre o restablezca su contraseña."}`
- Correo y contraseña válidos: `200` con `{"detail": "Enviamos un código a su correo. Revise su bandeja de entrada."}`

### Confirmar alta

`POST /api/sesion/alta/confirmar/`

```json
{ "correo": "nuevo@ejemplo.mx", "código": "123456" }
```

- Código válido: `200` con `{"detail": "Su cuenta quedó lista. Ya puede entrar."}`. Crea `User` (`username` = correo), un `Comercio` nuevo en estado pendiente (sin CLABE) y la `Membresia`.
- Código inválido o expirado: `403` con `{"detail": "El código no es válido o ya expiró. Solicite uno nuevo."}`

La cuenta demo `vendedor@demo.mx` y los usuarios de prueba existentes entran con `entrar` como antes; no hay comprobación global de correo confirmado en el login.

## Olvido de contraseña

### Solicitar código

`POST /api/sesion/olvido/solicitar/`

```json
{ "correo": "vendedor@ejemplo.mx" }
```

Siempre `200` con el mismo cuerpo:

```json
{ "detail": "Si existe una cuenta con ese correo, recibirá un código en breve." }
```

Solo se envía correo si el usuario existe; la respuesta no revela si el correo está registrado.

### Restablecer

`POST /api/sesion/olvido/restablecer/`

```json
{ "correo": "vendedor@ejemplo.mx", "código": "123456", "contraseña": "nueva-clave" }
```

- Código válido: `200` con `{"detail": "Su contraseña quedó actualizada. Ya puede entrar."}` (solo cambia la contraseña del usuario).
- Código inválido o expirado, correo sin cuenta o sin solicitud vigente: `403` con el mismo mensaje genérico de código que en la alta (sin importar si la contraseña nueva es débil; la validación de contraseña ocurre solo tras verificar el código).
- Contraseña que no cumple las reglas de Django: `403` con el mensaje de validación, **solo** cuando el código ya fue verificado correctamente.

## Movimientos (ámbito por sesión)

El servidor determina el comercio por membresía; no acepta `comercio` ni `comercio_id` en la cadena de consulta ni en el cuerpo.

| Método | Ruta | Autenticación |
| --- | --- | --- |
| `GET` | `/api/movimientos/` | Sesión activa |
| `GET` | `/api/movimientos/tablero/` | Sesión activa |
| `GET` | `/api/movimientos/<id>/` | Sesión activa |
| `PATCH` | `/api/movimientos/<id>/` | Sesión activa |

Sin sesión: `403` con `{"detail": "Debe iniciar sesión."}` (middleware, igual que el resto de `/api/`).

Listado `200`: arreglo JSON ordenado por fecha de creación descendente. Cada elemento incluye `id`, `monto` (cadena decimal), `concepto` (el enviado al pagador), `concepto_visible`, `canal`, `estado`, `origen`, `creado_en` y `pagado_en` (`null` si todavía no está pagado). Solo aparecen movimientos del comercio de la sesión.

Detalle propio: `200` con el mismo objeto. Id de otro comercio o inexistente en su ámbito: `404` con `{"detail": "No encontrado."}` (no `403`).

`PATCH` renombra solo el concepto visible de un movimiento `pagado`. Cuerpo: `{"concepto_visible": "Tortas"}`. Se guarda con `strip()`. Vacío o solo espacios: `400`. Más de 500 caracteres: `400`. Cualquier otro campo (`concepto`, `monto`, `estado`, …): `400`. Si no está pagado: `409` con `{"detail": "Solo se puede renombrar un movimiento cobrado."}`. La respuesta `200` es el movimiento. No cambia `concepto` ni el concepto del cobro, y no llama a pey. El tablero agrupa por el visible normalizado.

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

Tras guardar una CLABE válida, en la misma petición `POST /api/cuenta/clabe/` `GuardarClabeView` llama a `sincronizar_codi_status` antes de responder: el adaptador pey configurado actualiza el `codiStatus` persistido en `pey_codi_status` (`pending` / `active`; en desarrollo, sin red a pey). La respuesta del POST sigue siendo solo `{"clabe": ...}`; no expone secretos de plataforma.

## Cobro: alta QR general

El servidor crea o devuelve el QR general del comercio de la membresía; no acepta `comercio` ni `comercio_id` en el cuerpo. Antes de crear el cobro llama a `preparar_alta_qr_general`, que exige `pey_codi_status=active` (`cuenta_esta_active`). En desarrollo ese estado lo deja `sincronizar_codi_status`: hace falta CLABE válida y `semilla_active_dev`. La marca sola no alcanza. La respuesta no incluye secretos de plataforma.

| Método | Ruta | Autenticación |
| --- | --- | --- |
| `POST` | `/api/cobro/qr-general/` | Sesión activa |

Cuerpo JSON: `{}` (sin campos de negocio obligatorios).

Respuesta `201` en la primera alta: `{ "qr_string": "...", "pey_qr_id": "..." }`. Si el QR general ya existe para ese comercio, `200` con los mismos campos (sin volver a llamar a pey). Cuenta inactiva: `400` con `{"detail": "...", "tipo": "INVALID_STATE"}` y sin persistir cobro. Comercio en el cuerpo: `400` (ámbito). Sin sesión: `403` del middleware. Sin membresía: `403` con el mensaje de `SinAmbitoError`.

El alta no crea movimientos; los pagos sobre ese QR se registran vía webhook (historias posteriores).

## Alta de venta (QR)

`POST /api/ventas/` crea un cobro `qr_venta` pendiente y su movimiento. El comercio sale de la sesión; `comercio` o `comercio_id` en el cuerpo o en la cadena de consulta responden `400`.

| Método | Ruta | Autenticación |
| --- | --- | --- |
| `POST` | `/api/ventas/` | Sesión activa |

Cuerpo JSON: `monto` (cadena o número, por ejemplo `"0.01"`), `concepto` (opcional) y `referencia` (opcional). El monto tiene que ser mayor que 0, con hasta 2 decimales. Concepto vacío, en blanco o null se envía y se guarda como `Transferencia`. Referencia vacía o null se envía como `"0"`; si viene, tiene que ser numérica de 1 a 7 dígitos. Un cuerpo que no es JSON legible (entero enorme o exponente fuera de rango) responde `400`. El QR vence a los 600 segundos.

Respuesta `201`: `movimiento_id`, `cobro_id`, `canal` (`qr_venta`), `monto` (cadena con dos decimales), `concepto`, `estado` (`pendiente`), `vence_en`, `qr_string` y `origen`.

Sin sesión: `403` del middleware. Usuario sin membresía: `403`. Monto, referencia o concepto inválidos: `400`. Cuenta que no está ACTIVE: `409` con `{"detail": "La cuenta no está ACTIVE."}`. Si ya hay una venta pendiente vigente (QR de venta o notificación): `409` con `{"detail": "Ya hay una venta pendiente.", "movimiento_id", "canal", "vence_en"}`. Ese `detail` lo distingue del 409 de la cuenta. Un pendiente con `vence_en` nulo también bloquea y no se vence solo. Un pendiente de venta con `vence_en` ya cumplido (incluido el instante exacto) se marca `vencido` antes de llamar a pey, y la nueva venta sigue. El QR general no cuenta como venta y no bloquea. Un aviso de pago que llega después de ese vencido marca el movimiento `pagado`. Si pey no puede crear el cobro: `502` con `detail` (`pey no pudo crear el cobro.`), `tipo`, `request_id` y `puede_haberse_creado`; no queda cobro ni movimiento nuevo. La respuesta no incluye la API key.

El cobro guarda `pey_qr_id` y `qr_string`; `qr_string` también va en la respuesta del alta. La referencia se envía a pey como `numRef` y no se guarda en el movimiento.

`GET /api/ventas/<movimiento_id>/` devuelve el estado guardado de una venta del comercio de la sesión (`movimiento_id`, `canal`, `estado`, `monto`, `concepto`, `vence_en`, `pagado_en`, `qr_string`). `qr_string` sale del cobro y va vacío en una notificación. Otro comercio, un id inexistente o un canal que no es de venta (el QR general) responden `404`. `comercio` en la consulta responde `400`. Sin sesión: `403`. Si está `pendiente` y `vence_en` ya se cumplió, el servidor lo marca `vencido` antes de responder; `vence_en` nulo no vence. Esta consulta no llama a pey.

## Semilla de desarrollo

Con `DEBUG` activo:

```bash
cd backend
.venv/bin/python manage.py sembrar_vendedor --contraseña 'una-clave-local'
```

Crea o actualiza `vendedor@demo.mx` en «Comercio demo», marca `semilla_active_dev` y no inserta movimientos. Al entrar, el listado de movimientos queda vacío. Esa marca no cuenta sola como cuenta ACTIVE: `cuenta_esta_active` solo acepta `pey_codi_status=active` tras sincronizar (en el adaptador de desarrollo, hace falta CLABE válida y `semilla_active_dev` para simular ACTIVE). Fuera de desarrollo el comando se niega. El alta público por correo es independiente de este comando.

Con `DEBUG` activo, `manage.py sembrar_movimientos_demo` (correo por defecto `vendedor@demo.mx`) crea unos doce movimientos `origen_desarrollo` con cobros `demo-` para ver el tablero sin pey; sin `--reset` no duplica y `--reset` borra solo esos demo de ese comercio.
Fuera de `DEBUG` el comando se niega. Esos pagos aparecen solo en la sección de desarrollo, sin sumarse a lo confirmado.
