# App

Vista previa en un teléfono Android de 360 dp (las tarjetas **AppClaro** y **AppOscuro**). La app aún no está programada; estas pantallas fijan el lenguaje.

1. **Inicio de sesión** — correo y contraseña; botón primario Entrar.
2. **Inicio** — "Hoy llevas" en `monto-l`, **Cobrar** a todo lo ancho (72 px de alto) y **Mi QR** debajo; últimos cobros.
3. **Armar venta** — monto obligatorio, concepto "Transferencia" editable, referencia opcional y selector QR / A su celular. El botón repite el monto.
4. **Espera del pago** — chip "Esperando pago", monto, QR sobre blanco (siempre blanco, también en oscuro), cuenta regresiva en `pending-text` con barra, y Cancelar cobro. Al vencer: aviso "Este cobro venció" y botón "Generar otro igual".
5. **¡Te pagaron!** — la pantalla entera en `primary` con texto `on-primary`: palomita, "¡Te pagaron!", el monto en `monto-xl`, quién y de qué banco. Vibración corta. Nuevo cobro en `accent`.
6. **Movimientos** — filtros Hoy/Semana/Mes, separador con total del día y tarjetas de movimiento.
7. **Tablero** — total del periodo, barras por día (el día récord en `accent`) y totales por canal. Por concepto se ve igual que por canal.

Navegación inferior: Inicio, Movimientos, Tablero, Ajustes. Desde Ajustes se renombra el concepto por defecto.
