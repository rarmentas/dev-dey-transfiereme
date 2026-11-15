---
name: Transfiéreme
description: Sistema visual existente de la app Flutter para el pequeño comercio mexicano.
colors:
  primary: "#1E4FA3"
  accent: "#FFC233"
  background: "#F4F6FA"
  card: "#FFFFFF"
  ink: "#111A2B"
  ink-muted: "#4F5D76"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
---

# Sistema visual de Transfiéreme

## Visión general

Documentado desde el código de `feat/ui-pedidos-cuentas`, el 15-11-2026.
Autoridad: `frontend/lib/theme/transfiereme_theme.dart` (tema claro y oscuro).
Complementos reales: `frontend/lib/core/ui/{tf_tokens,tf_componentes}.dart`.
Marca: `landing/src/styles/{tokens,global,fonts}.css`; no trasladar reglas de landing a la app.
Referencias de uso: Inicio (`home_autenticado_page.dart`, `inicio_widgets.dart`), Tablero y Venta.
Los mockups `docs/diseno/mockups/app-{claro,oscuro}.png` son referencias históricas, no capturas de esta rama.
Lo descrito como «criterio» o «aplicación» normaliza las vistas nuevas; no afirma que ya esté implementado.

- El tendero opera con celular, una mano, prisa y sol/pantalla brillante: lectura rápida y acciones grandes.
- Con poca alfabetización digital, mostrar qué pasó y qué sigue en español breve: verbo primero y tuteo.
- Monto, estado y siguiente acción dominan; identificadores, revisión y fechas quedan en segundo plano.
- El azul transmite continuidad; amarillo destaca Cobrar; verde confirma pago, naranja espera, rojo error.
- Cada estado lleva palabra e ícono. Nunca depender solo del color ni equiparar cotizado con pagado.

## Colores

Usar `Theme.of(context).colorScheme` (`s`) y `extension<TfColors>()!` (`tf`).
Hexadecimal solo como documentación; resolver los roles del tema en los widgets.
El frontmatter resume el modo claro; esta tabla incluye ambos modos, activados por `ThemeMode.system`.

| Rol / token Flutter | Claro | Oscuro | Uso |
| --- | --- | --- | --- |
| `s.primary` / `s.onPrimary` | #1E4FA3 / #FFFFFF | #7FAEF5 / #0B1120 | Acción general, enlace, foco |
| `s.primaryContainer` / `s.onPrimaryContainer` | #DCE7FB / #0F3270 | #1C2D4D / #E8EDF6 | Selección/información |
| `tf.accent` / `tf.onAccent` | #FFC233 / #111A2B | #FFD15C / #0B1120 | Botón Cobrar |
| `s.surface` | #F4F6FA | #0B1120 | Fondo del Scaffold; equivale a `--bg` |
| `s.surfaceContainerLow`, `s.surfaceContainer` | #FFFFFF | #141C2E | Tarjeta; equivale a `--surface` |
| `s.surfaceContainerLowest` | #FFFFFF | #070B16 | Fondo de campo |
| `s.surfaceContainerHigh`, `Highest` | #E8EDF5 | #1D2740 | Contenedor tonal/neutro |
| `s.onSurface` | #111A2B | #E8EDF6 | Texto principal |
| `s.onSurfaceVariant` | #4F5D76 | #A2AEC4 | Texto secundario |
| `s.outline` / `s.outlineVariant` | #74819A / #DCE3EE | #65728C / #26314A | Campo / división suave |
| `tf.paid` / `tf.paidText` / `tf.paidContainer` | #1F9D55 / #157A45 / #E2F3E9 | #3DD68C / #3DD68C / #16352A | Confirmación |
| `tf.pending` / `tf.pendingText` / `tf.pendingContainer` | #F2811D / #A04A00 / #FFEBD6 | #FF9F4A / #FF9F4A / #3A2414 | Espera/atención |
| `tf.expired` / `tf.expiredText` / `tf.expiredContainer` | #C2412D / #A8361F / #FBE6E1 | #E8735F / #E8735F / #3D221D | Error/vencido/rechazado |
| `s.error` / `s.onError` | #C2412D / #FFFFFF | #E8735F / #0B1120 | Error Material |
| `s.errorContainer` / `s.onErrorContainer` | #FBE6E1 / #A8361F | #3D221D / #E8735F | Mensaje de error |
| `s.tertiary` / `s.onTertiary` | #157A45 / #FFFFFF | #3DD68C / #0B1120 | Confirmación Material |
| `s.inverseSurface` / `s.onInverseSurface` | #111A2B / #F4F6FA | #E8EDF6 / #0B1120 | Snackbar |

`tertiaryContainer/onTertiaryContainer` coinciden con `paidContainer/paidText`.
`secondary` coincide con `accent`, pero `secondaryContainer/onSecondaryContainer` coinciden con espera.
`surfaceTint` es transparente; `shadow` y `scrim` son negros.

Contrastes calculados por luminancia sRGB sobre colores sólidos, redondeados; no son pruebas de pantalla:

| Texto/fondo | Claro | Oscuro |
| --- | --- | --- |
| `onPrimary/primary` | 7.77:1 | 8.32:1 |
| `onAccent/accent` | 10.79:1 | 13.03:1 |
| `paidText/paidContainer` | 4.67:1 | 7.10:1 |
| `pendingText/pendingContainer` | 5.21:1 | 7.15:1 |
| `expiredText/expiredContainer` | 5.45:1 | 4.88:1 |

Criterio AA: texto normal ≥4.5:1; texto grande ≥3:1; controles e indicadores esenciales ≥3:1.
`paid` sobre blanco da 3.49:1 y `pending` 2.65:1: no usarlos como texto pequeño;
para íconos esenciales de espera también gana `pendingText`. `outlineVariant` solo separa, no identifica un campo.

## Tipografía

Plus Jakarta Sans local (`kDisplayFont = PlusJakartaSans`): títulos y montos grandes, pesos 600/700/800.
Inter local (`kUiFont`): cuerpo y controles, pesos 400/500/600. La landing registra las mismas familias.
Usar `textTheme`, conservando altura y peso; no sustituir por tamaños locales ni pedir pesos Inter inexistentes.

| `TextTheme` | Familia | Tamaño / interlínea / peso | Uso |
| --- | --- | --- | --- |
| `displayLarge` | Jakarta | 56 / 60 / 800 | Monto protagonista, `kTabular` |
| `displayMedium` | Jakarta | 40 / 44 / 800 | Confirmación «¡Te pagaron!» |
| `displaySmall` | Jakarta | 36 / 40 / 800 | Total de tarjeta, `kTabular` |
| `headlineLarge` | Jakarta | 28 / 34 / 800 | Título de pantalla en cuerpo |
| `headlineMedium` | Jakarta | 22 / 28 / 700 | AppBar |
| `headlineSmall` | Jakarta | 18 / 24 / 700 | Sección/título de aviso |
| `titleLarge` | Jakarta | 20 / 24 / 800 | Cobrar |
| `titleMedium` | Inter | 16 / 20 / 600 | Monto de lista, `kTabular` |
| `titleSmall` | Inter | 14 / 20 / 600 | Etiqueta/chip |
| `bodyLarge` | Inter | 17 / 24 / 400 | Texto de entrada/explicación destacada |
| `bodyMedium` | Inter | 15 / 22 / 400 | Cuerpo |
| `bodySmall` | Inter | 13 / 18 / 400 | Ayuda/metadatos; `onSurfaceVariant` |
| `labelLarge` | Inter | 16 / 20 / 600 | Botón |
| `labelMedium` | Inter | 12 / 16 / 600 | Sobretítulo, tracking 0.06 em |
| `labelSmall` | Inter | 11 / 14 / 600 | Etiqueta de navegación |

Tracking Jakarta: −0.02 em en displayLarge/Medium, −0.01 em en displaySmall/headlineLarge; resto 0.
`kTabular` alinea cifras. No usar `labelSmall` para montos, estados decisivos ni instrucciones.

## Distribución y espaciado

- Escala `TfSpace`: s1=4, s2=8, s3=12, s4=16, s5=20, s6=24, s8=32, s10=40, s12=48, s16=64.
- Excepción establecida: `kMargenPantalla = 18` px por lado; no redondearlo a 16 por conveniencia.
- Móvil primero, columna con desplazamiento vertical: a 360/390 px quedan 324/354 px antes del padding de tarjeta.
- Escritorio/tablet: `kMaxAnchoContenido = 480` px, centrado, incluido el margen interior de pantalla.
  Usar `TfPantalla` o `Center > ConstrainedBox(maxWidth: kMaxAnchoContenido)` como Inicio/Tablero.
  Aplicar el margen una sola vez. La landing usa 1200 px y padding 24/16; no es el ancho de la app.
- Patrón observado: tarjetas con padding s4 (Tablero/listas) o s5 (resumen de Inicio); entre tarjetas s3/s4.
  Criterio para vistas nuevas: s4 interior, s3 entre tarjetas, s4 entre secciones/campos, s2 entre acciones.
- `SafeArea` para bordes del sistema; conservar AppBar y desplazamiento con teclado.
  Mantener la acción principal fácil de alcanzar; no introducir barras fijas que tapen campos.
- En 360–390 px y texto ampliado, pasar filas a columna/`Wrap`; no fijar alturas al contenido ni recortar montos.

## Elevación y profundidad

Tarjetas `Card`: elevación 1 en claro y 0 en oscuro, sombra `#29111A2B`, sin tinte de superficie, margen 0.
AppBar: elevación y `scrolledUnderElevation` 0. Cobrar: elevación 2, sombra `accent` con alfa 0.5.
La landing tiene sombras CSS `--elev-1/2/3`; no equivalen a niveles Flutter.
Snackbar flotante y hoja inferior heredan sus elevaciones Material: el tema no fija valores propios.
En oscuro la separación depende de superficies y espacio, no de añadir sombras fuertes.

## Formas

`TfTheme`/`TfRadius`: sm=8, md=12, lg=16, xl=24; `TfRadius.full=999` para píldoras.
md: botones generales, campos, aviso y snackbar; lg: tarjetas/Cobrar; xl: borde superior de hoja y marco QR.
Campo: contorno `outline` 1.5 px; foco `primary` 2; error `expired` 2. Botón secundario: borde `primary` 2.

## Componentes

- **Tarjetas/listas:** `Card` del tema, título `headlineSmall/titleSmall`, detalle `bodyMedium/bodySmall`.
  Separar identificación, estados y monto; importe de lista `titleMedium`, total `displaySmall`.
  Texto largo de cliente/producto puede envolver; chevrón indica acceso, no reemplaza el nombre de la acción.
- **Primario general:** `FilledButton`, mínimo 48×52 px, padding horizontal 20, radio md, `labelLarge`, azul.
  **Cobrar:** `TfCobrarButton`/`TfTheme.cobrar(context)`, amarillo, texto `onAccent`, altura 64, ancho disponible.
  **Secundario:** `OutlinedButton`, mínimo 48×52, azul/borde 2. **Terciario:** `TextButton`, mínimo 48×48.
  **Destructivo:** `TfDestructivoButton`, borde `expired`, texto `expiredText`; confirmar con diálogo.
  Conservar condiciones de habilitación y callbacks; una operación en curso lleva indicador y texto comprensible.
- **Chips:** `TfEstadoChip.pagado/pendiente/vencido/cancelado`: fondo semántico, texto `*Text`, ícono y etiqueta.
  Su padding real es 10×4 y el ícono 16. `ChipTheme` usa `StadiumBorder`, padding horizontal 8 y `titleSmall`.
  Informativos azules: `Chip` con `primaryContainer/onPrimaryContainer`; neutros: `surfaceContainerHigh/onSurfaceVariant`.
  Los chips informativos no son botones; filtros/acciones sí requieren área táctil ≥48.
  `TfEstadoChip.desde` solo reconoce pagado, pendiente, vencido y cancelado (y equivalentes ingleses).
  Para otros estados elegir variante explícita; no dejar que «rechazado» termine como cancelado neutro.
  `TfEstadoChip` no envuelve su texto: mantener etiquetas cortas y poner explicaciones fuera del chip, especialmente al 200 %.
- **Campos:** heredar `InputDecorationTheme`, mínimo 56, padding 16×16, fondo `surfaceContainerLowest`.
  Etiqueta persistente `titleSmall`, ayuda `bodySmall`, foco/error visibles; el cuerpo puede crecer con mensajes.
  Selector de canal: `TfSegmentado` es la referencia visual; si debe deshabilitarse, usar `SegmentedButton` del tema.
  En ancho/texto limitado, `DropdownButtonFormField` etiquetado y expandido permite conservar las opciones completas.
- **Vacío:** `TfVacio` con ícono tonal, título, explicación y acción existente cuando aplique.
  **Carga:** indicador del tema (`tf.pending`) más etiqueta contextual; al actualizar conservar datos visibles.
  Si el indicador es una señal esencial sobre blanco, usar `tf.pendingText`: el `pending` actual solo alcanza 2.65:1.
  **Error:** `TfAvisoError`, mensaje humano y acción de recuperación existente. Atención/espera usa naranja;
  confirmación usa verde. No pintar de error un aviso de guardado correcto.
- **QR:** `TfSize.qrScreen=232`, módulos negros sobre fondo blanco opaco, incluso en oscuro;
  marco blanco con s4 y radio xl, como `VentaEsperaPage`. Blanco/negro son excepción óptica deliberada.
  No cambiar payload ni parámetros de cobro; añadir instrucción de escaneo y etiqueta semántica en español.
- **Navegación:** AppBar alineada a inicio, `headlineMedium`; barra inferior de 72 px, íconos de 24,
  indicador `primaryContainer`, etiquetas `labelSmall`; conservar rutas y destinos actuales.

### Montos MXN

Datos de pedidos en centavos enteros; visualización `$1,234.50`: coma de miles, punto decimal, dos decimales.
Ejemplos: 0 → `$0.00`; 1 → `$0.01`; 1250 → `$12.50`; 123450 → `$1,234.50`.
`pedidos/data/pedido.dart::formatearCentavos` ya cumple para importes no negativos; reutilizarlo en Pedidos.
`formatearMonto` separa miles pero conserva los decimales recibidos: no garantiza por sí solo dos posiciones.
`montoDeCentavos` (Tablero) también formatea centavos y maneja signo; no hace falta otro formateador.
No convertir a `double` para mostrar importes. Un total ausente significa «Por cotizar», nunca `$0.00`.
Importe editable: pesos sin separadores de miles, con `prefixText: '$ '` y ayuda «Pesos mexicanos»;
conservar parser/validación. «En demo se cobrará…» debe distinguir total del pedido e importe del cobro.

### Estados: aplicación de los roles existentes

Pedido comercial, pago y preparación son ejes distintos. Esta asignación visual queda por aplicar en las vistas nuevas;
las claves existen en los modelos y contratos actuales. No crea estados ni modifica transiciones.

| Eje / clave | Texto visible | Rol y pista adicional |
| --- | --- | --- |
| Pedido `borrador` | Pendiente de cotizar | `pendingText/Container`, reloj |
| Pedido `en_revision` | En revisión | `pendingText/Container`, reloj; aclarar artículos por cotizar |
| Pedido `cotizado` | Cotizado | `onPrimaryContainer/primaryContainer`, documento |
| Pedido `aceptado` | Aceptado por el cliente | Azul informativo, verificación; todavía no implica pago |
| Pedido `cerrado` | Cerrado | Neutro; no inferir cancelación: también se cierra al entregar |
| Pago `sin_cobro` | Sin cobro | Neutro, ícono de pago |
| Pago `en_espera` | Cobro en espera | Espera naranja, reloj |
| Pago `reservado`, `enviando` | Generando cobro… | Espera naranja, indicador |
| Pago `pendiente` | Pago pendiente | Espera naranja, reloj; QR o aviso al celular |
| Pago `incierto` | Sin confirmar | Espera naranja, advertencia y «No repitas el cobro» |
| Pago `pagado` | Pagado | `paidText/Container`, palomita |
| Pago `rechazado`, `vencido` | Cobro rechazado / Cobro vencido | `expiredText/Container`, error |
| Pago `descartado` | Cobro descartado | Neutro, bloqueo; explicar si pertenece a una aceptación anterior |
| Preparación `pendiente` | Preparación pendiente | Espera naranja, reloj |
| Preparación `listo` | Listo para entregar | Azul informativo, bolsa |
| Preparación `entregado` | Entregado | Confirmación verde, paquete/verificación; conservar chip de pago aparte |
| Cualquier clave desconocida | Estado no disponible | Neutro e información; no prometer éxito |

Cuentas: «Sin registrar» neutro; «Registro en proceso», «Pendiente de activación», «Sin confirmar» en espera;
«Registro rechazado» en error; «Lista para cobrar» verde solo cuando `puedeCobrar` lo confirma.
«Cuenta para cobrar»/predeterminada se distingue con etiqueta o ícono azul, sin confundir selección con activación.

## Reglas y contradicciones resueltas

- **AA y tacto:** objetivos ≥48 px lógicos, texto ampliable hasta 200 %, foco visible y recorrido de teclado coherente.
  No truncar montos ni instrucciones decisivas; añadir `Semantics` a estado dinámico y QR, sin anuncios repetidos del polling.
  Ícono más texto en estados; iconos sin texto requieren tooltip/etiqueta. Verificar ambos temas.
- **`secondary` contradictorio:** el comentario dice amarillo, pero sus contenedores son de espera naranja.
  Ganan `tf.accent/onAccent` para Cobrar y `tf.pending*` para espera; no usar `secondary` como estado.
- **Verdes distintos:** `tf.paid=#1F9D55`, `s.tertiary=tf.paidText=#157A45` en claro.
  No unificarlos por apariencia: para letras gana `paidText`; `paid` queda como acento gráfico con contraste comprobado.
- **Nombre `surface`:** Flutter `s.surface` es fondo, CSS `--surface` es tarjeta; ganar por rol, no por nombre literal.
  Campos oscuros Flutter #070B16 y altura Cobrar 64 ganan sobre simplificaciones de landing/mockups (incluidos 72 px históricos).
- **Ancho/márgenes:** ganan `kMaxAnchoContenido=480` y `kMargenPantalla=18` sobre ListView nuevos de ancho libre/padding 16.
- **Espacio:** `CardTheme.margin=0` es intencional; las pantallas deben agregar s3/s4 entre tarjetas.
  Literales 12/16 ya coinciden con la escala: son deuda de tokens, no colores o tamaños de marca nuevos.
- **Cobrar y resumen:** gana el estado vivo de `PagoCard` sobre el texto fijo «Cobro: no habilitado todavía» del resumen.
  `cerrado` gana como clave comercial; mostrar «Entregado» solo con preparación confirmada, no llamarlo siempre «Cancelado».
- **Documentación histórica:** conservar familia/paleta, pero ganan ThemeData y widgets actuales frente a CSS y mockups.
  No copiar el anillo CSS 3+2 como si Flutter ya lo tuviera: el campo Flutter enfoca con borde de 2 px.
  `TfSegmentado` fija 48 de alto, elipsis y exige callback activo; no asumir que admite texto ampliado o deshabilitación.
  Además pide Inter 700 al seleccionar, aunque solo está registrado hasta 600: gana `titleSmall` 600 del tema.
  Usar los componentes compartidos existentes sin alterar lógica, API o navegación para corregir presentación.
