import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/router/app_router.dart';
import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../../movimientos/data/movimiento.dart';
import '../data/venta.dart';
import '../data/venta_repository.dart';
import 'venta_providers.dart';
import 'widgets/venta_pagada_view.dart';

class VentaEsperaPage extends ConsumerStatefulWidget {
  const VentaEsperaPage({
    super.key,
    required this.movimientoId,
    this.avisoPendiente = false,
    this.repositorio,
  });

  final int movimientoId;
  final bool avisoPendiente;

  /// Si viene, las pruebas no dependen del provider global.
  final VentaRepository? repositorio;

  @override
  ConsumerState<VentaEsperaPage> createState() => _VentaEsperaPageState();
}

class _VentaEsperaPageState extends ConsumerState<VentaEsperaPage> {
  Timer? _timer;
  Timer? _reloj;
  Duration? _vigenciaInicial;
  Venta? _venta;
  String? _avisoRed;
  var _cargando = true;
  var _termino = false;
  var _enCurso = false;

  @override
  void initState() {
    super.initState();
    _consultar();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _consultar());
    _reloj = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && !_termino && _venta?.venceEn != null) {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _reloj?.cancel();
    super.dispose();
  }

  VentaRepository get _repositorio =>
      widget.repositorio ?? ref.read(ventaRepositoryProvider);

  void _detener() {
    _termino = true;
    _timer?.cancel();
    _timer = null;
    _reloj?.cancel();
    _reloj = null;
  }

  Future<void> _consultar() async {
    if (_termino || _enCurso) {
      return;
    }
    _enCurso = true;
    try {
      final venta = await _repositorio.obtener(widget.movimientoId);
      if (!mounted || _termino) {
        return;
      }
      final vence = venta.venceEn;
      if (_vigenciaInicial == null && vence != null && venta.esPendiente) {
        _vigenciaInicial = vence.difference(DateTime.now());
      }
      setState(() {
        _venta = venta;
        _cargando = false;
        _avisoRed = null;
      });
      if (venta.esTerminal) {
        _detener();
      }
    } on VentaApiException catch (error) {
      if (!mounted || _termino) {
        return;
      }
      setState(() {
        _cargando = false;
        _avisoRed = error.mensaje;
      });
    } catch (_) {
      if (!mounted || _termino) {
        return;
      }
      setState(() {
        _cargando = false;
        _avisoRed = 'No pudimos actualizar el estado. Seguimos intentando.';
      });
    } finally {
      _enCurso = false;
    }
  }

  Map<String, String> get _consulta {
    if (GoRouter.maybeOf(context) == null) {
      return const {};
    }
    try {
      return GoRouterState.of(context).uri.queryParameters;
    } catch (_) {
      return const {};
    }
  }

  @override
  Widget build(BuildContext context) {
    final venta = _venta;
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final referencia = _consulta['ref'];

    if (venta != null && venta.esPagado) {
      return VentaPagadaView(venta: venta, referencia: referencia);
    }

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                TfSpace.s2,
                TfSpace.s2,
                kMargenPantalla,
                0,
              ),
              child: Row(
                children: [
                  IconButton(
                    tooltip: 'Cerrar',
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () => context.go(kRutaInicio),
                  ),
                  const SizedBox(width: TfSpace.s2),
                  if (venta == null || venta.esPendiente)
                    const TfEstadoChip.pendiente(etiqueta: 'Esperando pago'),
                ],
              ),
            ),
            Expanded(
              child: _cargando && venta == null
                  ? const Center(child: CircularProgressIndicator())
                  : TfPantalla(
                      padding: const EdgeInsets.symmetric(
                        horizontal: kMargenPantalla,
                        vertical: TfSpace.s4,
                      ),
                      child: ListView(
                        children: [
                          if (widget.avisoPendiente) ...[
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(
                                horizontal: TfSpace.s4,
                                vertical: TfSpace.s3,
                              ),
                              decoration: BoxDecoration(
                                color: tf.pendingContainer,
                                borderRadius:
                                    BorderRadius.circular(TfRadius.md),
                              ),
                              child: Row(
                                children: [
                                  Icon(
                                    Icons.info_outline_rounded,
                                    size: TfSize.icon,
                                    color: tf.pendingText,
                                  ),
                                  const SizedBox(width: TfSpace.s2),
                                  Expanded(
                                    child: Text(
                                      'Ya tenías una venta pendiente',
                                      style: (tema.textTheme.titleSmall ??
                                              const TextStyle())
                                          .copyWith(color: tf.pendingText),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: TfSpace.s4),
                          ],
                          if (venta == null)
                            const SizedBox.shrink()
                          else if (venta.esVencido)
                            _Vencido(venta: venta, referencia: referencia)
                          else
                            _Pendiente(
                              venta: venta,
                              referencia: referencia,
                              telefonoFinal:
                                  venta.telefonoFinal ?? _consulta['tel'],
                              vigenciaInicial: _vigenciaInicial,
                            ),
                          if (_avisoRed != null) ...[
                            const SizedBox(height: TfSpace.s4),
                            TfAvisoError(titulo: _avisoRed!),
                          ],
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

String _detalleCobro(Venta venta, String? referencia) {
  final ref = referencia ?? venta.referencia;
  if (ref == null || ref.isEmpty) {
    return venta.concepto;
  }
  return '${venta.concepto} · Ref $ref';
}

class _Pendiente extends StatelessWidget {
  const _Pendiente({
    required this.venta,
    required this.referencia,
    required this.telefonoFinal,
    required this.vigenciaInicial,
  });

  final Venta venta;
  final String? referencia;
  final String? telefonoFinal;
  final Duration? vigenciaInicial;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final colores = tema.colorScheme;
    final vence = venta.venceEn;
    final ahora = DateTime.now();
    final restante = vence?.difference(ahora);
    final total = vigenciaInicial?.inSeconds ?? 0;
    final progreso = restante == null || total <= 0
        ? 0.0
        : (restante.inSeconds / total).clamp(0.0, 1.0);
    final textoAvisoCelular = telefonoFinal == null || telefonoFinal!.isEmpty
        ? 'Le enviamos la solicitud a su celular'
        : 'Le enviamos la solicitud a su celular terminado en $telefonoFinal';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            formatearMonto(venta.monto),
            style: tema.textTheme.displayLarge,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: TfSpace.s1),
        Text(
          _detalleCobro(venta, referencia),
          style: tema.textTheme.bodyMedium?.copyWith(
            color: colores.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: TfSpace.s5),
        if (venta.esNotificacion)
          Center(
            child: Container(
              width: TfSize.qrScreen,
              height: TfSize.qrScreen,
              decoration: BoxDecoration(
                color: colores.surfaceContainerLowest,
                borderRadius: BorderRadius.circular(TfRadius.xl),
              ),
              child: Icon(
                Icons.smartphone_rounded,
                size: 96,
                color: colores.primary,
              ),
            ),
          )
        else if (venta.qrString.trim().isNotEmpty)
          Center(
            child: Container(
              padding: const EdgeInsets.all(TfSpace.s4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(TfRadius.xl),
              ),
              child: QrImageView(
                data: venta.qrString,
                size: TfSize.qrScreen,
                backgroundColor: Colors.white,
                errorCorrectionLevel: QrErrorCorrectLevel.H,
              ),
            ),
          ),
        const SizedBox(height: TfSpace.s4),
        Text(
          venta.esNotificacion
              ? textoAvisoCelular
              : 'Pídele que escanee con la app de su banco',
          style: tema.textTheme.bodyLarge,
          textAlign: TextAlign.center,
        ),
        if (vence != null) ...[
          const SizedBox(height: TfSpace.s5),
          Row(
            children: [
              Text(
                'Vence en',
                style: tema.textTheme.bodyMedium?.copyWith(
                  color: colores.onSurfaceVariant,
                ),
              ),
              const Spacer(),
              Text(
                _minutosSegundos(vence, ahora),
                style: tema.textTheme.titleMedium?.copyWith(
                  color: tf.pendingText,
                  fontWeight: FontWeight.w700,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
          const SizedBox(height: TfSpace.s2),
          ClipRRect(
            borderRadius: TfRadius.brFull,
            child: LinearProgressIndicator(
              value: progreso,
              minHeight: 8,
              color: tf.pending,
              backgroundColor: colores.surfaceContainerHigh,
            ),
          ),
        ],
      ],
    );
  }
}

/// `m:ss` hasta [vence].
String _minutosSegundos(DateTime vence, DateTime ahora) {
  final resta = vence.difference(ahora);
  final total = resta.isNegative ? 0 : resta.inSeconds;
  final segundos = (total % 60).toString().padLeft(2, '0');
  return '${total ~/ 60}:$segundos';
}

class _Vencido extends StatelessWidget {
  const _Vencido({required this.venta, required this.referencia});

  final Venta venta;
  final String? referencia;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final ref = referencia ?? venta.referencia;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            formatearMonto(venta.monto),
            style: tema.textTheme.displayLarge?.copyWith(
              color: tema.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(height: TfSpace.s4),
        const TfAvisoError(
          titulo: 'Este cobro venció',
          mensaje: 'Puedes generar otro igual.',
        ),
        const SizedBox(height: TfSpace.s6),
        FilledButton(
          key: const Key('boton_generar_otro'),
          onPressed: () => context.go(
            Uri(
              path: kRutaNuevaVenta,
              queryParameters: {
                'monto': venta.monto,
                'concepto': venta.concepto,
                if (ref != null && ref.isNotEmpty) 'referencia': ref,
              },
            ).toString(),
          ),
          child: const Text('Generar otro igual'),
        ),
      ],
    );
  }
}
