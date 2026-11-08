import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/registro_olvido_repository.dart';
import '../../../core/sesion/sesion_providers.dart';
import '../../../core/sesion/sesion_repository.dart';

class OlvidoContrasenaPage extends ConsumerStatefulWidget {
  const OlvidoContrasenaPage({super.key});

  @override
  ConsumerState<OlvidoContrasenaPage> createState() =>
      _OlvidoContrasenaPageState();
}

class _OlvidoContrasenaPageState extends ConsumerState<OlvidoContrasenaPage> {
  final _formKey = GlobalKey<FormState>();
  final _correoController = TextEditingController();
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _correoController.dispose();
    super.dispose();
  }

  RegistroOlvidoRepository get _repo => ref.read(registroOlvidoRepositoryProvider);

  Future<void> _enviar() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    final correo = _correoController.text.trim();
    try {
      await _repo.solicitarOlvido(correo: correo);
      if (!mounted) {
        return;
      }
      context.push(kRutaOlvidoRestablecer, extra: correo);
    } on SesionApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.mensaje);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'No pudimos completar la solicitud. Intente de nuevo.');
      }
    } finally {
      if (mounted) {
        setState(() => _cargando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Recupere su contraseña')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Indique el correo de su cuenta. Si existe, le enviaremos un código.',
                      style: tema.textTheme.bodyMedium,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 24),
                    TextFormField(
                      controller: _correoController,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Correo',
                        prefixIcon: Icon(Icons.mail_outline),
                      ),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) {
                          return 'Indique su correo.';
                        }
                        return null;
                      },
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        style: tema.textTheme.bodySmall?.copyWith(
                          color: tema.colorScheme.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _cargando ? null : _enviar,
                      child: _cargando
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Enviar código'),
                    ),
                    TextButton(
                      onPressed: _cargando ? null : () => context.go(kRutaEntrar),
                      child: const Text('Volver al inicio de sesión'),
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
