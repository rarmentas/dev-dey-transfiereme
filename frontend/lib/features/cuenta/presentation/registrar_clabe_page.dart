import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../data/clabe.dart';
import '../data/clabe_repository.dart';
import 'cuenta_providers.dart';

class RegistrarClabePage extends ConsumerStatefulWidget {
  const RegistrarClabePage({super.key, this.repositorio});

  /// Si viene, las pruebas no dependen del provider global.
  final ClabeRepository? repositorio;

  @override
  ConsumerState<RegistrarClabePage> createState() => _RegistrarClabePageState();
}

class _RegistrarClabePageState extends ConsumerState<RegistrarClabePage> {
  final _formKey = GlobalKey<FormState>();
  final _clabeController = TextEditingController();

  var _guardando = false;
  String? _error;
  String? _guardada;

  @override
  void dispose() {
    _clabeController.dispose();
    super.dispose();
  }

  ClabeRepository get _repositorio =>
      widget.repositorio ?? ref.read(clabeRepositoryProvider);

  Future<void> _guardar() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _guardando = true;
      _error = null;
      _guardada = null;
    });
    try {
      final clabe = await _repositorio.guardar(_clabeController.text);
      if (!mounted) {
        return;
      }
      setState(() => _guardada = clabe);
    } on ClabeApiException catch (error) {
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

    return Scaffold(
      appBar: AppBar(title: const Text('Registrar CLABE')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(
                horizontal: kMargenPantalla,
                vertical: TfSpace.s6,
              ),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Pey usa esta cuenta para cobrar. El QR aparece cuando la marca activa.',
                      style: tema.textTheme.bodyLarge?.copyWith(
                        color: tema.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: TfSpace.s6),
                    TextFormField(
                      key: const Key('campo_clabe'),
                      controller: _clabeController,
                      keyboardType: TextInputType.number,
                      maxLength: 18,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                      decoration: const InputDecoration(
                        labelText: 'CLABE',
                        helperText: '18 dígitos de su cuenta.',
                      ),
                      validator: (valor) => validarClabe(valor ?? ''),
                    ),
                    if (_guardada != null) ...[
                      const SizedBox(height: TfSpace.s4),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(TfSpace.s4),
                        decoration: BoxDecoration(
                          color: tf.paidContainer,
                          borderRadius: BorderRadius.circular(TfRadius.md),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              Icons.check_circle_rounded,
                              color: tf.paidText,
                              size: TfSize.icon,
                            ),
                            const SizedBox(width: TfSpace.s3),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'CLABE guardada.',
                                    style: (tema.textTheme.titleSmall ??
                                            const TextStyle())
                                        .copyWith(
                                      color: tf.paidText,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const SizedBox(height: TfSpace.s1),
                                  Text(
                                    _guardada!,
                                    style: (tema.textTheme.bodyMedium ??
                                            const TextStyle())
                                        .copyWith(
                                      color: tema.colorScheme.onSurface,
                                      fontFeatures: kTabular,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: TfSpace.s4),
                      TfAvisoError(titulo: _error!),
                    ],
                    const SizedBox(height: TfSpace.s6),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton(
                        key: const Key('boton_guardar_clabe'),
                        onPressed: _guardando ? null : _guardar,
                        child: _guardando
                            ? const SizedBox(
                                height: 22,
                                width: 22,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Guardar'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
