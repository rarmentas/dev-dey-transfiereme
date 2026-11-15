# Evidencia de Fase 1 — entrega 3.6

Este documento es una plantilla: no acredita una ejecución ni un despliegue. Registrar
fecha, responsable y pruebas observadas sin nombres, teléfonos, CLABE completa,
credenciales, capturas de mensajes privados ni cuerpos de webhooks. Los estados de
abajo son conservadores y se actualizan solo con evidencia verificable.

## Preparación del tendero y del pagador

1. Usar una cuenta demo registrada y **ACTIVE** en pey, seleccionada como predeterminada;
   comprobar que coincide con el destino permitido de demo. La validación de una CLABE
   no demuestra titularidad ni activación. Confirmar modo demo y política coherentes
   en todos los procesos; el importe efectivo debe ser **MXN 0.01**.
2. Confirmar sesión del comercio correcto, canal de WhatsApp operativo y consentimiento
   de los participantes. El tendero revisa artículos, cantidades y precios; el cliente
   acepta la revisión vigente antes de solicitar el cobro.
3. Para QR, presentar el código en un dispositivo y escanearlo con la aplicación
   bancaria en otro. Para push, confirmar por separado con el pagador el número
   bancario, sin asumir que es el número de WhatsApp ni registrarlo en la evidencia.
4. El pagador verifica el importe y autoriza en su banco. Solo un webhook pey firmado,
   correlacionado y aplicado acredita el pago; una captura o un mensaje no bastan.
   El tendero marca después listo y entregado.

## Guion: texto y voz

Ejecutar ambos recorridos consecutivamente; al menos uno requiere pago real verificado.
Si el otro se detiene antes, registrar su estado real sin llamarlo pagado.

1. **Texto:** el cliente envía un pedido por WhatsApp. El tendero revisa un artículo o
   cantidad, corrige lo necesario y publica la cotización. El cliente revisa el resumen
   y acepta expresamente esa revisión por texto. Solicitar el cobro y seguir el pago,
   listo y entrega; registrar los IDs y tiempos.
2. **Voz:** enviar una nota de voz real. Verificar descarga y transcripción sin grabar
   contenido personal; revisar y corregir un producto o cantidad antes de publicar.
   El cliente acepta por texto el resumen vigente. Continuar con cobro y estados si
   están habilitados; registrar dónde terminó. La transcripción no autoriza el cobro.
3. Si se cambia una cotización ya aceptada, publicar otra y obtener nueva aceptación
   antes de cobrar. Un artículo sin precio o existencia conocida queda en revisión;
   nunca inventar el total. Probar audio inválido o vacío y comprobar alternativa de
   texto sin iniciar cobro ni perder un pedido válido.

## Registro de evidencia

Ejecutar desde `backend`: `python manage.py evidencia_fase1 --pedido <uuid>`. La salida
JSON es de lectura y muestra únicamente la cadena persistida, estados y fechas; los
identificadores externos que puedan contener números sensibles se omiten. Anotar
manualmente la revisión desplegada y la procedencia del adaptador: el comando no puede
demostrar por sí solo que pey sea real. Verificar la evidencia antes de compartirla.

| Dato | Texto | Voz |
|---|---|---|
| Fecha y responsable, sin datos personales | | |
| Mensaje de origen | | |
| Pedido | | |
| Revisión de cotización | | |
| Aceptación y mensaje de consentimiento | | |
| Intento y estado | | |
| Cobro | | |
| Movimiento y estado | | |
| Transacción | | |
| webhook-id y resultado verificado | | |
| evento_id de pago y eventos de entrega | | |
| Cuenta enmascarada | | |
| Revisión desplegada / SHA | | |
| Adaptador usado y evidencia de pey real o simulación | | |
| Momento de cada paso y resultado observado | | |

Si falta un dato, escribir «no observado», no inferirlo. Si el comando omite un ID,
conservar la correspondencia en un registro operativo protegido sin incluir datos
personales en esta entrega.

## Checklist de aceptación

Los estados describen la evidencia disponible para esta entrega, no una certificación
funcional del código. `parcial` indica que falta ejecución o comprobación de extremo a
extremo; `no cumplido` indica que aún no se ha demostrado el resultado exigido.

| AC | Comprobación | Estado honesto |
|---|---|---|
| AC1-01 | Texto, comercio correcto, aceptación y pago real con webhook verificado | no cumplido |
| AC1-02 | Audio real, transcripción, corrección y recorrido; pago real en al menos uno | no cumplido |
| AC1-03 | Audio inválido, vacío o fuera de límite ofrece alternativa sin perder pedido | parcial |
| AC1-04 | Artículo sin precio o existencia queda en revisión, sin total inventado | parcial |
| AC1-05 | Cambio de cotización aceptada exige nueva aceptación | parcial |
| AC1-06 | Repeticiones de entrada, aceptación y webhook no duplican; cotejar IDs | parcial |
| AC1-07 | Pago al pedido y destino correctos; incertidumbre sin reintento ciego | parcial |
| AC1-08 | Segundo pedido espera identificable ante cobro pendiente | parcial |
| AC1-09 | Pagado, listo y entregado distintos; tendero confirma entrega | parcial |
| AC1-10 | Dos recorridos consecutivos, pago real, grabación y entrega documentada | no cumplido |
| AC1-11 | Dueño guarda y lista dos cuentas aisladas; conserva cuenta previa | parcial |
| AC1-12 | CLABE válida de 18 dígitos, ceros iniciales y rechazo de duplicados | parcial |
| AC1-13 | Solo cuenta propia registrada y ACTIVE puede ser predeterminada única | parcial |
| AC1-14 | Cobro nuevo usa y fija cuenta predeterminada activa; no elige otra | parcial |
| AC1-15 | Cambio de predeterminada no reasigna cobros históricos ni webhooks | parcial |
| AC1-16 | Estado, sincronización e incertidumbre independientes por cuenta | parcial |

Pendientes de infraestructura: cuenta demo ACTIVE en pey, WAHA con número real,
modelo STT instalado en servidor y cobro habilitado allí. Ninguno se presume verificado.
Para cambiar un estado, adjuntar referencia de prueba, fecha, SHA y resultado observado.

## Matriz de alcance

| Fase 0 previa | Fase 1 nueva |
|---|---|
| Cobro y tablero del comercio | Pedido ligado a aceptación, intento, cobro y webhook |
| Cuenta de cobro única | Cuentas por comercio y destino histórico por intento |
| Canal de texto y revisión | Texto y voz con corrección y aceptación explícita |
| Estado financiero | Pago, preparación y entrega diferenciados |

## Límites y resolución de incertidumbre

- Un solo cobro vivo por comercio: otros pedidos esperan; no es una prueba de
  concurrencia. No existe cancelación bancaria desde esta solución.
- Voz en CPU: puede tardar; depende de modelo local y recursos disponibles. WAHA es
  una integración no oficial y su sesión o soporte de media pueden fallar.
- Un intento `incierto` bloquea nuevos envíos hasta resolverlo. Investigar con evidencia
  del proveedor: `manage.py resolver_intento --intento <uuid> --accion sin_cobro
  --confirmar` solo tras acreditar que no hubo cobro; o `--accion enlazar` con
  `--qr-id` o `--transaction-id` según el canal y `--confirmar` si existe. Enlazar
  no confirma el pago: se requiere webhook verificado. Nunca reenviar a ciegas.
- Un registro de cuenta incierto requiere identificar el registro real en pey;
  `manage.py enlazar_cuenta_pey --cuenta <uuid> --pey-id <id>` consulta y coteja
  la cuenta antes de enlazar. No repetir el alta a ciegas. Estos comandos son acciones
  operativas, no forman parte de la extracción de evidencia de solo lectura.

## Plantilla de video (máximo 3 minutos)

- 0:00–0:20: alcance, SHA y aclaración de adaptador real o simulado.
- 0:20–1:00: pedido de texto, corrección y aceptación vigente.
- 1:00–1:40: nota de voz, transcripción, corrección y aceptación.
- 1:40–2:25: cobro de 0.01, resultado bancario y webhook verificado; si no ocurrió,
  mostrar el punto de interrupción y decirlo expresamente.
- 2:25–3:00: listo y entregado, IDs enmascarados, límites y pendientes.

Revisar la grabación antes de compartirla para retirar secretos y datos personales.

## Contingencias y prerrequisitos de servidor

Antes de la demo verificar cuenta demo ACTIVE y destino permitido; núcleo real, pey de
producción y modo/política comunes; firmas pey y WAHA; WAHA con número real y soporte
de media con origen coincidente; ffmpeg/ffprobe, venv STT y modelo precargado local;
capacidad CPU/memoria; migraciones y latidos recientes de web, canal, cobros y STT.
El responsable habilita el cobro en el servidor solo tras estas comprobaciones y
reinicio coordinado; hasta entonces permanece cerrado. Validar con pago de 0.01 y
webhook firmado. No registrar valores de variables ni credenciales.

Variables nuevas, solo nombres: `STT_HABILITADO`, `STT_MODELO`, `STT_CPU_THREADS`,
`CODY_ROL`, `HF_HOME`, `HF_HUB_OFFLINE`, `WHATSAPP_DOWNLOAD_MEDIA`,
`WHATSAPP_FILES_LIFETIME`, `WAHA_BASE_URL` (contenedor WAHA).

Si falla audio o su capacidad amenaza el pago, deshabilitar STT, ofrecer texto y marcar
AC1-02 como no cumplido. Si WAHA falla, registrar el corte y no atribuirle un mensaje
real. Si cuenta, cobro o webhook no están verificados, mantener cerrado el cobro o
mostrar el recorrido hasta el punto alcanzado. Si hay incertidumbre, detener y resolver
como se indica arriba. Una simulación se identifica como simulación: **nunca se
presenta como producción ni como pago real**.
