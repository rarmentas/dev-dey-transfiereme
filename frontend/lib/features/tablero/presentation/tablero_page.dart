import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../../movimientos/presentation/widgets/formato_fechas.dart';
import '../../movimientos/presentation/widgets/tf_segmentado.dart';
import '../data/tablero.dart';
import '../data/tablero_repository.dart';
import 'tablero_providers.dart';

class TableroPage extends ConsumerStatefulWidget {
  const TableroPage({super.key});

  @override
  ConsumerState<TableroPage> createState() => _TableroPageState();
}

class _TableroPageState extends ConsumerState<TableroPage> {
  PeriodoTablero _periodo = PeriodoTablero.semana;
  bool _porCanal = true;

  Future<void> _recargar() async {
    final ahora = ref.read(tableroAhoraProvider);
    final actual = ref.refresh(
      tableroRangoProvider(_periodo.rango(ahora)).future,
    );
    ref.invalidate(tableroRangoProvider(_periodo.rangoAnterior(ahora)));
    try {
      await actual;
    } catch (_) {
      // El provider conserva el error y la pantalla lo muestra.
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final ahora = ref.watch(tableroAhoraProvider);
    final rango = _periodo.rango(ahora);
    final asyncTablero = ref.watch(tableroRangoProvider(rango));
    final previo = ref
        .watch(tableroRangoProvider(_periodo.rangoAnterior(ahora)))
        .asData
        ?.value;

    final Widget cuerpo = asyncTablero.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: TfSpace.s16),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Padding(
        padding: const EdgeInsets.only(top: TfSpace.s4),
        child: TfAvisoError(
          titulo: mensajeErrorTablero(error),
          accion: FilledButton(
            onPressed: _recargar,
            child: const Text('Reintentar'),
          ),
        ),
      ),
      data: (tablero) {
        if (tablero.estaVacio) {
          return const Padding(
            padding: EdgeInsets.only(top: TfSpace.s8),
            child: TfVacio(
              icono: Icons.bar_chart_rounded,
              titulo: 'Aún no tienes cobros',
              mensaje: 'Cobra y aquí verás cómo te va.',
            ),
          );
        }
        return _CuerpoTablero(
          tablero: tablero,
          previo: previo,
          periodo: _periodo,
          rango: rango,
          porCanal: _porCanal,
          onCambioVista: (v) => setState(() => _porCanal = v),
        );
      },
    );

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: RefreshIndicator(
              onRefresh: _recargar,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(
                  kMargenPantalla,
                  TfSpace.s4,
                  kMargenPantalla,
                  TfSpace.s6,
                ),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Tablero',
                          style: tema.textTheme.headlineLarge,
                        ),
                      ),
                      const SizedBox(width: TfSpace.s2),
                      _SelectorPeriodo(
                        periodo: _periodo,
                        onCambio: (p) => setState(() => _periodo = p),
                      ),
                    ],
                  ),
                  const SizedBox(height: TfSpace.s4),
                  cuerpo,
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

String mensajeErrorTablero(Object error) {
  if (error is TableroApiException) {
    return error.mensaje;
  }
  return 'No pudimos cargar el tablero. Intenta de nuevo.';
}

class _SelectorPeriodo extends StatelessWidget {
  const _SelectorPeriodo({required this.periodo, required this.onCambio});

  final PeriodoTablero periodo;
  final ValueChanged<PeriodoTablero> onCambio;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    return PopupMenuButton<PeriodoTablero>(
      tooltip: 'Cambiar periodo',
      initialValue: periodo,
      onSelected: onCambio,
      itemBuilder: (_) => [
        for (final p in PeriodoTablero.values)
          PopupMenuItem(value: p, child: Text(p.etiqueta)),
      ],
      child: Container(
        height: TfSize.touchMin,
        padding: const EdgeInsets.symmetric(horizontal: TfSpace.s3),
        decoration: BoxDecoration(
          color: colores.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(TfRadius.full),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.calendar_today_rounded,
              size: 16,
              color: colores.onSurfaceVariant,
            ),
            const SizedBox(width: TfSpace.s2),
            Text(
              periodo.etiqueta,
              style: tema.textTheme.titleSmall?.copyWith(
                color: colores.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CuerpoTablero extends StatelessWidget {
  const _CuerpoTablero({
    required this.tablero,
    required this.previo,
    required this.periodo,
    required this.rango,
    required this.porCanal,
    required this.onCambioVista,
  });

  final Tablero tablero;
  final Tablero? previo;
  final PeriodoTablero periodo;
  final RangoTablero rango;
  final bool porCanal;
  final ValueChanged<bool> onCambioVista;

  @override
  Widget build(BuildContext context) {
    final hayPruebas = tablero.desarrollo.filas.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _TarjetaCobrado(
          tablero: tablero,
          previo: previo,
          periodo: periodo,
          rango: rango,
        ),
        const SizedBox(height: TfSpace.s4),
        _TarjetaDesglose(
          filas: tablero.confirmado.filas,
          porCanal: porCanal,
          onCambioVista: onCambioVista,
        ),
        if (hayPruebas) ...[
          const SizedBox(height: TfSpace.s4),
          _TarjetaPruebas(seccion: tablero.desarrollo),
        ],
      ],
    );
  }
}

class _TarjetaCobrado extends StatelessWidget {
  const _TarjetaCobrado({
    required this.tablero,
    required this.previo,
    required this.periodo,
    required this.rango,
  });

  final Tablero tablero;
  final Tablero? previo;
  final PeriodoTablero periodo;
  final RangoTablero rango;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;

    final actual = centavosDe(tablero.confirmado.total);
    final antes = previo == null ? null : centavosDe(previo!.confirmado.total);
    Widget? comparacion;
    if (antes != null && antes > 0) {
      final pct = ((actual - antes) * 100 / antes).round();
      final sube = pct > 0;
      final baja = pct < 0;
      final color = sube
          ? tf.paidText
          : baja
          ? tf.expiredText
          : tema.colorScheme.onSurfaceVariant;
      comparacion = Padding(
        padding: const EdgeInsets.only(top: TfSpace.s1),
        child: Row(
          children: [
            if (sube || baja)
              Icon(
                sube ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
                size: 16,
                color: color,
              ),
            Flexible(
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: '${pct.abs()}%',
                      style: TextStyle(color: color, fontWeight: FontWeight.w700),
                    ),
                    TextSpan(text: ' vs. ${periodo.anterior}'),
                  ],
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: tema.textTheme.bodyMedium?.copyWith(
                  color: tema.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Lo cobrado',
              style: tema.textTheme.bodyMedium?.copyWith(
                color: tema.colorScheme.onSurfaceVariant,
              ),
            ),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                tablero.confirmado.totalFormateado,
                style: tema.textTheme.displaySmall,
              ),
            ),
            ?comparacion,
            const SizedBox(height: TfSpace.s4),
            _GraficaDias(
              filas: tablero.confirmado.filas,
              rango: rango,
              semanaCompleta: periodo == PeriodoTablero.semana,
            ),
          ],
        ),
      ),
    );
  }
}

/// Barras por día. Sin paquetes: contenedores en una fila.
class _GraficaDias extends StatelessWidget {
  const _GraficaDias({
    required this.filas,
    required this.rango,
    this.semanaCompleta = false,
  });

  final List<FilaTablero> filas;
  final RangoTablero rango;

  /// Muestra los 7 días (L a D) aunque los últimos aún no lleguen.
  final bool semanaCompleta;

  static const double _alto = 120;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    final tf = tema.extension<TfColors>()!;

    final dias = <DateTime>[];
    final fin = semanaCompleta
        ? DateTime(rango.desde.year, rango.desde.month, rango.desde.day + 6)
        : rango.hasta;
    for (
      var d = rango.desde;
      !d.isAfter(fin);
      d = DateTime(d.year, d.month, d.day + 1)
    ) {
      dias.add(d);
    }
    final totales = {for (final d in dias) d: 0};
    for (final f in filas) {
      final d = soloDia(f.dia);
      if (totales.containsKey(d)) {
        totales[d] = totales[d]! + centavosDe(f.total);
      }
    }
    final maximo = totales.values.fold(0, (a, b) => a > b ? a : b);
    final denso = dias.length > 7;
    final hoyUnico = dias.length == 1;

    String etiqueta(DateTime d) {
      if (!denso) return inicialDia(d);
      return (d.day == 1 || d.day % 7 == 0) ? '${d.day}' : '';
    }

    return Column(
      children: [
        SizedBox(
          height: _alto,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisAlignment:
                hoyUnico ? MainAxisAlignment.center : MainAxisAlignment.start,
            children: [
              for (final d in dias)
                Expanded(
                  flex: hoyUnico ? 0 : 1,
                  child: Semantics(
                    label: '${nombreDia(d)}, ${montoDeCentavos(totales[d]!)}',
                    excludeSemantics: true,
                    child: Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: denso ? 1 : TfSpace.s1 + 1,
                      ),
                      child: Align(
                        alignment: Alignment.bottomCenter,
                        child: Container(
                          width: hoyUnico ? 56 : null,
                          height: maximo == 0
                              ? 4
                              : (_alto * totales[d]! / maximo).clamp(4, _alto),
                          decoration: BoxDecoration(
                            color: maximo > 0 && totales[d] == maximo
                                ? tf.accent
                                : colores.primary,
                            borderRadius: BorderRadius.circular(
                              denso ? 2 : 6,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: TfSpace.s2),
        Row(
          mainAxisAlignment:
              hoyUnico ? MainAxisAlignment.center : MainAxisAlignment.start,
          children: [
            for (final d in dias)
              Expanded(
                flex: hoyUnico ? 0 : 1,
                child: SizedBox(
                  width: hoyUnico ? 56 : null,
                  child: Text(
                    hoyUnico ? inicialDia(d) : etiqueta(d),
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.visible,
                    softWrap: false,
                    style: tema.textTheme.labelSmall?.copyWith(
                      color: colores.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _Total {
  _Total(this.nombre, this.canal);

  final String nombre;
  final String canal;
  int centavos = 0;
  int cobros = 0;
}

class _TarjetaDesglose extends StatelessWidget {
  const _TarjetaDesglose({
    required this.filas,
    required this.porCanal,
    required this.onCambioVista,
  });

  final List<FilaTablero> filas;
  final bool porCanal;
  final ValueChanged<bool> onCambioVista;

  @override
  Widget build(BuildContext context) {
    final grupos = <String, _Total>{};
    for (final f in filas) {
      final clave = porCanal ? f.canal : f.etiqueta;
      final nombre = porCanal ? _etiquetaCanal(f.canal) : f.etiqueta;
      final g = grupos.putIfAbsent(clave, () => _Total(nombre, f.canal));
      g.centavos += centavosDe(f.total);
      g.cobros += f.cantidad;
    }
    final lista = grupos.values.toList()
      ..sort((a, b) => b.centavos.compareTo(a.centavos));
    final suma = lista.fold(0, (s, g) => s + g.centavos);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TfSegmentado<bool>(
              opciones: const {true: 'Por canal', false: 'Por concepto'},
              valor: porCanal,
              onCambio: onCambioVista,
            ),
            const SizedBox(height: TfSpace.s4),
            for (var i = 0; i < lista.length; i++) ...[
              if (i > 0) const SizedBox(height: TfSpace.s4),
              _FilaDesglose(
                grupo: lista[i],
                porCanal: porCanal,
                proporcion: suma > 0 ? lista[i].centavos / suma : 0,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _FilaDesglose extends StatelessWidget {
  const _FilaDesglose({
    required this.grupo,
    required this.porCanal,
    required this.proporcion,
  });

  final _Total grupo;
  final bool porCanal;
  final double proporcion;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    final pct = (proporcion * 100).round();
    final cobros = '${grupo.cobros} ${grupo.cobros == 1 ? 'cobro' : 'cobros'}';
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TfIconoCanal(porCanal ? _iconoCanal(grupo.canal) : Icons.sell_rounded),
        const SizedBox(width: TfSpace.s3),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      grupo.nombre,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: (tema.textTheme.titleSmall ?? const TextStyle())
                          .copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                  const SizedBox(width: TfSpace.s2),
                  Text(
                    montoDeCentavos(grupo.centavos),
                    style: tema.textTheme.titleMedium,
                  ),
                ],
              ),
              const SizedBox(height: TfSpace.s2),
              ClipRRect(
                borderRadius: BorderRadius.circular(TfRadius.full),
                child: LinearProgressIndicator(
                  value: proporcion.clamp(0.0, 1.0),
                  minHeight: 6,
                  color: colores.primary,
                  backgroundColor: colores.surfaceContainerHigh,
                ),
              ),
              const SizedBox(height: TfSpace.s1),
              Text(
                '$pct% · $cobros',
                style: tema.textTheme.bodySmall?.copyWith(
                  color: colores.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _TarjetaPruebas extends StatelessWidget {
  const _TarjetaPruebas({required this.seccion});

  final SeccionTablero seccion;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    final cobros = seccion.filas.fold(0, (s, f) => s + f.cantidad);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Row(
          children: [
            const TfIconoCanal(Icons.science_rounded),
            const SizedBox(width: TfSpace.s3),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Pruebas',
                    style: tema.textTheme.titleSmall?.copyWith(
                      color: colores.onSurfaceVariant,
                    ),
                  ),
                  Text(
                    '$cobros ${cobros == 1 ? 'cobro' : 'cobros'} de prueba, '
                    'no suman a lo cobrado.',
                    style: tema.textTheme.bodySmall?.copyWith(
                      color: colores.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: TfSpace.s2),
            Text(
              seccion.totalFormateado,
              style: tema.textTheme.titleMedium?.copyWith(
                color: colores.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
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
