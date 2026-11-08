import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    return Scaffold(
      appBar: AppBar(title: const Text('Registrar CLABE')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Pey usa esta cuenta para cobrar. El QR aparece cuando la marca activa.',
                  style: tema.textTheme.bodyLarge,
                ),
                const SizedBox(height: 16),
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
                  const SizedBox(height: 16),
                  Text(
                    'CLABE guardada.',
                    style: tema.textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(_guardada!, style: tema.textTheme.bodyMedium),
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
              ],
            ),
          ),
        ),
      ),
    );
  }
}
