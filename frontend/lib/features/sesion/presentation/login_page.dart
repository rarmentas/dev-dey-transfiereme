import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';
import 'olvido_contrasena_modal.dart';
import 'registro_cuenta_modal.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key, this.mensajeInicial});

  final String? mensajeInicial;

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _correoController = TextEditingController();
  final _contrasenaController = TextEditingController();

  @override
  void initState() {
    super.initState();
    final aviso = widget.mensajeInicial;
    if (aviso != null && aviso.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) {
          return;
        }
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(aviso)));
      });
    }
  }

  @override
  void dispose() {
    _correoController.dispose();
    _contrasenaController.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    final ok = await ref
        .read(sesionNotifierProvider.notifier)
        .entrar(
          correo: _correoController.text.trim(),
          contrasena: _contrasenaController.text,
        );
    if (ok && mounted) {
      context.go(kRutaInicio);
    }
  }

  Future<void> _abrirOlvido() async {
    final mensaje = await mostrarOlvidoContrasenaModal(context: context);
    if (!mounted || mensaje == null || mensaje.isEmpty) {
      return;
    }
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(mensaje)));
  }

  @override
  Widget build(BuildContext context) {
    final sesion = ref.watch(sesionNotifierProvider);
    final tema = Theme.of(context);

    final etiqueta = tema.textTheme.titleSmall;

    final superior = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Align(
          alignment: Alignment.centerLeft,
          child: TfLogo(width: 200),
        ),
        const SizedBox(height: TfSpace.s8),
        Text(
          'Entra a cobrar',
          style: tema.textTheme.headlineLarge,
          textAlign: TextAlign.start,
        ),
        const SizedBox(height: TfSpace.s2),
        Text(
          'Con tu correo y contraseña de Transfiéreme.',
          style: tema.textTheme.bodyMedium?.copyWith(
            color: tema.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.start,
        ),
        const SizedBox(height: TfSpace.s6),
        Text('Correo', style: etiqueta),
        const SizedBox(height: TfSpace.s2),
        TextFormField(
          key: const Key('campo_correo'),
          controller: _correoController,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.mail_outline_rounded),
          ),
          validator: (v) {
            if (v == null || v.trim().isEmpty) {
              return 'Escribe tu correo.';
            }
            return null;
          },
        ),
        const SizedBox(height: TfSpace.s4),
        Text('Contraseña', style: etiqueta),
        const SizedBox(height: TfSpace.s2),
        TextFormField(
          key: const Key('campo_contrasena'),
          controller: _contrasenaController,
          obscureText: true,
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.lock_outline_rounded),
          ),
          validator: (v) {
            if (v == null || v.isEmpty) {
              return 'Escribe tu contraseña.';
            }
            return null;
          },
        ),
        if (sesion.errorMensaje != null) ...[
          const SizedBox(height: TfSpace.s4),
          TfAvisoError(titulo: sesion.errorMensaje!),
        ],
        const SizedBox(height: TfSpace.s6),
        SizedBox(
          width: double.infinity,
          height: 52,
          child: FilledButton(
            key: const Key('boton_entrar'),
            onPressed: sesion.cargando ? null : _enviar,
            child: sesion.cargando
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Entrar'),
          ),
        ),
        const SizedBox(height: TfSpace.s2),
        Center(
          child: TextButton(
            onPressed: sesion.cargando ? null : _abrirOlvido,
            child: const Text('¿Olvidaste tu contraseña?'),
          ),
        ),
      ],
    );

    final inferior = Padding(
      padding: const EdgeInsets.only(top: TfSpace.s4),
      child: Center(
        child: Wrap(
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              '¿Nuevo? ',
              style: tema.textTheme.bodyMedium?.copyWith(
                color: tema.colorScheme.onSurfaceVariant,
              ),
            ),
            TextButton(
              onPressed: sesion.cargando
                  ? null
                  : () => mostrarRegistroCuentaModal(context: context),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: const Size(48, 48),
              ),
              child: const Text('Crea tu cuenta'),
            ),
          ],
        ),
      ),
    );

    const arriba = TfSpace.s6;
    const abajo = TfSpace.s4;

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, restricciones) {
            return SingleChildScrollView(
              child: TfPantalla(
                padding: const EdgeInsets.fromLTRB(
                  kMargenPantalla,
                  arriba,
                  kMargenPantalla,
                  abajo,
                ),
                child: Form(
                  key: _formKey,
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      minHeight: restricciones.maxHeight - arriba - abajo,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [superior, inferior],
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
