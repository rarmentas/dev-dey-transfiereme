# Cody

- Habilita al negocio que hoy cobra en efectivo. Poca influencia sobre el cliente. Solo cobra quien ya tiene CoDi. Quien nunca lo activó queda fuera.
- El vendedor no abre su banco. El QR del local ya impreso cobra sin abrir Cody. En la venta, monto y concepto opcional se teclean más rápido que en el banco.
- Pagar solo es el QR del local: el cliente abre su banco, escanea y teclea el monto. Concepto «Transferencia». Sin notificación.
- La venta, si el cliente coopera, lleva un solo canal: celular o QR. El otro aparece cuando el primero está vencido y sin pago. Antes, la pantalla no lo ofrece.
- Mientras la venta sigue pendiente, el vendedor no cobra por otro lado. Si no esperan, el doble cobro es riesgo aceptado.
- Después del abono: resumen, renombre del concepto solo en Cody, tablero por concepto vigente, día y canal.
- Una API key de plataforma, oculta. El vendedor mete su CLABE. El QR aparece cuando pey la marca ACTIVE. No hay API key por vendedor.
- Cuentas nuevas y proyecto nuevo de Google. Cody verifica el id_token y abre su cookie. También correo y contraseña, sin confirmación. Nombre y tipo de negocio (informales u «otro») se guardan después o se saltan. El tipo no cambia el cobro ni el tablero.
- Hackatón: cuenta ya creada, correo y contraseña, CLABE demo ACTIVE. Google y la captura de CLABE no se demuestran. La confirmación de correo queda en la documentación como feature posible.

Rechazado:

- QR leído por la cámara del teléfono que abre el banco y le pasa el JSON. `qrString` es el mensaje CoDi, no una URL.
- Los dos canales de una venta vivos a la vez. Son dos altas en pey y el segundo abono no se cancela.
- Cuentas, proyecto de Google y JWT de cuentas-claras.
- Wizard de nombre y tipo antes del primer QR.
