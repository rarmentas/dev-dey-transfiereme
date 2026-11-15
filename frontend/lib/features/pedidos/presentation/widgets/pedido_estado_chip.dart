import 'package:cody/core/ui/tf_tokens.dart';
import 'package:flutter/material.dart';

class PedidoEstadoChip extends StatelessWidget {
  const PedidoEstadoChip.comercial({super.key, required this.estado})
    : _eje = _Eje.comercial;
  const PedidoEstadoChip.pago({super.key, required this.estado})
    : _eje = _Eje.pago;
  const PedidoEstadoChip.preparacion({super.key, required this.estado})
    : _eje = _Eje.preparacion;
  final String estado;
  final _Eje _eje;
  @override
  Widget build(BuildContext context) {
    final (etiqueta, tipo) = switch (_eje) {
      _Eje.comercial => switch (estado) {
        'borrador' => ('Por cotizar', _Tipo.pendiente),
        'en_revision' => ('En revisión', _Tipo.pendiente),
        'cotizado' => ('Cotizado', _Tipo.info),
        'aceptado' => ('Aceptado', _Tipo.info),
        'cerrado' => ('Cerrado', _Tipo.neutro),
        _ => ('Estado no disponible', _Tipo.neutro),
      },
      _Eje.pago => switch (estado) {
        'sin_cobro' => ('Sin cobro', _Tipo.neutro),
        'en_espera' => ('Cobro en espera', _Tipo.pendiente),
        'reservado' || 'enviando' => ('Generando cobro…', _Tipo.pendiente),
        'pendiente' => ('Pago pendiente', _Tipo.pendiente),
        'incierto' => ('Cobro no confirmado. No lo repitas.', _Tipo.pendiente),
        'pagado' => ('Pagado', _Tipo.pagado),
        'rechazado' => ('Cobro rechazado', _Tipo.vencido),
        'vencido' => ('Cobro vencido', _Tipo.vencido),
        'descartado' => (
          'Cobro descartado. Publica y acepta de nuevo.',
          _Tipo.neutro,
        ),
        _ => ('Estado no disponible', _Tipo.neutro),
      },
      _Eje.preparacion => switch (estado) {
        'pendiente' => ('Preparación pendiente', _Tipo.pendiente),
        'listo' => ('Listo para entregar', _Tipo.info),
        'entregado' => ('Entregado', _Tipo.pagado),
        _ => ('Estado no disponible', _Tipo.neutro),
      },
    };
    return _EstadoChip(etiqueta: etiqueta, tipo: tipo);
  }
}

enum _Eje { comercial, pago, preparacion }

enum _Tipo { pagado, pendiente, vencido, neutro, info }

class _EstadoChip extends StatelessWidget {
  const _EstadoChip({required this.etiqueta, required this.tipo});
  final String etiqueta;
  final _Tipo tipo;
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final colors = t.colorScheme;
    final (fondo, frente, icono) = switch (tipo) {
      _Tipo.pagado => (
        colors.tertiaryContainer,
        colors.onTertiaryContainer,
        Icons.check_circle_rounded,
      ),
      _Tipo.pendiente => (
        colors.secondaryContainer,
        colors.onSecondaryContainer,
        Icons.schedule_rounded,
      ),
      _Tipo.vencido => (
        colors.errorContainer,
        colors.onErrorContainer,
        Icons.error_rounded,
      ),
      _Tipo.neutro => (
        colors.surfaceContainerHigh,
        colors.onSurfaceVariant,
        Icons.block_rounded,
      ),
      _Tipo.info => (
        colors.primaryContainer,
        colors.onPrimaryContainer,
        Icons.description_rounded,
      ),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: TfSpace.s1),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(TfRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.max,
        children: [
          Icon(icono, size: 16, color: frente),
          const SizedBox(width: TfSpace.s1),
          Flexible(
            child: Text(
              etiqueta,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: t.textTheme.titleSmall?.copyWith(color: frente),
            ),
          ),
        ],
      ),
    );
  }
}
