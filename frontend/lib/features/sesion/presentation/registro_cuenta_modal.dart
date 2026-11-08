import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/registro_olvido_repository.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/sesion/sesion_providers.dart';
import '../../../core/sesion/sesion_repository.dart';
import '../../../core/ui/ui.dart';
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
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(TfRadius.xl),
        ),
        clipBehavior: Clip.antiAlias,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
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
            if (_paso == _PasoRegistro.datos) ...[
              Text(
                'Indique su correo y contraseña. Le enviaremos un código de confirmación.',
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
                    return 'Indique su correo.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: TfSpace.s3),
              TextFormField(
                controller: _contrasenaController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Contraseña',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
                ),
                validator: (v) {
                  if (v == null || v.isEmpty) {
                    return 'Indique su contraseña.';
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
                  labelText: 'Confirme su contraseña',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
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
                    return 'Indique el código.';
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
            ),
          ],
        ),
      ),
    );
  }
}
