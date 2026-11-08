import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/router/app_router.dart';
import '../../../theme/transfiereme_theme.dart';
import '../../cobro/presentation/qr_general_impreso_page.dart';
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
    return Scaffold(
      appBar: AppBar(title: const Text('Cobro')),
      body: SafeArea(
        child: _cargando && venta == null
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  if (widget.avisoPendiente) ...[
                    const Text('Ya tenía una venta pendiente'),
                    const SizedBox(height: 16),
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
                    const SizedBox(height: 16),
                    Text(
                      _avisoRed!,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ],
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
    final vence = venta.venceEn;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (venta.qrString.trim().isNotEmpty)
          Center(
            child: ColoredBox(
              color: Colors.white,
              child: QrImageView(
                data: venta.qrString,
                size: kLadoMinimoQrPantalla,
                backgroundColor: Colors.white,
              ),
            ),
          ),
        const SizedBox(height: 24),
        Text(
          formatearMonto(venta.monto),
          style: tema.textTheme.displaySmall,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          venta.concepto,
          style: tema.textTheme.titleMedium,
          textAlign: TextAlign.center,
        ),
        if (vence != null) ...[
          const SizedBox(height: 12),
          Text(
            'Quedan ${cuentaRegresiva(vence, DateTime.now())}',
            style: tema.textTheme.titleLarge?.copyWith(
              color: tema.extension<TfColors>()?.pendingText,
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
    final tf = tema.extension<TfColors>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Pagado',
          style: tema.textTheme.headlineMedium?.copyWith(color: tf?.paidText),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 12),
        Text(
          formatearMonto(venta.monto),
          style: tema.textTheme.displaySmall,
          textAlign: TextAlign.center,
        ),
        if (venta.horaPagado.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            venta.horaPagado,
            style: tema.textTheme.titleLarge,
            textAlign: TextAlign.center,
          ),
        ],
        const SizedBox(height: 24),
        FilledButton(
          onPressed: () => context.go(kRutaNuevaVenta),
          child: const Text('Nueva venta'),
        ),
        const SizedBox(height: 12),
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
    final tema = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'El cobro venció sin pago',
          style: tema.textTheme.headlineSmall?.copyWith(
            color: tema.extension<TfColors>()?.expiredText,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: () => context.go(kRutaNuevaVenta),
          child: const Text('Nueva venta'),
        ),
      ],
    );
  }
}
