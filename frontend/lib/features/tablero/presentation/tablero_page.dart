import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
              return const _EstadoCentrado(child: Text('Aún no hay cobros'));
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
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        _EncabezadoSeccion(
          titulo: 'Cobrado',
          total: tablero.confirmado.totalFormateado,
        ),
        const SizedBox(height: 8),
        ..._bloques(tablero.confirmado.filas),
        if (pruebas) ...[
          const SizedBox(height: 24),
          _EncabezadoSeccion(
            titulo: 'Pruebas',
            total: tablero.desarrollo.totalFormateado,
            atenuado: true,
          ),
          const SizedBox(height: 8),
          ..._bloques(tablero.desarrollo.filas, atenuado: true),
        ],
      ],
    );
  }
}

List<Widget> _bloques(List<FilaTablero> filas, {bool atenuado = false}) {
  final bloques = <Widget>[];
  for (final grupo in _gruposPorDia(filas)) {
    bloques.add(
      _BloqueDia(dia: grupo.dia, filas: grupo.filas, atenuado: atenuado),
    );
    bloques.add(const SizedBox(height: 12));
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
    final estilo = tema.textTheme.headlineSmall?.copyWith(color: color);
    return Row(
      children: [
        Expanded(child: Text(titulo, style: estilo)),
        Text(total, style: estilo),
      ],
    );
  }
}

class _BloqueDia extends StatelessWidget {
  const _BloqueDia({
    required this.dia,
    required this.filas,
    required this.atenuado,
  });

  final DateTime dia;
  final List<FilaTablero> filas;
  final bool atenuado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final color = atenuado
        ? tema.colorScheme.onSurfaceVariant
        : tema.colorScheme.onSurface;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          _diaCorto(dia),
          style: tema.textTheme.titleSmall?.copyWith(color: color),
        ),
        const SizedBox(height: 8),
        for (final fila in filas) ...[
          _FilaTableroTile(fila: fila, atenuado: atenuado),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _FilaTableroTile extends StatelessWidget {
  const _FilaTableroTile({required this.fila, required this.atenuado});

  final FilaTablero fila;
  final bool atenuado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final color = atenuado
        ? tema.colorScheme.onSurfaceVariant
        : tema.colorScheme.onSurface;
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    fila.etiqueta,
                    style: tema.textTheme.titleMedium?.copyWith(color: color),
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  fila.totalFormateado,
                  style: tema.textTheme.titleMedium?.copyWith(color: color),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(_etiquetaCanal(fila.canal), style: tema.textTheme.bodySmall),
            Text('×${fila.cantidad}', style: tema.textTheme.bodySmall),
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
              child: Center(child: child),
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
    final tema = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            mensaje,
            style: tema.textTheme.bodyLarge?.copyWith(
              color: tema.colorScheme.error,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () async {
              await onReintentar();
            },
            child: const Text('Reintentar'),
          ),
        ],
      ),
    );
  }
}
