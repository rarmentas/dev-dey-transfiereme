import 'package:flutter/material.dart';

import 'tf_tokens.dart';

/// Filtro segmentado del mockup: contenedor tonal con el segmento activo
/// elevado y en negritas.
class TfSegmentado<T> extends StatelessWidget {
  const TfSegmentado({
    super.key,
    required this.opciones,
    required this.valor,
    required this.onCambio,
    this.iconos,
  });

  final Map<T, String> opciones;
  final T valor;
  final ValueChanged<T> onCambio;

  /// Ícono opcional por opción, a la izquierda de la etiqueta.
  final Map<T, IconData>? iconos;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    return Container(
      padding: const EdgeInsets.all(TfSpace.s1),
      decoration: BoxDecoration(
        color: colores.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(TfRadius.md),
      ),
      child: Row(
        children: [
          for (final e in opciones.entries)
            Expanded(
              child: Semantics(
                button: true,
                selected: e.key == valor,
                child: InkWell(
                  borderRadius: BorderRadius.circular(TfRadius.sm),
                  onTap: () => onCambio(e.key),
                  child: Container(
                    height: TfSize.touchMin,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: e.key == valor ? colores.surfaceContainerLow : null,
                      borderRadius: BorderRadius.circular(TfRadius.sm),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (iconos?[e.key] != null) ...[
                          Icon(
                            iconos![e.key],
                            size: 18,
                            color: e.key == valor
                                ? colores.onSurface
                                : colores.onSurfaceVariant,
                          ),
                          const SizedBox(width: TfSpace.s2),
                        ],
                        Flexible(
                          child: Text(
                            e.value,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: tema.textTheme.titleSmall?.copyWith(
                              fontWeight: e.key == valor
                                  ? FontWeight.w700
                                  : FontWeight.w500,
                              color: e.key == valor
                                  ? colores.onSurface
                                  : colores.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
