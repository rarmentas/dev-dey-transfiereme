# Componentes

Cada componente se muestra en claro y oscuro en Componentes. Reglas generales:

- **Botón Cobrar** (`accent`, `button-xl`, `radius-lg`, `elev-2`): uno por pantalla, la acción más importante. Texto en `boton-cobrar`. Puede llevar el monto: "Cobrar $120".
- **Botones secundarios**: primario lleno (`primary`) para Entrar/Guardar; contorno de 2px (`primary`) para Mi QR; tonal (`primary-container`) para acciones de apoyo; texto para Ver todos; destructivo con contorno `expired` para Cancelar cobro.
- **Campo de monto**: número grande en Plus Jakarta Sans 800 con `$` y centavos en `ink-muted`; teclado numérico; el monto nunca se corta.
- **Concepto** (prellenado "Transferencia", hasta 40 caracteres), **Referencia** (opcional, 1–7 dígitos, teclado numérico), **Celular** (10 dígitos con prefijo +52 fijo). El contador aparece a la derecha de la ayuda; el error reemplaza la ayuda en `expired-text`.
- **Chips de estado**: Pagado, Pendiente, Vencido (y Cancelado neutro). Siempre ícono + palabra.
- **Tarjeta de movimiento**: ícono de canal, concepto, hora · canal · referencia, monto tabular y chip. Un vencido muestra el monto tachado en `ink-muted`.
- **Tarjeta del tablero**: total en `monto-l` y una barra por canal (QR general, QR por venta, Notificación) con porcentaje y número de cobros.
- **Estados vacíos**: ilustración tonal, título en `titulo-3`, una frase y, si aplica, el botón Cobrar.
- **Errores**: aviso en `expired-container` con título que dice qué pasó ("Este cobro venció") y frase de qué sigue; snackbar en `ink` con acción "Reintentar".
