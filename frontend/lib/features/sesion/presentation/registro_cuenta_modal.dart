import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/registro_olvido_repository.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/sesion/sesion_providers.dart';
import '../../../core/sesion/sesion_repository.dart';
import 'widgets/reenvio_codigo_button.dart';

enum _PasoRegistro { datos, codigo }

Future<void> mostrarRegistroCuentaModal({
  required BuildContext context,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: true,
    builder: (dialogContext) {
      return Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: RegistroCuentaModal(
            onCerrar: () => Navigator.of(dialogContext).pop(),
            despuesDeEntrar: () {
              if (context.mounted) {
                context.go(kRutaInicio);
              }
            },
          ),
        ),
      );
    },
  );
}

class RegistroCuentaModal extends ConsumerStatefulWidget {
  const RegistroCuentaModal({
    super.key,
    required this.onCerrar,
    required this.despuesDeEntrar,
  });

  final VoidCallback onCerrar;
  final VoidCallback despuesDeEntrar;

  @override
  ConsumerState<RegistroCuentaModal> createState() =>
      _RegistroCuentaModalState();
}

class _RegistroCuentaModalState extends ConsumerState<RegistroCuentaModal> {
  final _formKey = GlobalKey<FormState>();
  final _correoController = TextEditingController();
  final _contrasenaController = TextEditingController();
  final _confirmarController = TextEditingController();
  final _codigoController = TextEditingController();

  _PasoRegistro _paso = _PasoRegistro.datos;
  String _correoGuardado = '';
  String _contrasenaGuardada = '';
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _correoController.dispose();
    _contrasenaController.dispose();
    _confirmarController.dispose();
    _codigoController.dispose();
    super.dispose();
  }

  RegistroOlvidoRepository get _repo => ref.read(registroOlvidoRepositoryProvider);

  Future<void> _solicitarAlta() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    final correo = _correoController.text.trim();
    final contrasena = _contrasenaController.text;
    try {
      await _repo.solicitarAlta(correo: correo, contrasena: contrasena);
      if (!mounted) {
        return;
      }
      setState(() {
        _correoGuardado = correo;
        _contrasenaGuardada = contrasena;
        _paso = _PasoRegistro.codigo;
      });
    } on SesionApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.mensaje);
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'No pudimos completar la solicitud. Intente de nuevo.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _cargando = false);
      }
    }
  }

  Future<bool> _reenviarCodigo() async {
    setState(() => _error = null);
    try {
      await _repo.solicitarAlta(
        correo: _correoGuardado,
        contrasena: _contrasenaGuardada,
      );
      return true;
    } on SesionApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.mensaje);
      }
      return false;
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'No pudimos completar la solicitud. Intente de nuevo.',
        );
      }
      return false;
    }
  }

  Future<void> _confirmarYEntrar() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await _repo.confirmarAlta(
        correo: _correoGuardado,
        codigo: _codigoController.text.trim(),
      );
      if (!mounted) {
        return;
      }
      widget.onCerrar();
      final ok = await ref.read(sesionNotifierProvider.notifier).entrar(
            correo: _correoGuardado,
            contrasena: _contrasenaGuardada,
          );
      if (!mounted) {
        return;
      }
      if (ok) {
        widget.despuesDeEntrar();
      }
    } on SesionApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.mensaje);
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'No pudimos completar la solicitud. Intente de nuevo.',
        );
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
    final titulo =
        _paso == _PasoRegistro.datos ? 'Cree su cuenta' : 'Confirme su cuenta';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      child: Form(
        key: _formKey,
        child: ListView(
          shrinkWrap: true,
          padding: EdgeInsets.zero,
          physics: const ClampingScrollPhysics(),
          children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      titulo,
                      style: tema.textTheme.titleLarge,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Cerrar',
                    onPressed: _cargando ? null : widget.onCerrar,
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (_paso == _PasoRegistro.datos) ...[
                Text(
                  'Indique su correo y contraseña. Le enviaremos un código de confirmación.',
                  style: tema.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
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
                const SizedBox(height: 12),
                TextFormField(
                  controller: _contrasenaController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Contraseña',
                    prefixIcon: Icon(Icons.lock_outline),
                  ),
                  validator: (v) {
                    if (v == null || v.isEmpty) {
                      return 'Indique su contraseña.';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  key: const Key('campo_confirmar_contrasena'),
                  controller: _confirmarController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Confirme su contraseña',
                    prefixIcon: Icon(Icons.lock_outline),
                  ),
                  validator: (v) {
                    if (v == null || v.isEmpty) {
                      return 'Confirme su contraseña.';
                    }
                    if (v != _contrasenaController.text) {
                      return 'Las contraseñas no coinciden.';
                    }
                    return null;
                  },
                ),
              ] else ...[
                Text(
                  'Escriba el código de seis dígitos que enviamos a $_correoGuardado.',
                  style: tema.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _codigoController,
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                  decoration: const InputDecoration(
                    labelText: 'Código',
                    prefixIcon: Icon(Icons.pin_outlined),
                    counterText: '',
                  ),
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) {
                      return 'Indique el código.';
                    }
                    return null;
                  },
                ),
                ReenvioCodigoButton(
                  onReenviar: _reenviarCodigo,
                  habilitado: !_cargando,
                  iniciarEnEspera: true,
                ),
              ],
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
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _cargando
                    ? null
                    : (_paso == _PasoRegistro.datos
                        ? _solicitarAlta
                        : _confirmarYEntrar),
                child: _cargando
                    ? const SizedBox(
                        height: 22,
                        width: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        _paso == _PasoRegistro.datos
                            ? 'Continuar'
                            : 'Confirmar cuenta',
                      ),
              ),
          ],
        ),
      ),
    );
  }
}
