import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../../cobro/presentation/qr_general_impreso_page.dart';
import '../../movimientos/data/movimiento.dart';
import '../data/venta.dart';
import '../data/venta_repository.dart';
import 'venta_providers.dart';

/// Concepto que el API usa cuando llega vacío.
const kConceptoPorDefecto = 'Transferencia';

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

  final _celularController = TextEditingController();
  var _aCelular = false;
  var _prellenado = false;

  var _guardando = false;
  String? _error;
  PeyException? _pey;
  var _cuentaInactiva = false;

  @override
  void initState() {
    super.initState();
    _conceptoController.text = kConceptoPorDefecto;
    _montoController.addListener(_alCambiarMonto);
  }

  void _alCambiarMonto() => setState(() {});

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_prellenado) {
      return;
    }
    _prellenado = true;
    final consulta =
        GoRouter.maybeOf(context)?.routeInformationProvider.value.uri
            .queryParameters;
    if (consulta == null) {
      return;
    }
    _montoController.text = consulta['monto'] ?? '';
    final concepto = consulta['concepto'];
    if (concepto != null && concepto.isNotEmpty) {
      _conceptoController.text = concepto;
    }
    _referenciaController.text = consulta['referencia'] ?? '';
  }

  @override
  void dispose() {
    _montoController.removeListener(_alCambiarMonto);
    _celularController.dispose();
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
      final referencia = _referenciaController.text.trim();
      final venta = _aCelular
          ? await _repositorio.crearNotificacion(
              monto: _montoController.text,
              telefono: _celularController.text,
              concepto: _conceptoController.text,
              referencia: referencia,
            )
          : await _repositorio.crear(
              monto: _montoController.text,
              concepto: _conceptoController.text,
              referencia: referencia,
            );
      if (!mounted) {
        return;
      }
      final consulta = <String, String>{
        if (referencia.isNotEmpty) 'ref': referencia,
        if (venta.telefonoFinal != null) 'tel': venta.telefonoFinal!,
      };
      context.push(
        Uri(
          path: '/venta/${venta.movimientoId}',
          queryParameters: consulta.isEmpty ? null : consulta,
        ).toString(),
      );
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
    final tf = tema.extension<TfColors>()!;
    final colores = tema.colorScheme;
    final montoValido = validarMontoVenta(_montoController.text) == null;
    final etiquetaCobrar = montoValido
        ? 'Cobrar ${formatearMonto(_montoController.text.trim())}'
        : 'Cobrar';

    InputDecoration campo({String? hint, Widget? icono, String? prefijo}) {
      return InputDecoration(
        hintText: hint,
        prefixIcon: icono,
        prefixText: prefijo,
      );
    }

    Widget etiqueta(String texto, {String? extra}) {
      return Padding(
        padding: const EdgeInsets.only(bottom: TfSpace.s2),
        child: Text.rich(
          TextSpan(
            text: texto,
            children: [
              if (extra != null)
                TextSpan(
                  text: ' $extra',
                  style: TextStyle(
                    color: colores.onSurfaceVariant,
                    fontWeight: FontWeight.w400,
                  ),
                ),
            ],
          ),
          style: tema.textTheme.titleSmall,
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        scrolledUnderElevation: 0,
        title: Text('Nuevo cobro', style: tema.textTheme.headlineMedium),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  child: TfPantalla(
                    padding: const EdgeInsets.symmetric(
                      horizontal: kMargenPantalla,
                      vertical: TfSpace.s2,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _CampoMonto(controller: _montoController),
                        const SizedBox(height: TfSpace.s5),
                        etiqueta('Concepto'),
                        TextFormField(
                          key: const Key('campo_concepto'),
                          controller: _conceptoController,
                          maxLength: 40,
                          decoration: campo(
                            hint: kConceptoPorDefecto,
                            icono: const Icon(Icons.edit_rounded),
                          ),
                        ),
                        const SizedBox(height: TfSpace.s2),
                        etiqueta('Referencia', extra: '(opcional)'),
                        TextFormField(
                          key: const Key('campo_referencia'),
                          controller: _referenciaController,
                          keyboardType: TextInputType.number,
                          decoration: campo(hint: 'Ej. 4521'),
                          validator: (valor) =>
                              validarReferenciaVenta(valor ?? ''),
                        ),
                        const SizedBox(height: TfSpace.s4),
                        SegmentedButton<bool>(
                          key: const Key('selector_canal'),
                          showSelectedIcon: false,
                          segments: const [
                            ButtonSegment(
                              value: false,
                              icon: Icon(Icons.qr_code_2_rounded),
                              label: Text('QR'),
                            ),
                            ButtonSegment(
                              value: true,
                              icon: Icon(Icons.smartphone_rounded),
                              label: Text('A su celular'),
                            ),
                          ],
                          selected: {_aCelular},
                          onSelectionChanged: (valor) =>
                              setState(() => _aCelular = valor.first),
                        ),
                        if (_aCelular) ...[
                          const SizedBox(height: TfSpace.s4),
                          etiqueta('Celular'),
                          TextFormField(
                            key: const Key('campo_celular'),
                            controller: _celularController,
                            keyboardType: TextInputType.phone,
                            maxLength: 10,
                            inputFormatters: [
                              FilteringTextInputFormatter.digitsOnly,
                            ],
                            decoration: campo(
                              hint: '10 dígitos',
                              prefijo: '+52  ',
                            ).copyWith(counterText: ''),
                            validator: (valor) =>
                                validarCelularVenta(valor ?? ''),
                          ),
                        ],
                        if (_cuentaInactiva) ...[
                          const SizedBox(height: TfSpace.s4),
                          const TfAvisoError(
                            titulo: kMensajeCuentaNoActivaQr,
                          ),
                        ],
                        if (_pey != null) ...[
                          const SizedBox(height: TfSpace.s4),
                          TfAvisoError(
                            titulo: _pey!.mensaje,
                            mensaje: _pey!.puedeHaberseCreado
                                ? 'Puede que el cobro se haya creado; revisa Movimientos antes de reintentar'
                                : null,
                          ),
                        ],
                        if (_error != null) ...[
                          const SizedBox(height: TfSpace.s4),
                          TfAvisoError(titulo: _error!),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  kMargenPantalla,
                  TfSpace.s2,
                  kMargenPantalla,
                  TfSpace.s4,
                ),
                child: TfCobrarButton(
                  key: const Key('boton_cobrar'),
                  onPressed: _guardando ? null : _cobrar,
                  child: _guardando
                      ? SizedBox(
                          height: TfSize.icon,
                          width: TfSize.icon,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: tf.onAccent,
                          ),
                        )
                      : Text(_pey != null ? 'Reintentar' : etiquetaCobrar),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Tarjeta del monto: borde primary de 2 px, etiqueta y cifra grande.
class _CampoMonto extends StatelessWidget {
  const _CampoMonto({required this.controller});

  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final colores = tema.colorScheme;
    final estiloMonto = tema.textTheme.displaySmall?.copyWith(
      fontWeight: FontWeight.w800,
    );

    return FormField<String>(
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: (_) => validarMontoVenta(controller.text),
      builder: (estado) {
        final hayError = estado.hasError;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: TfSpace.s4,
                vertical: TfSpace.s3,
              ),
              decoration: BoxDecoration(
                color: tema.cardTheme.color ?? colores.surfaceContainerLowest,
                borderRadius: BorderRadius.circular(TfRadius.md),
                border: Border.all(
                  color: hayError ? tf.expired : colores.primary,
                  width: 2,
                ),
              ),
              child: Column(
                children: [
                  Text(
                    '¿Cuánto vas a cobrar?',
                    style: tema.textTheme.bodyMedium?.copyWith(
                      color: colores.onSurfaceVariant,
                    ),
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Text(
                        '\$',
                        style: estiloMonto?.copyWith(
                          color: colores.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: TfSpace.s1),
                      Flexible(
                        child: IntrinsicWidth(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(minWidth: 96),
                            child: TextField(
                              key: const Key('campo_monto'),
                              controller: controller,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                decimal: true,
                              ),
                              textAlign: TextAlign.center,
                              style: estiloMonto,
                              onChanged: estado.didChange,
                              decoration: InputDecoration(
                                hintText: '0.00',
                                hintStyle: estiloMonto?.copyWith(
                                  color: colores.onSurfaceVariant
                                      .withValues(alpha: 0.5),
                                ),
                                filled: false,
                                border: InputBorder.none,
                                enabledBorder: InputBorder.none,
                                focusedBorder: InputBorder.none,
                                errorBorder: InputBorder.none,
                                focusedErrorBorder: InputBorder.none,
                                contentPadding: EdgeInsets.zero,
                                isDense: true,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (hayError)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s2),
                child: Text(
                  estado.errorText!,
                  style: tema.textTheme.bodySmall?.copyWith(
                    color: tf.expiredText,
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
