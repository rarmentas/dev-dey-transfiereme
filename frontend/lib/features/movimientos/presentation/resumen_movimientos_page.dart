import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/fecha/dia_cdmx.dart';
import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../data/movimiento.dart';
import '../data/movimientos_repository.dart';
import 'movimientos_providers.dart';
import 'widgets/formato_fechas.dart';

enum PeriodoMovimientos { hoy, semana, mes }

class ResumenMovimientosPage extends ConsumerStatefulWidget {
  const ResumenMovimientosPage({super.key});

  @override
  ConsumerState<ResumenMovimientosPage> createState() =>
      _ResumenMovimientosPageState();
}

class _ResumenMovimientosPageState
    extends ConsumerState<ResumenMovimientosPage> {
  PeriodoMovimientos _periodo = PeriodoMovimientos.hoy;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final asyncMovimientos = ref.watch(movimientosProvider);
    final ahora = ref.watch(movimientosAhoraProvider);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: RefreshIndicator(
              onRefresh: () => _recargar(ref),
              child: asyncMovimientos.when(
                loading: () => const _EstadoCentrado(
                  child: CircularProgressIndicator(),
                ),
                error: (error, _) => _EstadoCentrado(
                  child: _ErrorMovimientos(
                    mensaje: mensajeErrorMovimientos(error),
                    onReintentar: () => _recargar(ref),
                  ),
                ),
                data: (movimientos) {
                  if (movimientos.isEmpty) {
                    return const _EstadoCentrado(
                      child: TfVacio(
                        icono: Icons.receipt_long_rounded,
                        titulo: 'Aún no tienes cobros',
                        mensaje: 'Cobra y aquí verás cada pago.',
                      ),
                    );
                  }
                  final grupos = _agrupar(
                    movimientos,
                    _periodo,
                    soloDia(ahora),
                  );
                  return ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(
                      kMargenPantalla,
                      TfSpace.s4,
                      kMargenPantalla,
                      TfSpace.s6,
                    ),
                    children: [
                      Text('Movimientos', style: tema.textTheme.headlineLarge),
                      const SizedBox(height: TfSpace.s4),
                      TfSegmentado<PeriodoMovimientos>(
                        opciones: const {
                          PeriodoMovimientos.hoy: 'Hoy',
                          PeriodoMovimientos.semana: 'Semana',
                          PeriodoMovimientos.mes: 'Mes',
                        },
                        valor: _periodo,
                        onCambio: (p) => setState(() => _periodo = p),
                      ),
                      const SizedBox(height: TfSpace.s4),
                      if (grupos.isEmpty)
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: TfSpace.s8,
                          ),
                          child: Text(
                            'Sin cobros en este periodo.',
                            textAlign: TextAlign.center,
                            style: tema.textTheme.bodyMedium?.copyWith(
                              color: tema.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      for (final grupo in grupos) ...[
                        _EncabezadoDia(
                          grupo: grupo,
                          esHoy: grupo.dia == soloDia(ahora),
                        ),
                        _GrupoDia(movimientos: grupo.movimientos),
                        const SizedBox(height: TfSpace.s4),
                      ],
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Grupo {
  _Grupo(this.dia);

  final DateTime dia;
  final List<Movimiento> movimientos = [];

  int get totalCentavos => movimientos
      .where((m) => m.estado == 'pagado')
      .fold(0, (suma, m) => suma + centavosDe(m.monto));
}

/// Filtra por fecha local y agrupa por día, del más reciente al más antiguo.
List<_Grupo> _agrupar(
  List<Movimiento> movimientos,
  PeriodoMovimientos periodo,
  DateTime hoy,
) {
  final inicio = switch (periodo) {
    PeriodoMovimientos.hoy => hoy,
    PeriodoMovimientos.semana => lunesDe(hoy),
    PeriodoMovimientos.mes => DateTime(hoy.year, hoy.month),
  };
  final ordenados = [...movimientos]
    ..sort((a, b) => b.fechaMostrada.compareTo(a.fechaMostrada));
  final grupos = <_Grupo>[];
  for (final m in ordenados) {
    final dia = diaCdmx(m.fechaMostrada);
    if (dia.isBefore(inicio) || dia.isAfter(hoy)) continue;
    if (grupos.isEmpty || grupos.last.dia != dia) grupos.add(_Grupo(dia));
    grupos.last.movimientos.add(m);
  }
  return grupos;
}

class _EncabezadoDia extends StatelessWidget {
  const _EncabezadoDia({required this.grupo, required this.esHoy});

  final _Grupo grupo;
  final bool esHoy;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final n = grupo.movimientos.length;
    final cuenta = '$n ${n == 1 ? 'COBRO' : 'COBROS'}';
    final texto = '${esHoy ? 'HOY' : fechaSobretitulo(grupo.dia)} · $cuenta';
    return Padding(
      padding: const EdgeInsets.only(bottom: TfSpace.s2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Text(
              texto,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: tema.textTheme.labelMedium?.copyWith(
                color: tema.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const SizedBox(width: TfSpace.s2),
          Text(
            montoDeCentavos(grupo.totalCentavos),
            style: tema.textTheme.titleSmall?.copyWith(
              fontFeatures: kTabular,
              color: tema.colorScheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }
}

class _GrupoDia extends StatelessWidget {
  const _GrupoDia({required this.movimientos});

  final List<Movimiento> movimientos;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < movimientos.length; i++) ...[
            if (i > 0)
              Divider(
                height: 1,
                thickness: 1,
                indent: TfSpace.s4,
                endIndent: TfSpace.s4,
                color: Theme.of(context).colorScheme.surfaceContainerHigh,
              ),
            _FilaMovimiento(movimiento: movimientos[i]),
          ],
        ],
      ),
    );
  }
}

String mensajeErrorMovimientos(Object error) {
  if (error is MovimientosApiException) {
    return error.mensaje;
  }
  return 'No pudimos cargar tus movimientos. Intenta de nuevo.';
}

Future<void> _recargar(WidgetRef ref) async {
  final recarga = ref.refresh(movimientosProvider.future);
  try {
    await recarga;
  } catch (_) {
    // El provider conserva el error y la pantalla lo muestra.
  }
}

class _EstadoCentrado extends StatelessWidget {
  const _EstadoCentrado({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: kMargenPantalla),
                  child: child,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ErrorMovimientos extends StatelessWidget {
  const _ErrorMovimientos({required this.mensaje, required this.onReintentar});

  final String mensaje;
  final Future<void> Function() onReintentar;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(TfSpace.s4),
      child: TfAvisoError(
        titulo: mensaje,
        accion: FilledButton(
          onPressed: () async {
            await onReintentar();
          },
          child: const Text('Reintentar'),
        ),
      ),
    );
  }
}

class _FilaMovimiento extends StatelessWidget {
  const _FilaMovimiento({required this.movimiento});

  final Movimiento movimiento;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    final esVencido = movimiento.estado.toLowerCase().trim() == 'vencido';
    final secundario = tema.textTheme.bodySmall?.copyWith(
      color: colores.onSurfaceVariant,
    );

    final estiloMonto = (tema.textTheme.titleMedium ?? const TextStyle())
        .copyWith(
          color: esVencido ? colores.onSurfaceVariant : colores.onSurface,
          decoration: esVencido ? TextDecoration.lineThrough : null,
          decorationColor: esVencido ? colores.onSurfaceVariant : null,
        );

    final contenido = Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: TfSpace.s4,
        vertical: TfSpace.s3,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TfIconoCanal(_iconoCanal(movimiento.canal)),
          const SizedBox(width: TfSpace.s3),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(
                      child: Row(
                        children: [
                          Flexible(
                            child: Text(
                              movimiento.conceptoVisible,
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                              style:
                                  (tema.textTheme.titleSmall ??
                                          const TextStyle())
                                      .copyWith(fontWeight: FontWeight.w600),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: TfSpace.s2),
                    Text(movimiento.montoFormateado, style: estiloMonto),
                  ],
                ),
                if (movimiento.muestraEnviado) ...[
                  const SizedBox(height: TfSpace.s1),
                  Text(
                    'Enviado: ${movimiento.concepto}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: secundario,
                  ),
                ],
                const SizedBox(height: TfSpace.s1),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(
                      child: Text(
                        '${horaCdmx(movimiento.fechaMostrada)} · '
                        '${movimiento.etiquetaCanal}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: secundario,
                      ),
                    ),
                    const SizedBox(width: TfSpace.s2),
                    if (movimiento.esPrueba) ...[
                      Chip(
                        visualDensity: VisualDensity.compact,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        labelPadding: const EdgeInsets.symmetric(
                          horizontal: TfSpace.s1,
                        ),
                        padding: EdgeInsets.zero,
                        label: Text(
                          'Prueba',
                          style: tema.textTheme.labelSmall?.copyWith(
                            color: colores.onSurfaceVariant,
                          ),
                        ),
                      ),
                      const SizedBox(width: TfSpace.s1),
                    ],
                    TfEstadoChip.desde(
                      estado: movimiento.estado,
                      etiqueta: movimiento.etiquetaEstado,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );

    return contenido;
  }
}

IconData _iconoCanal(String canal) {
  return switch (canal) {
    'qr_general' => Icons.qr_code_2_rounded,
    'qr_venta' => Icons.storefront_rounded,
    'notificacion' => Icons.phonelink_ring_rounded,
    _ => Icons.payment_rounded,
  };
}
