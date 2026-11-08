# Color

Todos los colores son tokens con valor claro y oscuro (Tokens › Colores). Las combinaciones de abajo están calculadas con la fórmula de contraste WCAG 2.1: **AA** pide 4.5:1 para texto normal y 3:1 para texto grande (≥24 px, o ≥19 px en negritas) y para bordes, íconos y anillos de foco.

## Acentos reconfigurados para cobro

En esta variante los acentos se eligieron por lo que la app hace, no por decoración:

- **Amarillo Cobro** (`accent` #FFC233 / #FFD15C) — el botón Cobrar, el marco del QR impreso y el día récord. Azul + amarillo es el par de la señalética de "aquí se paga" en mostradores y tiene 4.82:1 entre sí, así que el botón se distingue del azul también para quien no ve bien el color. Texto siempre `on-accent` encima (10.79:1).
- **Naranja Espera** (`pending` #F2811D / #FF9F4A) — el tiempo corriendo mientras llega el pago. Se separa del amarillo de Cobrar para que "todavía no pagan" nunca se confunda con "aquí cobras". Texto en `pending-text` #A04A00 (6.04:1 sobre blanco).
- **Pagado verde y vencido rojo se quedan**: en un cobro el verde significa dinero recibido en cualquier app bancaria; cambiarlo cuesta más de lo que gana.
- **Colores por canal** para el tablero: `chan-qr-general` (azul marino), `chan-qr-venta` (azul cielo) y `chan-notificacion` (turquesa), todos ≥3:1 sobre `surface` en ambos modos. Van siempre con el nombre y el ícono del canal.

| Token | Claro | Oscuro |
| --- | --- | --- |
| `accent` (Amarillo Cobro) | #FFC233 | #FFD15C |
| `pending` (Naranja Espera) | #F2811D | #FF9F4A |
| `pending-text` / `pending-container` | #A04A00 / #FFEBD6 | #FF9F4A / #3A2414 |
| `chan-qr-general` | #1E4FA3 | #7FAEF5 |
| `chan-qr-venta` | #2B8FD6 | #4F8FE8 |
| `chan-notificacion` | #0E8FA3 | #3CC1D3 |

## Paleta

| Rol | Claro | Oscuro |
| --- | --- | --- |
| Primario (Azul Cobro) | #1E4FA3, texto blanco | #7FAEF5, texto oscuro |
| Acento (Amarillo Cobro) | #FFC233, texto oscuro | #FFD15C, texto oscuro |
| Tinta / Texto | #111A2B | #E8EDF6 |
| Fondo | #F4F6FA | #0B1120 |
| Superficie | #FFFFFF | #141C2E |
| Pagado | #1F9D55 | #3DD68C |
| Pendiente (Naranja Espera) | #F2811D | #FF9F4A |
| Vencido o error | #C2412D | #E8735F |

## Contraste de la paleta — modo claro

| Combinación | Colores | Contraste | Resultado | Uso |
| --- | --- | --- | --- | --- |
| `on-primary` sobre `primary` | #FFFFFF / #1E4FA3 | 7.77:1 | ✅ AA | Botón primario |
| `on-accent` sobre `accent` | #111A2B / #FFC233 | 10.79:1 | ✅ AA | Botón Cobrar |
| `ink` sobre `bg` | #111A2B / #F4F6FA | 16.09:1 | ✅ AA | Texto general |
| `ink` sobre `surface` | #111A2B / #FFFFFF | 17.41:1 | ✅ AA | Texto en tarjetas |
| `primary` sobre `bg` | #1E4FA3 / #F4F6FA | 7.18:1 | ✅ AA | Enlaces |
| `primary` sobre `surface` | #1E4FA3 / #FFFFFF | 7.77:1 | ✅ AA | Enlaces en tarjetas |
| `accent` sobre `surface` | #FFC233 / #FFFFFF | 1.61:1 | ❌ No pasa | Amarillo Cobro como texto |
| `accent` sobre `bg` | #FFC233 / #F4F6FA | 1.49:1 | ❌ No pasa | Amarillo Cobro como texto |
| `paid` sobre `surface` | #1F9D55 / #FFFFFF | 3.49:1 | ⚠️ Solo texto grande | Pagado como texto |
| `paid` sobre `bg` | #1F9D55 / #F4F6FA | 3.23:1 | ⚠️ Solo texto grande | Pagado como texto |
| `on-primary` sobre `paid` | #FFFFFF / #1F9D55 | 3.49:1 | ⚠️ Solo texto grande | Texto sobre relleno pagado |
| `pending` sobre `surface` | #F2811D / #FFFFFF | 2.65:1 | ❌ No pasa | Pendiente como texto |
| `on-accent` sobre `pending` | #111A2B / #F2811D | 6.58:1 | ✅ AA | Texto sobre relleno pendiente |
| `expired` sobre `surface` | #C2412D / #FFFFFF | 5.14:1 | ✅ AA | Vencido/error como texto |
| `expired` sobre `bg` | #C2412D / #F4F6FA | 4.75:1 | ✅ AA | Vencido/error como texto |
| `on-expired` sobre `expired` | #FFFFFF / #C2412D | 5.14:1 | ✅ AA | Botón destructivo lleno |

**No pasan en claro:**

- ❌ **Amarillo Cobro #FFC233 como texto** (sobre blanco 1.61:1, sobre fondo 1.49:1) — y lo mismo el Naranja Espera #F2811D como texto (2.65:1). Úsalo solo como relleno con texto `on-accent` encima (10.79:1). Para texto de pendiente usa `pending-text` #A04A00.
- ⚠️ **Pagado #1F9D55 como texto** (3.49:1 sobre blanco, 3.23:1 sobre fondo) y **texto blanco sobre #1F9D55** (3.49:1): solo sirven en texto de 24 px o más. Para texto usa `paid-text` #157A45; sobre un relleno #1F9D55 pon texto `ink` (4.98:1) o hazlo grande.
- ❌ **Amarillo Cobro como forma sobre blanco** (1.61:1): el botón Cobrar se identifica por su texto, que sí pasa, pero no uses #FFC233 como único borde de un control ni como ícono suelto sobre blanco.

## Contraste de la paleta — modo oscuro

| Combinación | Colores | Contraste | Resultado | Uso |
| --- | --- | --- | --- | --- |
| `on-primary` sobre `primary` | #0B1120 / #7FAEF5 | 8.32:1 | ✅ AA | Botón primario |
| `on-accent` sobre `accent` | #0B1120 / #FFD15C | 13.03:1 | ✅ AA | Botón Cobrar |
| `ink` sobre `bg` | #E8EDF6 / #0B1120 | 16.03:1 | ✅ AA | Texto general |
| `ink` sobre `surface` | #E8EDF6 / #141C2E | 14.47:1 | ✅ AA | Texto en tarjetas |
| `primary` sobre `bg` | #7FAEF5 / #0B1120 | 8.32:1 | ✅ AA | Enlaces |
| `primary` sobre `surface` | #7FAEF5 / #141C2E | 7.51:1 | ✅ AA | Enlaces en tarjetas |
| `accent` sobre `surface` | #FFD15C / #141C2E | 11.76:1 | ✅ AA | Amarillo Cobro como texto |
| `accent` sobre `bg` | #FFD15C / #0B1120 | 13.03:1 | ✅ AA | Amarillo Cobro como texto |
| `paid` sobre `surface` | #3DD68C / #141C2E | 9.06:1 | ✅ AA | Pagado como texto |
| `paid` sobre `bg` | #3DD68C / #0B1120 | 10.04:1 | ✅ AA | Pagado como texto |
| `on-primary` sobre `paid` | #0B1120 / #3DD68C | 10.04:1 | ✅ AA | Texto sobre relleno pagado |
| `pending` sobre `surface` | #FF9F4A / #141C2E | 8.35:1 | ✅ AA | Pendiente como texto |
| `on-accent` sobre `pending` | #0B1120 / #FF9F4A | 9.24:1 | ✅ AA | Texto sobre relleno pendiente |
| `expired` sobre `surface` | #E8735F / #141C2E | 5.71:1 | ✅ AA | Vencido/error como texto |
| `expired` sobre `bg` | #E8735F / #0B1120 | 6.32:1 | ✅ AA | Vencido/error como texto |
| `on-expired` sobre `expired` | #0B1120 / #E8735F | 6.32:1 | ✅ AA | Botón destructivo lleno |

En oscuro **todas las combinaciones pasan AA**. Ojo: el relleno `paid` #3DD68C lleva texto oscuro, nunca blanco.

## Tonos agregados para que todo pase

Para no re-teñir la marca, los colores pedidos se quedan exactos y se agregan tonos de apoyo:

| Token | Claro | Oscuro | Para qué |
| --- | --- | --- | --- |
| `surface-2` | #E8EDF5 | #1D2740 | Segmentados, chips neutros |
| `ink-muted` | #4F5D76 | #A2AEC4 | Texto secundario |
| `outline` / `outline-soft` | #74819A / #DCE3EE | #65728C / #26314A | Borde de control / separador |
| `primary-container` | #DCE7FB | #1C2D4D | Fondos tonales |
| `paid-text` / `paid-container` | #157A45 / #E2F3E9 | #3DD68C / #16352A | Chip y texto de pagado |
| `pending-text` / `pending-container` | #A04A00 / #FFEBD6 | #FFD15C / #3A2414 | Chip y texto de pendiente |
| `expired-text` / `expired-container` | #A8361F / #FBE6E1 | #E8735F / #3D221D | Chip vencido, avisos de error |

### Verificación — claro

| Combinación | Colores | Contraste | Resultado | Uso |
| --- | --- | --- | --- | --- |
| `ink-muted` sobre `bg` | #4F5D76 / #F4F6FA | 6.14:1 | ✅ AA | Texto secundario |
| `ink-muted` sobre `surface` | #4F5D76 / #FFFFFF | 6.65:1 | ✅ AA | Texto secundario |
| `ink-muted` sobre `surface-2` | #4F5D76 / #E8EDF5 | 5.65:1 | ✅ AA | Texto en segmentados |
| `on-primary-container` sobre `primary-container` | #0F3270 / #DCE7FB | 9.86:1 | ✅ AA | Pestaña activa, íconos de canal |
| `paid-text` sobre `surface` | #157A45 / #FFFFFF | 5.38:1 | ✅ AA | Pagado como texto (corrección) |
| `paid-text` sobre `bg` | #157A45 / #F4F6FA | 4.97:1 | ✅ AA | Pagado como texto (corrección) |
| `paid-text` sobre `paid-container` | #157A45 / #E2F3E9 | 4.67:1 | ✅ AA | Chip pagado |
| `pending-text` sobre `surface` | #A04A00 / #FFFFFF | 6.04:1 | ✅ AA | Pendiente como texto (corrección) |
| `pending-text` sobre `pending-container` | #A04A00 / #FFEBD6 | 5.21:1 | ✅ AA | Chip pendiente |
| `expired-text` sobre `expired-container` | #A8361F / #FBE6E1 | 5.45:1 | ✅ AA | Chip vencido y aviso de error |
| `outline` sobre `surface` | #74819A / #FFFFFF | 3.93:1 | ✅ AA (3:1) | Borde de campo (3:1) |
| `outline` sobre `bg` | #74819A / #F4F6FA | 3.63:1 | ✅ AA (3:1) | Borde de campo sobre fondo |
| `primary` sobre `surface` | #1E4FA3 / #FFFFFF | 7.77:1 | ✅ AA (3:1) | Anillo de foco |
| `accent` sobre `surface` | #FFC233 / #FFFFFF | 1.61:1 | ❌ No pasa | Botón Cobrar como forma (sin borde) |

### Verificación — oscuro

| Combinación | Colores | Contraste | Resultado | Uso |
| --- | --- | --- | --- | --- |
| `ink-muted` sobre `bg` | #A2AEC4 / #0B1120 | 8.42:1 | ✅ AA | Texto secundario |
| `ink-muted` sobre `surface` | #A2AEC4 / #141C2E | 7.60:1 | ✅ AA | Texto secundario |
| `ink-muted` sobre `surface-2` | #A2AEC4 / #1D2740 | 6.63:1 | ✅ AA | Texto en segmentados |
| `on-primary-container` sobre `primary-container` | #E8EDF6 / #1C2D4D | 11.67:1 | ✅ AA | Pestaña activa, íconos de canal |
| `paid-text` sobre `surface` | #3DD68C / #141C2E | 9.06:1 | ✅ AA | Pagado como texto (corrección) |
| `paid-text` sobre `bg` | #3DD68C / #0B1120 | 10.04:1 | ✅ AA | Pagado como texto (corrección) |
| `paid-text` sobre `paid-container` | #3DD68C / #16352A | 7.10:1 | ✅ AA | Chip pagado |
| `pending-text` sobre `surface` | #FF9F4A / #141C2E | 8.35:1 | ✅ AA | Pendiente como texto (corrección) |
| `pending-text` sobre `pending-container` | #FF9F4A / #3A2414 | 7.15:1 | ✅ AA | Chip pendiente |
| `expired-text` sobre `expired-container` | #E8735F / #3D221D | 4.88:1 | ✅ AA | Chip vencido y aviso de error |
| `outline` sobre `surface` | #65728C / #141C2E | 3.51:1 | ✅ AA (3:1) | Borde de campo (3:1) |
| `outline` sobre `bg` | #65728C / #0B1120 | 3.89:1 | ✅ AA (3:1) | Borde de campo sobre fondo |
| `primary` sobre `surface` | #7FAEF5 / #141C2E | 7.51:1 | ✅ AA (3:1) | Anillo de foco |
| `accent` sobre `surface` | #FFD15C / #141C2E | 11.76:1 | ✅ AA (3:1) | Botón Cobrar como forma (sin borde) |

## Reglas

- `accent` aparece una vez por pantalla como máximo (el botón Cobrar). En el tablero, solo el día con más cobros.
- Pagado y vencido difieren en tono (verde/rojo) y en ícono y palabra; nunca muestres un estado solo con color.
- En el modo oscuro el amarillo sobre el azul (#7FAEF5) no se distingue bien: no los pongas juntos sin una superficie neutra en medio.
