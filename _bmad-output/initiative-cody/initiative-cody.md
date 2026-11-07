---
tracker_id: ""
type: initiative
title: "El pequeño comercio cobra con CoDi sin recorrer los menús de su banco"
sources:
  - README.md
  - docs/stack-tecnologico/000-stack.md
  - docs/flujos-de-trabajo/flujo-codi-actual.md
  - _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md
companions:
  - docs/stack-tecnologico/000-stack.md
  - docs/flujos-de-trabajo/flujo-codi-actual.md
risk: high
---

# El pequeño comercio cobra con CoDi sin recorrer los menús de su banco

## Description

transfiereme es la capa de cobro CoDi del vendedor en un pequeño comercio que hoy cobra en efectivo. Hoy ese cobro se arma dentro de la app del banco. Al terminar, el vendedor publica un QR en el local o arma una venta, el cliente paga desde su banco, pey avisa el abono y transfiereme muestra el resumen y el tablero. El repositorio todavía no tiene aplicación: este ticket fija qué es verdad cuando exista.

## Outcome

Para el vendedor de un pequeño comercio, cobrar con CoDi deja de pasar por los menús de su banco; la señal es un cobro real de $0.01 que queda agrupado en el tablero.

## Requirements

- R1 (README.md, Solución propuesta; docs/stack-tecnologico/000-stack.md, POST /codi/qr; _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): El vendedor tiene en el local un QR general, creado una vez por comercio, sin vencimiento y sin tope de pagos. Ya impreso, cobra sin abrir transfiereme. El cliente, que ya tiene CoDi, lo lee en su banco, teclea el monto y ve el concepto "Transferencia". Sobre ese QR no hay notificación, y el vendedor no arma esa venta. Se cumple cuando un segundo pago sobre ese mismo QR aparece como otro movimiento, con el monto que tecleó el cliente, y el QR sigue abierto sin haber abierto la app para ese cobro.
- R2 (README.md, Solución propuesta; docs/stack-tecnologico/000-stack.md, POST /codi/qr): El vendedor arma un cobro por venta con monto obligatorio y, si quiere, concepto y referencia. La referencia solo se acepta si trae de 1 a 7 dígitos. El concepto vacío sale como "Transferencia" y el cobro vence. Si pey rechaza el alta, el vendedor ve el error y no queda un movimiento pagado. Se cumple cuando el cliente puede leer el QR de esa venta y una referencia inválida no se envía.
- R3 (README.md, Flujo de usuario; docs/stack-tecnologico/000-stack.md, POST /codi/pn; _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): En una venta hay un solo canal vivo: el QR o la notificación a un celular de 10 dígitos con monto mayor a cero. El otro aparece solo cuando el primero venció sin pago; antes, la pantalla no lo ofrece. El acercamiento lo hace la app del cliente sobre el QR y no abre un canal propio. Se cumple cuando, con el primer canal pendiente, el otro no se puede elegir, y tras vencer sin pago sí se puede.
- R4 (README.md, Flujo de usuario; docs/stack-tecnologico/000-stack.md, Webhooks y Espera del pago en pantalla): pey avisa el abono con codi.qr.payment_received o codi.pn.payment_received. transfiereme acepta el aviso solo con firma válida, lo aplica una vez y lo cuelga del QR o de la notificación que lo originó. El aviso de la notificación se liga con el identificador de transacción que pey devolvió al crear ese cobro. La pantalla muestra pagado sin recargar cuando el aviso ya está guardado y, si aún no llegó, transfiereme puede consultar el estado a pey. Sin aviso ni pago, el cobro queda vencido al expirar. Se cumple cuando un aviso repetido no duplica el movimiento y un cobro sin pago pasa a vencido.
- R5 (README.md, Concepto por defecto; docs/stack-tecnologico/000-stack.md, Concepto editable): El vendedor puede renombrar el concepto de un movimiento ya cobrado. El tablero usa el concepto nuevo. El que vio el pagador y el que guardó pey siguen igual. Se cumple cuando, tras cambiar "Transferencia" por otro nombre, el tablero agrupa por el nuevo y el concepto enviado a pey no cambia.
- R6 (README.md, Solución propuesta; docs/stack-tecnologico/000-stack.md, Concepto editable): El resumen lista cada movimiento y el tablero suma lo cobrado por concepto vigente, por día y por canal (QR general, QR por venta, notificación). Dos conceptos que solo se distinguen por mayúsculas o espacios sobrantes cuentan como uno. Se cumple cuando dos cobros del mismo concepto, día y canal se ven juntos y un canal distinto no se mezcla.
- R7 (docs/stack-tecnologico/000-stack.md, Sesión): El vendedor entra con su sesión y solo ve los cobros de su comercio. Se cumple cuando, sin sesión, no puede consultarlos y, con la sesión de otro comercio, ese cobro no se encuentra.

## Constraints

- C1 (docs/stack-tecnologico/000-stack.md, Capas y Sesión): La app es Flutter para web y Android, el API es Django 6 con DRF sobre Python 3.12, los datos son Postgres 17 y la sesión es la cookie de Django. Ese stack se mantiene, sin JWT y sin iOS. Versiones y paquetes están en el companion de arquitectura.
- C2 (docs/stack-tecnologico/000-stack.md, Cobros y Pruebas): El cobro y la consulta de respaldo van a la API de producción de pey. El ambiente de pruebas no está disponible. Cada pago de prueba es real, de $0.01, y no se devuelve. La cuenta que recibe tiene que estar activa.
- C3 (README.md, Alcance; docs/flujos-de-trabajo/flujo-codi-actual.md): transfiereme cubre el tramo del vendedor. La autorización del cliente en su banco y el abono por SPEI siguen en ese otro tramo.
- C4 (README.md, Flujo de usuario): Reintento, cancelación y conciliación quedan fuera de este alcance.
- C5 (docs/stack-tecnologico/000-stack.md, Sesión): El comercio lo determina el servidor según la membresía. La petición no elige el ámbito.
- C6 (docs/stack-tecnologico/000-stack.md, Capas): El día del tablero se cuenta en America/Mexico_City y la app está en español.
- C7 (docs/stack-tecnologico/000-stack.md, Webhooks y Datos y secretos): Cada API key tiene un solo webhook. La misma ruta recibe los dos avisos, verifica la firma sobre el cuerpo crudo y responde enseguida. La API key y el secreto no se suben al repositorio.
- C8 (docs/stack-tecnologico/000-stack.md, POST /codi/qr; _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): El QR se dibuja en la app con la cadena que devuelve pey, sin pedirle la imagen. Esa cadena es el mensaje CoDi, no una URL que abra el banco.
- C9 (docs/stack-tecnologico/000-stack.md, Despliegue y Backend): El día del hackatón basta con correr en local. WhatsApp, almacenamiento de objetos y CFDI quedan fuera. Un servidor posterior sigue el patrón del companion de arquitectura.
- C10 (README.md, Cómo correrlo): La URL pública que recibe los avisos de pey es https://transfiereme.asware.com.mx.
- C11 (docs/stack-tecnologico/000-stack.md, Sesión; _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): El vendedor del día se crea a mano y entra con correo y contraseña. El alta pública, Google, el nombre, el tipo de negocio y la confirmación de correo quedan fuera. En la demo su CLABE ya está ACTIVE y no se recorre la captura. Se cumple cuando no hay pantalla de registro y solo entra ese vendedor.
- C12 (_bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): Mientras una venta sigue pendiente, transfiereme no abre otro cobro. Si el vendedor cobra por fuera sin esperar, el doble cobro no se concilia. Se cumple cuando, con una venta pendiente, no hay forma de armar otra.
- C13 (_bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md): Hay una sola API key de plataforma, oculta, y no hay llave por vendedor. El vendedor indica su CLABE y el QR aparece cuando pey la marca ACTIVE. Se cumple cuando un vendedor sin cuenta ACTIVE no obtiene QR y la llave no está en la app.

## Done when

- Un vendedor creado a mano, con sesión, tiene un QR general impreso. Un cliente que ya tiene CoDi paga tecleando el monto sin que el vendedor abra la app para ese cobro; el movimiento aparece como "Transferencia".
- El mismo vendedor arma una venta con un solo canal vivo, QR o notificación. El otro aparece solo si el primero venció sin pago, y con la venta pendiente no se arma otro cobro. El resumen distingue QR de venta y notificación.
- Un aviso de pey con firma válida marca el cobro pagado una sola vez; sin pago, el cobro queda vencido al expirar.
- El tablero agrupa por concepto vigente, día y canal, y un cambio de concepto no altera lo que vio el pagador ni lo que guardó pey.
- La demo de punta a punta es un cobro real de $0.01 en la API de producción.
- Inventario, ticket, caja, iOS, el alta pública, activar CoDi para el cliente, la confirmación de correo y el despliegue a un servidor siguen fuera.

## Boundaries

transfiereme reemplaza el tramo en que el vendedor arma el cobro dentro de su banco. Sirve a quien hoy cobra en efectivo. El cliente sigue autorizando en su app y SPEI sigue abonando la cuenta. Quien nunca activó CoDi queda fuera.

Fuera de esta iniciativa: inventario, ticket, caja, iOS, reintento, cancelación, conciliación, WhatsApp, almacenamiento de objetos, CFDI, el alta pública, activar CoDi para el cliente, la confirmación de correo, y publicar la app en un servidor el día del hackatón.

Recorrido que une las capas: el QR impreso del local cobra sin abrir transfiereme. Para una venta, el vendedor abre la app y arma un solo canal. El cliente paga, pey avisa y el tablero se actualiza.

- Touch point: API de pey (`https://api.pey.mx`) — alta de QR, notificación, consulta de respaldo, avisos de pago y la CLABE hasta que pey la marca ACTIVE; owner: sin epic todavía
- Touch point: portal de pey — una persona registra la URL del webhook y guarda el secreto; owner: sin epic todavía
- Touch point: app bancaria del cliente — leer el QR, el acercamiento y la autorización; owner: no se construye

## References

- brief — README.md, Problema, Alcance, Solución propuesta, Concepto por defecto, Flujo de usuario, Nota de pruebas, Roadmap del día del hackatón
- architecture — docs/stack-tecnologico/000-stack.md
- flujo-actual — docs/flujos-de-trabajo/flujo-codi-actual.md
- forge — _bmad-output/initiative-cody/forge-cody-readme/forge-cody-readme.md

## Notes

- Assumption: la app se llama transfiereme.
- Assumption: la URL pública de los avisos se escribe con https.
- Assumption: no hay página de inicio aparte; la app web se sirve en la raíz.
- Decision: el alta por correo, Google, nombre y tipo de negocio que proponía el forge se ignora. El vendedor se crea a mano.
