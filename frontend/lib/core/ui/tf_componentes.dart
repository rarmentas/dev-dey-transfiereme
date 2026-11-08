import 'package:cody/core/ui/tf_tokens.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';

/// Botón principal de cobro (Amarillo Cobro).
///
/// Tiene una altura de 64 px ([TfSize.buttonXl]), se extiende a todo lo ancho
/// y encapsula un [FilledButton] para preservar compatibilidad con pruebas.
class TfCobrarButton extends StatelessWidget {
  /// Crea un botón principal de cobro.
  const TfCobrarButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.icon,
    this.style,
  });

  /// Acción al pulsar el botón; si es null el botón aparece deshabilitado.
  final VoidCallback? onPressed;

  /// Contenido del botón (habitualmente [Text]).
  final Widget child;

  /// Ícono opcional a la izquierda del contenido.
  final Widget? icon;

  /// Estilo adicional opcional para sobreescribir o combinar.
  final ButtonStyle? style;

  @override
  Widget build(BuildContext context) {
    final baseStyle = TfTheme.cobrar(context).copyWith(
      minimumSize: const WidgetStatePropertyAll(
        Size(double.infinity, TfSize.buttonXl),
      ),
    );
    final effectiveStyle = style != null ? baseStyle.merge(style) : baseStyle;

    final button = icon != null
        ? FilledButton.icon(
            onPressed: onPressed,
            style: effectiveStyle,
            icon: icon!,
            label: child,
          )
        : FilledButton(
            onPressed: onPressed,
            style: effectiveStyle,
            child: child,
          );

    return SizedBox(
      width: double.infinity,
      height: TfSize.buttonXl,
      child: button,
    );
  }
}

/// Botón destructivo secundario (ej. "Cancelar cobro").
///
/// Utiliza un [OutlinedButton] con contorno de 2 px y texto en los colores
/// de error / expiración definidos en [TfColors].
class TfDestructivoButton extends StatelessWidget {
  /// Crea un botón destructivo.
  const TfDestructivoButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.icon,
    this.style,
  });

  /// Acción al pulsar el botón; si es null el botón aparece deshabilitado.
  final VoidCallback? onPressed;

  /// Contenido del botón.
  final Widget child;

  /// Ícono opcional.
  final Widget? icon;

  /// Estilo adicional opcional.
  final ButtonStyle? style;

  @override
  Widget build(BuildContext context) {
    final tf = Theme.of(context).extension<TfColors>()!;
    final baseStyle = OutlinedButton.styleFrom(
      foregroundColor: tf.expiredText,
      side: BorderSide(color: tf.expired, width: 2),
      minimumSize: const Size(TfSize.touchMin, 52),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(TfRadius.md),
      ),
    );
    final effectiveStyle = style != null ? baseStyle.merge(style) : baseStyle;

    if (icon != null) {
      return OutlinedButton.icon(
        onPressed: onPressed,
        style: effectiveStyle,
        icon: icon!,
        label: child,
      );
    }

    return OutlinedButton(
      onPressed: onPressed,
      style: effectiveStyle,
      child: child,
    );
  }
}

enum _TfTipoEstado {
  pagado,
  pendiente,
  vencido,
  cancelado,
}

/// Chip de estado en formato píldora con ícono redondeado y etiqueta de texto.
class TfEstadoChip extends StatelessWidget {
  /// Chip para estado pagado (verde).
  const TfEstadoChip.pagado({
    super.key,
    required this.etiqueta,
  }) : _tipo = _TfTipoEstado.pagado;

  /// Chip para estado pendiente (naranja).
  const TfEstadoChip.pendiente({
    super.key,
    required this.etiqueta,
  }) : _tipo = _TfTipoEstado.pendiente;

  /// Chip para estado vencido (rojo).
  const TfEstadoChip.vencido({
    super.key,
    required this.etiqueta,
  }) : _tipo = _TfTipoEstado.vencido;

  /// Chip para estado cancelado (neutro).
  const TfEstadoChip.cancelado({
    super.key,
    required this.etiqueta,
  }) : _tipo = _TfTipoEstado.cancelado;

  /// Constructor fábrica para resolver el tipo a partir de un texto de estado.
  factory TfEstadoChip.desde({
    Key? key,
    required String estado,
    required String etiqueta,
  }) {
    switch (estado.toLowerCase().trim()) {
      case 'pagado':
      case 'paid':
        return TfEstadoChip.pagado(key: key, etiqueta: etiqueta);
      case 'vencido':
      case 'expired':
        return TfEstadoChip.vencido(key: key, etiqueta: etiqueta);
      case 'cancelado':
      case 'cancelled':
      case 'canceled':
        return TfEstadoChip.cancelado(key: key, etiqueta: etiqueta);
      case 'pendiente':
      case 'pending':
      default:
        return TfEstadoChip.pendiente(key: key, etiqueta: etiqueta);
    }
  }

  /// Texto a mostrar en el chip.
  final String etiqueta;

  final _TfTipoEstado _tipo;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final tf = theme.extension<TfColors>()!;

    final (Color fondo, Color frente, IconData icono) = switch (_tipo) {
      _TfTipoEstado.pagado => (
        tf.paidContainer,
        tf.paidText,
        Icons.check_circle_rounded,
      ),
      _TfTipoEstado.pendiente => (
        tf.pendingContainer,
        tf.pendingText,
        Icons.schedule_rounded,
      ),
      _TfTipoEstado.vencido => (
        tf.expiredContainer,
        tf.expiredText,
        Icons.error_rounded,
      ),
      _TfTipoEstado.cancelado => (
        theme.colorScheme.surfaceContainerHigh,
        theme.colorScheme.onSurfaceVariant,
        Icons.block_rounded,
      ),
    };

    final textStyle = (theme.textTheme.titleSmall ?? const TextStyle()).copyWith(
      color: frente,
      fontWeight: FontWeight.w600,
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(TfRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(icono, size: 16, color: frente),
          const SizedBox(width: 4),
          Text(etiqueta, style: textStyle),
        ],
      ),
    );
  }
}

/// Sobretítulo en tipografía [TextTheme.labelMedium] con color `onSurfaceVariant`.
///
/// Conserva el texto original sin transformarlo a mayúsculas para permitir búsquedas
/// exactas en pruebas.
class TfSobretitulo extends StatelessWidget {
  /// Crea un sobretítulo.
  const TfSobretitulo(
    this.texto, {
    super.key,
    this.trailing,
  });

  /// Texto del sobretítulo.
  final String texto;

  /// Elemento opcional alineado al extremo derecho.
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = theme.textTheme.labelMedium?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );

    final textWidget = Text(texto, style: style);

    if (trailing == null) {
      return textWidget;
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        textWidget,
        trailing!,
      ],
    );
  }
}

/// Ilustración tonal y mensaje de estado vacío con acción opcional.
class TfVacio extends StatelessWidget {
  /// Crea una vista de estado vacío.
  const TfVacio({
    super.key,
    required this.icono,
    required this.titulo,
    this.mensaje,
    this.accion,
  });

  /// Ícono a mostrar dentro del círculo tonal.
  final IconData icono;

  /// Título principal del estado vacío.
  final String titulo;

  /// Frase descriptiva opcional.
  final String? mensaje;

  /// Widget de acción opcional (ej. botón Cobrar).
  final Widget? accion;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(TfSpace.s6),
              decoration: BoxDecoration(
                color: colors.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icono,
                size: 64,
                color: colors.primary,
              ),
            ),
            const SizedBox(height: TfSpace.s5),
            Text(
              titulo,
              style: theme.textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            if (mensaje != null) ...[
              const SizedBox(height: TfSpace.s2),
              Text(
                mensaje!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ],
            if (accion != null) ...[
              const SizedBox(height: TfSpace.s6),
              accion!,
            ],
          ],
        ),
      ),
    );
  }
}

/// Contenedor de aviso de error o cobro vencido.
class TfAvisoError extends StatelessWidget {
  /// Crea un aviso de error.
  const TfAvisoError({
    super.key,
    required this.titulo,
    this.mensaje,
    this.accion,
  });

  /// Título del aviso.
  final String titulo;

  /// Mensaje explicativo opcional.
  final String? mensaje;

  /// Acción opcional asociada al aviso.
  final Widget? accion;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final tf = theme.extension<TfColors>()!;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(TfSpace.s4),
      decoration: BoxDecoration(
        color: tf.expiredContainer,
        borderRadius: BorderRadius.circular(TfRadius.md),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.error_rounded,
            color: tf.expiredText,
            size: TfSize.icon,
          ),
          const SizedBox(width: TfSpace.s3),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  titulo,
                  style: theme.textTheme.headlineSmall?.copyWith(
                    color: colors.onSurface,
                  ),
                ),
                if (mensaje != null) ...[
                  const SizedBox(height: TfSpace.s1),
                  Text(
                    mensaje!,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                ],
                if (accion != null) ...[
                  const SizedBox(height: TfSpace.s3),
                  accion!,
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Contenedor estructurado de pantalla con margen horizontal de 18 px
/// y ancho máximo de 480 px centrado.
class TfPantalla extends StatelessWidget {
  /// Crea un contenedor de pantalla.
  const TfPantalla({
    super.key,
    required this.child,
    this.padding,
  });

  /// Contenido principal de la pantalla.
  final Widget child;

  /// Relleno opcional (por defecto 18 px horizontal).
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    final effectivePadding = padding ??
        const EdgeInsets.symmetric(horizontal: kMargenPantalla);

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
        child: Padding(
          padding: effectivePadding,
          child: child,
        ),
      ),
    );
  }
}

/// Ícono de canal de pago de 40×40 px con esquinas redondeadas sm.
class TfIconoCanal extends StatelessWidget {
  /// Crea un ícono de canal.
  const TfIconoCanal(
    this.icono, {
    super.key,
  });

  /// Ícono representativo del canal.
  final IconData icono;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: colors.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(TfRadius.sm),
      ),
      alignment: Alignment.center,
      child: Icon(
        icono,
        size: 22,
        color: colors.onSurfaceVariant,
      ),
    );
  }
}

/// Logotipo oficial de Transfiéreme con soporte automático para tema claro y oscuro.
class TfLogo extends StatelessWidget {
  /// Crea el logotipo con ancho configurable (por defecto 200 px).
  const TfLogo({
    super.key,
    this.width = 200,
  });

  /// Ancho del logotipo en píxeles lógicos.
  final double width;

  @override
  Widget build(BuildContext context) {
    final esOscuro = Theme.of(context).brightness == Brightness.dark;

    return Image.asset(
      esOscuro
          ? 'assets/brand/logo-oscuro.png'
          : 'assets/brand/logo-claro.png',
      width: width,
      semanticLabel: 'Transfiéreme',
    );
  }
}
