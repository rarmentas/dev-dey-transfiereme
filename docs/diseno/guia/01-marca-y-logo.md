# Marca y logo

Tres direcciones, cada una con isotipo + logotipo en Plus Jakarta Sans convertida a trazos. Mira las tarjetas **LogoAcento**, **LogoQR** y **LogoLlega** en Componentes › Marca: cada una se muestra en fondo claro, fondo oscuro, una tinta, como ícono de app Android y como favicon.

## C · La é — recomendada

`transfiéreme` en minúsculas (Plus Jakarta Sans 800) donde el acento de la **é** es un trazo amarillo. El isotipo es esa misma é sobre el cuadro Azul Cobro (radio 24/96).

- Por qué: el nombre lleva acento y la marca lo presume. Se siente de barrio y escrito a mano, no corporativo.
- El acento amarillo es la chispa del "ya te pagaron" y reutiliza el color de Cobrar.
- Es la única de las tres que se lee a 16 px (favicon) y que no compite con el QR real del cartel de mostrador.
- Riesgo: la é sola puede recordar a un editor de texto; por eso el isotipo nunca va sin el azul.

## A · Esquina QR

Tres marcas de posición de un QR y, en la cuarta esquina, un punto amarillo con palomita. Logotipo en Plus Jakarta Sans 700.

- A favor: cuenta la función al instante.
- En contra: casi todas las apps de pago usan un QR; junto al QR real del cartel se confunde, y a 16 px se vuelve ruido.

## B · Llega

Una flecha amarillo que cae en una palma/caja azul: transferir es que te llegue. Logotipo en Plus Jakarta Sans 800.

- A favor: amable y fácil de entender.
- En contra: es el ícono universal de "descargar"; se lee como app de archivos.

## Reglas del logo (dirección C)

- Usa `acento-logo-claro.svg` sobre `bg` o `surface` claros, `acento-logo-oscuro.svg` sobre fondos oscuros y `acento-logo-una-tinta.svg` (tinta #111A2B) para sellos, facturas y impresión a un color.
- El isotipo conserva su azul en ambos modos; solo el logotipo cambia a #E8EDF6 en oscuro.
- Área de respeto: la altura de la x del logotipo alrededor de todo el conjunto. Tamaño mínimo: 96 px de ancho el logotipo, 16 px el isotipo.
- No cambies el color del acento salvo en una tinta; no lo gires, no lo separes de la e.
- Android: ícono adaptativo con fondo `#1E4FA3` y capa de frente `acento-android-foreground.svg` (figura dentro de la zona segura de 66 dp).
