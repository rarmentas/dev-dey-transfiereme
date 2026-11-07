# Cody

**Cobro CoDi en un paso: el comercio dicta o escribe el monto y el cliente paga por QR o notificación push.**

Proyecto para el **DevDay Exchange Community Hackathon CDMX** (7 de noviembre de 2026, UTOPÍA Elena Poniatowska, Coyoacán). Organizan AI Builders México, UTOPÍAS, SEDECO y pey.

Reto: construir con OpenAI y CoDi usando la API abierta de pey. Documentación: [https://docs.pey.mx](https://docs.pey.mx).

> **Estado: propuesta, sin implementar.** Este repositorio solo contiene este README. No hay aplicación, endpoints, agente ni resultados. Lo descrito abajo es el plan del día. Donde algo aún no existe, está marcado como **pendiente**.

Nombre tentativo: **Cody**. Se puede cambiar durante el hackatón.

## Problema

Cobrar con CoDi sigue pidiendo demasiados pasos dentro de la app del banco, y el efectivo sigue dominando los pagos chicos.

Datos de contexto (sin métricas propias del proyecto):

- Según *Mexico Business News* (28 de septiembre de 2026), CoDi tiene **23.2 millones de cuentas validadas**, frente a una meta de **37 millones**.
- Métricas de Banxico sobre la experiencia en la app del banco: encontrar CoDi toma **1–2 toques**, generar un cobro **2–4 toques** y pagar escaneando un QR **2–3 toques**.
- Solo **25 de 48** instituciones con transferencias móviles ofrecen CoDi.
- La ENIF 2024 del INEGI indica que el **85%** de las compras de **$500 o menos** se pagan en efectivo.
- La Circular 9/2026 de Banxico obliga a homologar la experiencia de transferencias y CoDi en móvil para el **14 de diciembre de 2026**.

Cody apunta a esa fricción: que el comercio no tenga que recorrer menús del banco para armar un cobro.

## Solución propuesta

**Pendiente de implementación.**

El comercio cobra en un solo paso. Dicta o escribe el monto (y, si hace falta, un concepto breve). Un agente de OpenAI, con *function calling*, llama a la API de pey y genera el cobro CoDi de una de estas dos formas:

- **QR**, para que el cliente lo escanee.
- **Notificación push** (*payment notification*), para enviarlo a la app del banco del cliente.

La confirmación de pago llega por webhooks de pey:

- `codi.qr.payment_received`
- `codi.pn.payment_received`

La voz queda como **opcional y pendiente**: el comercio podría dictar el monto en lugar de escribirlo, con el mismo mecanismo de dent-intec (faster-whisper y Kokoro o Piper).

## Flujo de usuario

**Pendiente de implementación.** Recorrido previsto:

1. El comercio abre Cody e indica el monto, por texto o por voz.
2. El agente confirma monto y concepto, y elige el canal: QR o notificación push.
3. Cody pide a pey el cobro y muestra el QR, o envía la notificación al cliente.
4. El cliente paga desde su app bancaria (escanea el QR o acepta la notificación).
5. pey avisa a Cody con `codi.qr.payment_received` o `codi.pn.payment_received`.
6. Cody muestra al comercio que el pago se recibió.

Si el pago no llega, la pantalla se queda en espera. No hay lógica de reintento, cancelación ni conciliación: eso está **pendiente**.

## Arquitectura

**Pendiente de implementación.** Diseño previsto:

```text
Comercio (texto o voz)
        │
        ▼
Agente LangGraph (Ollama u OpenAI)
  herramientas del grafo
        │
        ├── POST /codi/qr     → cobro por QR
        ├── POST /codi/pn     → cobro por notificación push
        └── links de pago     → alternativa de cobro
        │
        ▼
pey  ──webhooks──►  Cody
     codi.qr.payment_received
     codi.pn.payment_received
        │
        ▼
Confirmación en pantalla para el comercio
```

- **Agente:** LangGraph dentro de Django. El modelo no arma el mensaje CoDi a mano: el grafo llama herramientas que hablan con pey. El proveedor es Ollama u OpenAI (`LLM_SERVER`).
- **pey:** `POST /codi/qr`, `POST /codi/pn` y links de pago, según [docs.pey.mx](https://docs.pey.mx). El contrato exacto de cada endpoint se toma de esa documentación; este README no lo reproduce.
- **Webhooks:** un endpoint propio (**pendiente**) recibe `codi.qr.payment_received` y `codi.pn.payment_received` y actualiza el estado del cobro.

La voz, si se alcanza, usa el mismo camino opcional que dent-intec (faster-whisper y Kokoro o Piper) y entra al mismo agente. No cambia los endpoints de pey.

## Stack

Cody usa la misma plataforma que dent-intec: Flutter (web y Android), Django 6 + DRF, Postgres 17, sesión por cookie, Gunicorn y LangGraph. El detalle y las versiones están en [docs/stack-tecnologico](docs/stack-tecnologico/README.md). BMAD no entra.

Nada de eso está instalado en este repositorio todavía.

| Capa | Elección |
| --- | --- |
| App | Flutter (web y Android) |
| API | Django 6 + Django REST Framework, Python 3.12 |
| Datos | PostgreSQL 17 |
| Agente | LangGraph (`LLM_SERVER=ollama` o `openai`), con herramientas |
| Voz (opcional) | faster-whisper y Kokoro o Piper, como en dent-intec |
| Cobros | API de pey (`/codi/qr`, `/codi/pn`, links de pago) |
| Confirmación | Webhook en el mismo Django |

## Cómo correrlo

**Pendiente.** Aún no hay código, `package.json` ni servidor. Cuando exista la app, el arranque previsto es:

1. Clonar este repositorio e instalar dependencias (**pendiente**: aún no hay `backend/requirements.txt` ni `frontend/pubspec.yaml`; el stack ya está fijado en [docs/stack-tecnologico](docs/stack-tecnologico/README.md)).
2. Crear un archivo `backend/.env` (no se incluye en el repo) con:

```bash
PEY_API_KEY=tu_llave_de_pey
LLM_SERVER=openai
OPENAI_API_KEY=tu_llave_de_openai
# URL pública para que pey entregue los webhooks. Pendiente de definir.
WEBHOOK_BASE_URL=https://tu-tunel-o-dominio.example
```

3. Levantar la app en local (**pendiente**: no hay comando de arranque definido) y exponer la ruta de webhooks con un túnel si pey debe alcanzar la máquina.

Sustituye los placeholders por llaves reales. No subas esas llaves al repositorio.

## Nota de pruebas

pey se prueba en **producción**. Usar montos de **$0.01**.

No hay suite de pruebas, cobros de ejemplo ni registro de pagos de este proyecto: **pendiente**.

## Roadmap del día del hackatón

Plan del 7 de noviembre de 2026. Ningún bloque está hecho.

| Bloque | Qué se busca | Estado |
| --- | --- | --- |
| 1 | Llaves, lectura de [docs.pey.mx](https://docs.pey.mx) y un `POST /codi/qr` de $0.01 | Pendiente |
| 2 | Agente con *function calling* que arme ese cobro a partir de un monto escrito | Pendiente |
| 3 | `POST /codi/pn` y pantalla de espera | Pendiente |
| 4 | Webhooks `codi.qr.payment_received` y `codi.pn.payment_received` | Pendiente |
| 5 | Links de pago, si queda tiempo | Pendiente |
| 6 | Voz con faster-whisper (opcional) | Pendiente |
| 7 | Demo de punta a punta con un cobro de $0.01 | Pendiente |

## Equipo

**Pendiente.** Completar el día del hackatón.

| Rol | Nombre |
| --- | --- |
| Por definir | Por definir |
| Por definir | Por definir |
| Por definir | Por definir |
