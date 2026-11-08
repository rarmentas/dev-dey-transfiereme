import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/sesion/registro_olvido_repository.dart';
import '../../../core/sesion/sesion_providers.dart';
import '../../../core/sesion/sesion_repository.dart';
import 'widgets/reenvio_codigo_button.dart';

enum _PasoOlvido { correo, restablecer }

Future<String?> mostrarOlvidoContrasenaModal({
  required BuildContext context,
}) {
  return showDialog<String?>(
    context: context,
    barrierDismissible: true,
    builder: (dialogContext) {
      return Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: OlvidoContrasenaModal(
            onCerrar: () => Navigator.of(dialogContext).pop(),
            onExito: (mensaje) => Navigator.of(dialogContext).pop(mensaje),
          ),
        ),
      );
    },
  );
}

class OlvidoContrasenaModal extends ConsumerStatefulWidget {
  const OlvidoContrasenaModal({
    super.key,
    required this.onCerrar,
    required this.onExito,
  });

  final VoidCallback onCerrar;
  final void Function(String mensaje) onExito;

  @override
  ConsumerState<OlvidoContrasenaModal> createState() =>
      _OlvidoContrasenaModalState();
}

class _OlvidoContrasenaModalState extends ConsumerState<OlvidoContrasenaModal> {
  final _formKey = GlobalKey<FormState>();
  final _correoController = TextEditingController();
  final _codigoController = TextEditingController();
  final _contrasenaController = TextEditingController();
  final _confirmarController = TextEditingController();

  _PasoOlvido _paso = _PasoOlvido.correo;
  String _correoGuardado = '';
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _correoController.dispose();
    _codigoController.dispose();
    _contrasenaController.dispose();
    _confirmarController.dispose();
    super.dispose();
  }

  RegistroOlvidoRepository get _repo => ref.read(registroOlvidoRepositoryProvider);

  Future<void> _solicitarCodigo() async {
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
      setState(() {
        _correoGuardado = correo;
        _paso = _PasoOlvido.restablecer;
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
      await _repo.solicitarOlvido(correo: _correoGuardado);
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

  Future<void> _restablecer() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final mensaje = await _repo.restablecerOlvido(
        correo: _correoGuardado,
        codigo: _codigoController.text.trim(),
        contrasena: _contrasenaController.text,
      );
      if (!mounted) {
        return;
      }
      widget.onExito(mensaje);
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
    final titulo = _paso == _PasoOlvido.correo
        ? 'Recupere su contraseña'
        : 'Nueva contraseña';

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
              if (_paso == _PasoOlvido.correo) ...[
                Text(
                  'Indique el correo de su cuenta. Si existe, le enviaremos un código.',
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
              ] else ...[
                Text(
                  'Escriba el código enviado a $_correoGuardado y su nueva contraseña.',
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
                const SizedBox(height: 12),
                TextFormField(
                  controller: _contrasenaController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Nueva contraseña',
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
                    : (_paso == _PasoOlvido.correo
                        ? _solicitarCodigo
                        : _restablecer),
                child: _cargando
                    ? const SizedBox(
                        height: 22,
                        width: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        _paso == _PasoOlvido.correo
                            ? 'Enviar código'
                            : 'Actualizar contraseña',
                      ),
              ),
          ],
        ),
      ),
    );
  }
}
