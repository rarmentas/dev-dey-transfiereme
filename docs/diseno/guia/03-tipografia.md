# Tipografía

- **Plus Jakarta Sans** (600, 700, 800) para títulos y montos grandes: redonda, amable y con números anchos que se leen de lejos.
- **Inter** (400, 500, 600) para la interfaz: formularios, listas, metadatos.
- Los montos en listas y tarjetas usan **cifras tabulares** (`font-variant-numeric: tabular-nums`; en Flutter `FontFeature.tabularFigures()`), para que `$85.50` y `$120.00` se alineen a la derecha.

La escala completa está en Tipografía, con su uso. Resumen:

| Estilo | Familia | Tamaño / interlínea | Peso | Uso |
| --- | --- | --- | --- | --- |
| `monto-xl` | Plus Jakarta Sans | 56 / 60 | 800 | Monto en ¡Te pagaron! y espera |
| `display` | Plus Jakarta Sans | 40 / 44 | 800 | "¡Te pagaron!", landing |
| `monto-l` | Plus Jakarta Sans | 36 / 40 | 800 | Totales del tablero, "Hoy llevas" |
| `titulo-1` | Plus Jakarta Sans | 28 / 34 | 800 | Título de pantalla |
| `titulo-2` | Plus Jakarta Sans | 22 / 28 | 700 | Encabezado de tarjeta |
| `titulo-3` | Plus Jakarta Sans | 18 / 24 | 700 | Avisos, vacíos, diálogos |
| `boton-cobrar` | Plus Jakarta Sans | 20 / 24 | 800 | Solo el botón Cobrar |
| `cuerpo-l` | Inter | 17 / 24 | 400 | Texto dentro de campos |
| `cuerpo` | Inter | 15 / 22 | 400 | Texto general |
| `cuerpo-s` | Inter | 13 / 18 | 400 | Metadatos y ayudas |
| `etiqueta` | Inter | 14 / 20 | 600 | Etiquetas de campo, chips |
| `boton` | Inter | 16 / 20 | 600 | Botones normales |
| `monto-lista` | Inter | 16 / 20 | 600 · tnum | Montos en listas |
| `sobretitulo` | Inter | 12 / 16 | 600 · MAYÚS | Separadores por día |
| `micro` | Inter | 11 / 14 | 600 | Etiquetas de navegación |

Reglas: no bajes de 13 px salvo `micro` en la barra de navegación. Respeta el tamaño de letra del sistema hasta 1.3× sin cortar montos (los montos se encogen antes que perder dígitos).
