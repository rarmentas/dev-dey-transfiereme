# Cody

**Capa de cobro CoDi para el pequeño comercio: un QR general en el local, un QR por venta, y un tablero que agrupa lo cobrado.**

Proyecto para el **DevDay Exchange Community Hackathon CDMX** (7 de noviembre de 2026, UTOPÍA Elena Poniatowska, Coyoacán). Organizan AI Builders México, UTOPÍAS, SEDECO y pey.

Reto: construir con CoDi usando la API abierta de pey. Documentación: [https://docs.pey.mx](https://docs.pey.mx). Base: `https://api.pey.mx`.

> **Estado: scaffold local en desarrollo.** Ya hay backend Django, app Flutter (web y Android) y arranque local documentado. El cobro con pey, sesión del vendedor y tablero siguen **pendientes** en MR posteriores.

Nombre tentativo: **Cody**. Se puede cambiar durante el hackatón.

## Problema

Cobrar con CoDi sigue pidiendo demasiados pasos dentro de la app del banco, y el efectivo sigue dominando los pagos chicos.

Datos de contexto (sin métricas propias del proyecto):

- Según *Mexico Business News* (28 de septiembre de 2026), CoDi tiene **23.2 millones de cuentas validadas**, frente a una meta de **37 millones**.
- Métricas de Banxico sobre la experiencia en la app del banco: encontrar CoDi toma **1–2 toques**, generar un cobro **2–4 toques** y pagar escaneando un QR **2–3 toques**.
- Solo **25 de 48** instituciones con transferencias móviles ofrecen CoDi.
- La ENIF 2024 del INEGI indica que el **85%** de las compras de **$500 o menos** se pagan en efectivo.
- La Circular 9/2026 de Banxico obliga a homologar la experiencia de transferencias y CoDi en móvil para el **14 de diciembre de 2026**.

Cody apunta a esa fricción desde el lado del proveedor: el pequeño comercio cobra sin recorrer los menús de su banco.

## Alcance

La app es del **vendedor**, en pequeños comercios. El alcance es la **capa de cobro**. El punto de venta (inventario, ticket, caja) queda fuera por ahora, para no complicar la operación del día.

## Solución propuesta

**Pendiente de implementación.**

El vendedor tiene dos QR:

- **QR general.** Se publica en el establecimiento. Quien quiera pagar directo lo lee con su app bancaria y teclea el monto. El vendedor no arma esa venta.
- **QR por venta.** Se crea en cada cobro. El vendedor captura el monto y, si quiere, un concepto y una referencia. Cody pide el cobro a pey y muestra el QR. El cliente lo lee con su app bancaria, lo acepta por NFC, o el vendedor pide el número y manda el cobro por notificación push.

pey confirma el abono con webhooks:

- `codi.qr.payment_received`
- `codi.pn.payment_received`

Con esos cobros, Cody arma un **resumen de ventas** y un **tablero** que agrupa lo cobrado por concepto, día y canal (QR general, QR por venta, notificación).

### Concepto por defecto: "Transferencia"

Todo cobro sin concepto queda como **"Transferencia"**:

- El QR general siempre lleva "Transferencia", porque el vendedor no arma esa venta.
- En un QR por venta o una notificación, si el vendedor deja el concepto vacío, Cody manda "Transferencia".

Como en una app bancaria, el vendedor puede **renombrar el concepto de un movimiento** después de cobrado (por ejemplo, "Transferencia" → "Tortas"). El cambio vive solo en Cody: el concepto que vio el pagador y que registró pey no cambia. El tablero agrupa con el concepto vigente.

## Flujo de usuario

**Pendiente de implementación.** Recorrido previsto:

1. El vendedor abre Cody.
2. Muestra el QR general ya publicado, o arma una venta: monto obligatorio, concepto y referencia opcionales.
3. En la venta, el cliente paga de una de estas formas: lee el QR con su app, acerca el teléfono (NFC) o recibe una notificación en el número que dio el vendedor.
4. pey avisa a Cody con `codi.qr.payment_received` o `codi.pn.payment_received`.
5. El resumen lista el movimiento con su concepto ("Transferencia" si no tenía) y el tablero actualiza los totales.
6. Si quiere, el vendedor abre el movimiento y cambia el concepto.

Si el pago no llega, la pantalla se queda en espera hasta que el cobro expira. No hay lógica de reintento, cancelación ni conciliación: eso está **pendiente**.

## Arquitectura

**Pendiente de implementación.** Las cinco épicas de cobro comparten primero el contrato de movimientos y cobros descrito en [docs/stack-tecnologico/000-stack.md](docs/stack-tecnologico/000-stack.md#contrato-transversal-de-movimientos-y-cobros) (sin épica aparte). Diseño previsto:

```text
Vendedor (QR general o venta: monto, concepto, referencia)
        │
        ▼
Cody
  ├── QR general publicado en el local   (POST /codi/qr, amount 0, sin expiración)
  ├── POST /codi/qr   → QR de esa venta (el cliente lo lee o lo acepta por NFC)
  └── POST /codi/pn   → cobro al número del cliente
        │
        ▼
pey  ──webhooks──►  Cody
     codi.qr.payment_received
     codi.pn.payment_received
        │
        ▼
Resumen de ventas y tablero
  agrupado por concepto (editable), día y canal
```

- **Cobro:** la app llama la API de pey (`https://api.pey.mx`). `POST /codi/qr` arma el QR de la venta y el QR general. `POST /codi/pn` manda la notificación al celular. El NFC lo resuelve la app bancaria del cliente sobre ese mismo cobro; pey no tiene un endpoint de NFC. El contrato verificado está en [docs/stack-tecnologico](docs/stack-tecnologico/000-stack.md#cobros-api-de-pey).
- **Webhooks:** un endpoint propio (**pendiente**) recibe `codi.qr.payment_received` y `codi.pn.payment_received`, verifica la firma y marca el cobro como pagado.
- **Espera en pantalla:** la app consulta a Django cada pocos segundos; Django responde con lo que llegó por webhook y, como respaldo, con `GET /transaction/...` de pey.
- **Tablero:** suma por concepto normalizado (minúsculas, sin espacios sobrantes), día y canal. Es una consulta a Postgres.

## Stack

Cody usa la misma plataforma que dent-intec: Flutter (web y Android), Django 6 + DRF, Postgres 17, sesión por cookie y Gunicorn, más la API de pey para el cobro. El detalle y las versiones están en [docs/stack-tecnologico](docs/stack-tecnologico/000-stack.md). BMAD no entra.

En este repositorio ya está el **scaffold local** del stack (Flutter web/Android, Django 6 + DRF, Postgres 17 en Docker). Cobro con pey, sesión del vendedor y tablero **aún no** están implementados.

| Capa | Elección |
| --- | --- |
| App | Flutter (web y Android) |
| API | Django 6 + Django REST Framework, Python 3.12 |
| Datos | PostgreSQL 17 |
| Cobros | API de pey (`https://api.pey.mx`: `POST /codi/qr`, `POST /codi/pn`) |
| Confirmación | Webhook en el mismo Django, firmado con Standard Webhooks |

## Cómo correrlo

Requisitos: Docker, Python 3.12, Flutter 3.47.x (ver [stack](docs/stack-tecnologico/000-stack.md)).

1. Clonar el repositorio.
2. Ejecutar `./scripts/upgrade.sh` (venv en `backend/.venv`, dependencias y `flutter pub get`).
3. Copiar `backend/.env.example` a `backend/.env` y ajustar valores **locales** (sin credenciales de pey; véase [variables de entorno](docs/desarrollo/variables-entorno.md)).
4. Ejecutar `./scripts/dev-start.sh` (incluye Postgres vía Compose en el puerto **5433**, migraciones, Django, Flutter web y proxy). Cuando el script confirme la API, use **http://127.0.0.1:8000** (origen único). Prueba: `curl http://127.0.0.1:8000/api/salud/`. La primera vez, Flutter puede seguir compilando unos minutos aunque la API ya responda.

En GitLab, `PROD_ENV_FILE` (`master`) y `TEST_ENV_FILE` (rama `test`) son el `.env` de la app, con `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `PEY_API_KEY` y `PEY_WEBHOOK_SECRET` dentro. El deploy usa otras variables, que no van en ese archivo: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT`, `DEPLOY_PATH` y `SSH_PRIVATE_KEY` (base64), con prefijo `PROD_` o `TEST_`. Lista en [variables de entorno](docs/desarrollo/variables-entorno.md).

## Nota de pruebas

pey se prueba en **producción** (el ambiente de pruebas de pey todavía no está disponible). Usar montos de **$0.01**; lo que se paga no se devuelve.

Pruebas **acotadas** del scaffold: `manage.py check`, `manage.py test config.tests`, `flutter analyze` y un smoke test en `frontend/test/widget_smoke_test.dart`. Cobros reales con pey, integración de punta a punta y registro de pagos: **pendiente**.

## Roadmap del día del hackatón

Plan del 7 de noviembre de 2026. Ningún bloque está hecho.

| Bloque | Qué se busca | Estado |
| --- | --- | --- |
| 1 | Llaves, túnel, webhook registrado en el portal y un `POST /codi/qr` de $0.01 | Pendiente |
| 2 | QR general para publicar en el local (`amount: 0`, concepto "Transferencia") | Pendiente |
| 3 | QR por venta: monto, concepto y referencia opcionales | Pendiente |
| 4 | `POST /codi/pn` al número del cliente, y espera del pago (QR, NFC o notificación) | Pendiente |
| 5 | Webhooks `codi.qr.payment_received` y `codi.pn.payment_received` con firma verificada | Pendiente |
| 6 | Resumen de ventas, edición del concepto y tablero por concepto, día y canal | Pendiente |
| 7 | Demo de punta a punta con un cobro de $0.01 | Pendiente |

## Equipo

**Pendiente.** Completar el día del hackatón.

| Rol | Nombre |
| --- | --- |
| Por definir | Por definir |
| Por definir | Por definir |
| Por definir | Por definir |
