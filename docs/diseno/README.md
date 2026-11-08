# Design system Transfiéreme (variante azul)

Origen: `Transfiereme-azul.zip` de Claude Design. Tema de Flutter aplicado en `frontend/lib/theme/transfiereme_theme.dart`; secciones en `guia/`, tokens en `tokens.json`, logos SVG en `logos/`, vistas previas en `mockups/` y el cartel QR en `impresos/`.

> Variante azul de Transfiéreme, para comparar con la versión verde. Primario Azul Cobro (#1E4FA3 / #7FAEF5), neutros fríos y acentos pensados para cobrar: Amarillo Cobro para la acción, Naranja Espera para lo pendiente y un color por canal en el tablero.

Transfiéreme es la forma más rápida de cobrar con CoDi en un comercio de barrio. Todo en este sistema existe para un momento: el vendedor ve **"Listo, te pagaron"** un segundo después de que su cliente paga. Rápida, confiable, cálida y de barrio; nunca un banco.

## Voz y tono

- Tutea siempre y habla corto. Una idea por frase, el verbo primero: "Cobrar", "Mi QR", "Nuevo cobro".
- Celebra el pago con el monto exacto: "Listo, te pagaron $120", "¡Te pagaron!". Nunca "Transacción completada exitosamente".
- Di qué pasó y qué sigue, sin culpas: "Este cobro venció. Puedes generar otro igual." / "Revisa el celular: deben ser 10 dígitos."
- Escribe los montos como en México: `$1,250.00` (coma de miles, punto decimal, sin "MXN" en pantalla). Horas en 24 h: `13:42`.
- Sin jerga bancaria: "QR por venta", no "cobro dinámico"; "Notificación", no "solicitud de pago push"; "concepto" y "referencia" sí, porque así los ve el cliente en su banco.
- El concepto por defecto es **Transferencia**; el vendedor lo renombra y ese nombre manda en el tablero.
- Sin emojis en la interfaz. La alegría la ponen el color y el tamaño del monto.

## Fundamentos visuales

- **Fondo gris azulado, no blanco de banco.** Pantallas en `bg` (#F4F6FA); tarjetas y campos en `surface`. En oscuro, `bg` #0B1120 y `surface` #141C2E.
- **Azul Cobro manda, amarillo señala.** `primary` para acciones, enlaces, foco y gráficas. `accent` (Amarillo Cobro) solo para el botón **Cobrar**, el marco del QR impreso y el día récord del tablero: si todo es naranja, nada lo es. Nunca uses `accent` como color de texto.
- **Estados con palabra e ícono.** Pagado (`paid`), pendiente (`pending`), vencido/error (`expired`) van siempre como chip con ícono y palabra; el color nunca es la única pista. Para texto usa las variantes `paid-text`, `pending-text`, `expired-text`.
- **Montos grandes y tabulares.** Montos protagonistas en `monto-xl`/`monto-l` (Plus Jakarta Sans 800). Montos en listas en `monto-lista` (Inter 600) con `font-variant-numeric: tabular-nums` para que las cifras se alineen.
- **Táctil generoso.** Todo lo que se toca mide `touch-min` (48px) o más; los campos `input-h` (56px) y el botón Cobrar `button-xl` (64px). Pensado para usarse con una mano, de pie y con prisa.
- **Formas redondeadas, no infladas.** `radius-md` en campos y botones, `radius-lg` en tarjetas y en Cobrar, `radius-xl` en el marco del QR y el isotipo, `radius-full` en chips.
- **Sombras casi nulas.** `elev-1` en tarjetas; `elev-2` (resplandor amarillo) solo en Cobrar; `elev-3` en hojas y snackbars.
- **Foco visible.** Anillo `focus` de 3px sólido con 2px de separación; pasa 3:1 en todas las superficies de ambos modos.
- **Movimiento:** la confirmación de pago entra en 200 ms (escala 0.9→1 y vibración corta). Nada más se anima por gusto.

## Iconografía

Usa **Material Symbols Rounded**, peso 500, relleno 0, en 24px (en Flutter: `Icons.*_rounded` o el paquete `material_symbols_icons`). Las vistas previas usan íconos de trazo dibujados a mano que imitan ese estilo (trazo 2px, extremos redondos). Íconos de canal: QR general = `qr_code_2`, QR por venta = `storefront`, notificación = `phonelink_ring`. Estados: `check_circle`, `schedule`, `error`.

## Dónde está cada cosa

Marca y logo, color con verificación de contraste, tipografía, tokens, componentes, la app, el QR impreso, la landing y el `ThemeData` de Flutter están en las secciones siguientes. Los logos de la dirección recomendada están en Recursos › Logos como SVG.
