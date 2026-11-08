import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../data/tablero.dart';
import '../data/tablero_repository.dart';
import 'tablero_providers.dart';

class TableroPage extends ConsumerWidget {
  const TableroPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncTablero = ref.watch(tableroProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Tablero')),
      body: RefreshIndicator(
        onRefresh: () => _recargar(ref),
        child: asyncTablero.when(
          loading: () =>
              const _EstadoCentrado(child: CircularProgressIndicator()),
          error: (error, _) => _EstadoCentrado(
            child: _ErrorTablero(
              mensaje: mensajeErrorTablero(error),
              onReintentar: () => _recargar(ref),
            ),
          ),
          data: (tablero) {
            if (tablero.estaVacio) {
              return const _EstadoCentrado(
                child: TfVacio(
                  icono: Icons.bar_chart_rounded,
                  titulo: 'Aún no hay cobros',
                ),
              );
            }
            return _CuerpoTablero(tablero: tablero);
          },
        ),
      ),
    );
  }
}

String mensajeErrorTablero(Object error) {
  if (error is TableroApiException) {
    return error.mensaje;
  }
  return 'No pudimos cargar el tablero. Intente de nuevo.';
}

Future<void> _recargar(WidgetRef ref) async {
  final recarga = ref.refresh(tableroProvider.future);
  try {
    await recarga;
  } catch (_) {
    // El provider conserva el error y la pantalla lo muestra.
  }
}

class _CuerpoTablero extends StatelessWidget {
  const _CuerpoTablero({required this.tablero});

  final Tablero tablero;

  @override
  Widget build(BuildContext context) {
    final pruebas = tablero.desarrollo.filas.isNotEmpty;
    final totalConfirmado = double.tryParse(tablero.confirmado.total) ?? 0.0;
    final totalDesarrollo = double.tryParse(tablero.desarrollo.total) ?? 0.0;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(
            kMargenPantalla,
            TfSpace.s3,
            kMargenPantalla,
            TfSpace.s6,
          ),
          children: [
            _EncabezadoSeccion(
              titulo: 'Cobrado',
              total: tablero.confirmado.totalFormateado,
            ),
            const SizedBox(height: TfSpace.s2),
            ..._bloques(tablero.confirmado.filas, totalConfirmado),
            if (pruebas) ...[
              const SizedBox(height: TfSpace.s4),
              _EncabezadoSeccion(
                titulo: 'Pruebas',
                total: tablero.desarrollo.totalFormateado,
                atenuado: true,
              ),
              const SizedBox(height: TfSpace.s2),
              ..._bloques(
                tablero.desarrollo.filas,
                totalDesarrollo,
                atenuado: true,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

List<Widget> _bloques(
  List<FilaTablero> filas,
  double totalSeccion, {
  bool atenuado = false,
}) {
  final bloques = <Widget>[];
  for (final grupo in _gruposPorDia(filas)) {
    bloques.add(
      _BloqueDia(
        dia: grupo.dia,
        filas: grupo.filas,
        totalSeccion: totalSeccion,
        atenuado: atenuado,
      ),
    );
    bloques.add(const SizedBox(height: TfSpace.s3));
  }
  return bloques;
}

class _GrupoDia {
  const _GrupoDia(this.dia, this.filas);

  final DateTime dia;
  final List<FilaTablero> filas;
}

List<_GrupoDia> _gruposPorDia(List<FilaTablero> filas) {
  final grupos = <_GrupoDia>[];
  for (final fila in filas) {
    if (grupos.isEmpty || grupos.last.dia != fila.dia) {
      grupos.add(_GrupoDia(fila.dia, [fila]));
    } else {
      grupos.last.filas.add(fila);
    }
  }
  return grupos;
}

class _EncabezadoSeccion extends StatelessWidget {
  const _EncabezadoSeccion({
    required this.titulo,
    required this.total,
    this.atenuado = false,
  });

  final String titulo;
  final String total;
  final bool atenuado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final color = atenuado
        ? tema.colorScheme.onSurfaceVariant
        : tema.colorScheme.onSurface;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              titulo,
              style: tema.textTheme.labelMedium?.copyWith(
                color: atenuado
                    ? tema.colorScheme.onSurfaceVariant
                    : tema.colorScheme.primary,
              ),
            ),
            const SizedBox(height: TfSpace.s1),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                total,
                style: (tema.textTheme.displaySmall ?? const TextStyle()).copyWith(
                  color: color,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BloqueDia extends StatelessWidget {
  const _BloqueDia({
    required this.dia,
    required this.filas,
    required this.totalSeccion,
    required this.atenuado,
  });

  final DateTime dia;
  final List<FilaTablero> filas;
  final double totalSeccion;
  final bool atenuado;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: TfSpace.s2, bottom: TfSpace.s1),
          child: TfSobretitulo(_diaCorto(dia)),
        ),
        for (final fila in filas) ...[
          _FilaTableroTile(
            fila: fila,
            proporcion: totalSeccion > 0
                ? (double.tryParse(fila.total) ?? 0) / totalSeccion
                : 0.0,
            atenuado: atenuado,
          ),
          const SizedBox(height: TfSpace.s2),
        ],
      ],
    );
  }
}

class _FilaTableroTile extends StatelessWidget {
  const _FilaTableroTile({
    required this.fila,
    required this.proporcion,
    required this.atenuado,
  });

  final FilaTablero fila;
  final double proporcion;
  final bool atenuado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final color = atenuado
        ? tema.colorScheme.onSurfaceVariant
        : tema.colorScheme.onSurface;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TfIconoCanal(_iconoCanal(fila.canal)),
            const SizedBox(width: TfSpace.s3),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          fila.etiqueta,
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                          style: (tema.textTheme.titleMedium ?? const TextStyle()).copyWith(
                            color: color,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: TfSpace.s3),
                      Flexible(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: Text(
                            fila.totalFormateado,
                            style: (tema.textTheme.titleMedium ?? const TextStyle()).copyWith(
                              color: color,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: TfSpace.s1),
                  Row(
                    children: [
                      Text(
                        _etiquetaCanal(fila.canal),
                        style: tema.textTheme.bodySmall,
                      ),
                      const SizedBox(width: TfSpace.s2),
                      Text(
                        '×${fila.cantidad}',
                        style: tema.textTheme.bodySmall,
                      ),
                    ],
                  ),
                  const SizedBox(height: TfSpace.s2),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(TfRadius.full),
                    child: LinearProgressIndicator(
                      value: proporcion.clamp(0.0, 1.0),
                      minHeight: 6,
                      color: atenuado
                          ? tema.colorScheme.outline
                          : tema.colorScheme.primary,
                      backgroundColor: tema.colorScheme.surfaceContainerHigh,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _diaCorto(DateTime dia) {
  final d = dia.day.toString().padLeft(2, '0');
  final m = dia.month.toString().padLeft(2, '0');
  return '$d/$m/${dia.year}';
}

String _etiquetaCanal(String canal) {
  return switch (canal) {
    'qr_general' => 'QR general',
    'qr_venta' => 'QR de venta',
    'notificacion' => 'Notificación',
    _ => canal,
  };
}

IconData _iconoCanal(String canal) {
  return switch (canal) {
    'qr_general' => Icons.qr_code_2_rounded,
    'qr_venta' => Icons.storefront_rounded,
    'notificacion' => Icons.phonelink_ring_rounded,
    _ => Icons.payment_rounded,
  };
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

class _ErrorTablero extends StatelessWidget {
  const _ErrorTablero({required this.mensaje, required this.onReintentar});

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
