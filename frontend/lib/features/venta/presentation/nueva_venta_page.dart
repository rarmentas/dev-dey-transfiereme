import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../cobro/presentation/qr_general_impreso_page.dart';
import '../data/venta.dart';
import '../data/venta_repository.dart';
import 'venta_providers.dart';

class NuevaVentaPage extends ConsumerStatefulWidget {
  const NuevaVentaPage({super.key, this.repositorio});

  /// Si viene, las pruebas no dependen del provider global.
  final VentaRepository? repositorio;

  @override
  ConsumerState<NuevaVentaPage> createState() => _NuevaVentaPageState();
}

class _NuevaVentaPageState extends ConsumerState<NuevaVentaPage> {
  final _formKey = GlobalKey<FormState>();
  final _montoController = TextEditingController();
  final _conceptoController = TextEditingController();
  final _referenciaController = TextEditingController();

  var _guardando = false;
  String? _error;
  PeyException? _pey;
  var _cuentaInactiva = false;

  @override
  void dispose() {
    _montoController.dispose();
    _conceptoController.dispose();
    _referenciaController.dispose();
    super.dispose();
  }

  VentaRepository get _repositorio =>
      widget.repositorio ?? ref.read(ventaRepositoryProvider);

  Future<void> _cobrar() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _guardando = true;
      _error = null;
      _pey = null;
      _cuentaInactiva = false;
    });
    try {
      final venta = await _repositorio.crear(
        monto: _montoController.text,
        concepto: _conceptoController.text,
        referencia: _referenciaController.text,
      );
      if (!mounted) {
        return;
      }
      context.push('/venta/${venta.movimientoId}');
    } on VentaPendienteException catch (error) {
      if (!mounted) {
        return;
      }
      context.push('/venta/${error.movimientoId}?aviso=pendiente');
    } on CuentaNoActiveException {
      if (!mounted) {
        return;
      }
      setState(() => _cuentaInactiva = true);
    } on PeyException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _pey = error);
    } on ValidacionVentaException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error.mensaje);
    } on VentaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error.mensaje);
    } finally {
      if (mounted) {
        setState(() => _guardando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Nueva venta')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextFormField(
                  key: const Key('campo_monto'),
                  controller: _montoController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(labelText: 'Monto'),
                  validator: (valor) => validarMontoVenta(valor ?? ''),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  key: const Key('campo_concepto'),
                  controller: _conceptoController,
                  decoration: const InputDecoration(
                    labelText: 'Concepto',
                    helperText: 'Si lo deja vacío, se envía "Transferencia"',
                  ),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  key: const Key('campo_referencia'),
                  controller: _referenciaController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Referencia',
                    helperText: 'Opcional. Solo dígitos, de 1 a 7.',
                  ),
                  validator: (valor) => validarReferenciaVenta(valor ?? ''),
                ),
                if (_cuentaInactiva) ...[
                  const SizedBox(height: 16),
                  Text(
                    kMensajeCuentaNoActivaQr,
                    style: tema.textTheme.bodyLarge?.copyWith(
                      color: tema.colorScheme.error,
                    ),
                  ),
                ],
                if (_pey != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _pey!.mensaje,
                    style: tema.textTheme.bodyLarge?.copyWith(
                      color: tema.colorScheme.error,
                    ),
                  ),
                  if (_pey!.puedeHaberseCreado) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Puede que el cobro se haya creado; revise Movimientos antes de reintentar',
                      style: tema.textTheme.bodyMedium,
                    ),
                  ],
                ],
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    style: tema.textTheme.bodyLarge?.copyWith(
                      color: tema.colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  key: const Key('boton_cobrar'),
                  onPressed: _guardando ? null : _cobrar,
                  child: _guardando
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(_pey != null ? 'Reintentar' : 'Cobrar'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
