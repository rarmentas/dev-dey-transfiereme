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
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  VentaRepository get _repositorio =>
      widget.repositorio ?? ref.read(ventaRepositoryProvider);

  void _detener() {
    _termino = true;
    _timer?.cancel();
    _timer = null;
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

  @override
  Widget build(BuildContext context) {
    final venta = _venta;
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Cobro',
          style: tema.textTheme.headlineMedium,
        ),
      ),
      body: SafeArea(
        child: _cargando && venta == null
            ? const Center(child: CircularProgressIndicator())
            : TfPantalla(
                padding: const EdgeInsets.symmetric(
                  horizontal: kMargenPantalla,
                  vertical: TfSpace.s6,
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
                          borderRadius: BorderRadius.circular(TfRadius.md),
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
                                'Ya tenía una venta pendiente',
                                style: (tema.textTheme.titleSmall ??
                                        const TextStyle())
                                    .copyWith(
                                  color: tf.pendingText,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: TfSpace.s4),
                    ],
                    if (venta == null)
                      const SizedBox.shrink()
                    else if (venta.esPagado)
                      _Pagado(venta: venta)
                    else if (venta.esVencido)
                      const _Vencido()
                    else
                      _Pendiente(venta: venta),
                    if (_avisoRed != null) ...[
                      const SizedBox(height: TfSpace.s4),
                      TfAvisoError(titulo: _avisoRed!),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

class _Pendiente extends StatelessWidget {
  const _Pendiente({required this.venta});

  final Venta venta;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final vence = venta.venceEn;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Center(
          child: TfEstadoChip.pendiente(etiqueta: 'Esperando pago'),
        ),
        const SizedBox(height: TfSpace.s4),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            formatearMonto(venta.monto),
            style: tema.textTheme.displayLarge,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: TfSpace.s2),
        Text(
          venta.concepto,
          style: tema.textTheme.titleMedium?.copyWith(
            color: tema.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: TfSpace.s5),
        if (venta.qrString.trim().isNotEmpty)
          Center(
            child: Container(
              padding: const EdgeInsets.all(TfSpace.s4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(TfRadius.xl),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: QrImageView(
                data: venta.qrString,
                size: TfSize.qrScreen,
                backgroundColor: Colors.white,
                errorCorrectionLevel: QrErrorCorrectLevel.H,
              ),
            ),
          ),
        if (vence != null) ...[
          const SizedBox(height: TfSpace.s6),
          Text(
            'Quedan ${cuentaRegresiva(vence, DateTime.now())}',
            style: tema.textTheme.titleLarge?.copyWith(
              color: tf.pendingText,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }
}

class _Pagado extends StatelessWidget {
  const _Pagado({required this.venta});

  final Venta venta;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colors = tema.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(
            horizontal: TfSpace.s6,
            vertical: TfSpace.s8,
          ),
          decoration: BoxDecoration(
            color: colors.primary,
            borderRadius: BorderRadius.circular(TfRadius.lg),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.check_circle_rounded,
                size: 72,
                color: colors.onPrimary,
              ),
              const SizedBox(height: TfSpace.s4),
              Text(
                'Pagado',
                style: tema.textTheme.headlineMedium?.copyWith(
                  color: colors.onPrimary,
                  fontWeight: FontWeight.w700,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: TfSpace.s4),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  formatearMonto(venta.monto),
                  style: tema.textTheme.displayLarge?.copyWith(
                    color: colors.onPrimary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              if (venta.horaPagado.isNotEmpty) ...[
                const SizedBox(height: TfSpace.s2),
                Text(
                  venta.horaPagado,
                  style: tema.textTheme.titleMedium?.copyWith(
                    color: colors.onPrimary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: TfSpace.s6),
        TfCobrarButton(
          onPressed: () => context.go(kRutaNuevaVenta),
          child: const Text('Nueva venta'),
        ),
        const SizedBox(height: TfSpace.s3),
        OutlinedButton(
          onPressed: () => context.push(kRutaMovimientos),
          child: const Text('Ver movimientos'),
        ),
      ],
    );
  }
}

class _Vencido extends StatelessWidget {
  const _Vencido();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const TfAvisoError(
          titulo: 'El cobro venció sin pago',
        ),
        const SizedBox(height: TfSpace.s6),
        FilledButton(
          onPressed: () => context.go(kRutaNuevaVenta),
          child: const Text('Nueva venta'),
        ),
      ],
    );
  }
}
