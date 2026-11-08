import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/sesion/registro_olvido_repository.dart';
import '../../../core/sesion/sesion_providers.dart';
import '../../../core/sesion/sesion_repository.dart';
import '../../../core/ui/ui.dart';
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
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(TfRadius.xl),
        ),
        clipBehavior: Clip.antiAlias,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
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
          () => _error = 'No pudimos completar la solicitud. Inténtalo de nuevo.',
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
          () => _error = 'No pudimos completar la solicitud. Inténtalo de nuevo.',
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
          () => _error = 'No pudimos completar la solicitud. Inténtalo de nuevo.',
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
        ? 'Recupera tu contraseña'
        : 'Nueva contraseña';

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: TfSpace.s6,
        vertical: TfSpace.s5,
      ),
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
                    style: tema.textTheme.headlineSmall,
                  ),
                ),
                IconButton(
                  tooltip: 'Cerrar',
                  onPressed: _cargando ? null : widget.onCerrar,
                  icon: const Icon(Icons.close_rounded),
                ),
              ],
            ),
            const SizedBox(height: TfSpace.s2),
            if (_paso == _PasoOlvido.correo) ...[
              Text(
                'Escribe el correo de tu cuenta. Si existe, te enviaremos un código.',
                style: tema.textTheme.bodyMedium?.copyWith(
                  color: tema.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: TfSpace.s5),
              TextFormField(
                controller: _correoController,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                decoration: const InputDecoration(
                  labelText: 'Correo',
                  prefixIcon: Icon(Icons.mail_outline_rounded),
                ),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) {
                    return 'Escribe tu correo.';
                  }
                  return null;
                },
              ),
            ] else ...[
              Text(
                'Escribe el código enviado a $_correoGuardado y tu nueva contraseña.',
                style: tema.textTheme.bodyMedium?.copyWith(
                  color: tema.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: TfSpace.s5),
              TextFormField(
                controller: _codigoController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                decoration: const InputDecoration(
                  labelText: 'Código',
                  prefixIcon: Icon(Icons.pin_rounded),
                  counterText: '',
                ),
                validator: (v) {
                  if (v == null || v.trim().isEmpty) {
                    return 'Escribe el código.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: TfSpace.s3),
              TextFormField(
                controller: _contrasenaController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Nueva contraseña',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
                ),
                validator: (v) {
                  if (v == null || v.isEmpty) {
                    return 'Escribe tu contraseña.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: TfSpace.s3),
              TextFormField(
                key: const Key('campo_confirmar_contrasena'),
                controller: _confirmarController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Confirma tu contraseña',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
                ),
                validator: (v) {
                  if (v == null || v.isEmpty) {
                    return 'Confirma tu contraseña.';
                  }
                  if (v != _contrasenaController.text) {
                    return 'Las contraseñas no coinciden.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: TfSpace.s2),
              Align(
                alignment: Alignment.centerRight,
                child: ReenvioCodigoButton(
                  onReenviar: _reenviarCodigo,
                  habilitado: !_cargando,
                  iniciarEnEspera: true,
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: TfSpace.s4),
              TfAvisoError(titulo: _error!),
            ],
            const SizedBox(height: TfSpace.s5),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: FilledButton(
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
            ),
          ],
        ),
      ),
    );
  }
}
