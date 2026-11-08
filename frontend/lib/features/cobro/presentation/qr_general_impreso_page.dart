import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/router/app_router.dart';
import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';

/// Lado mínimo del QR en pantalla (`qr-screen` en diseño).
const double kLadoMinimoQrPantalla = 232;

/// Alineado con [CuentaNoActiveError] del API `POST /api/cobro/qr-general/`.
const String kMensajeCuentaNoActivaQr =
    'Tu cuenta aún no está activa para generar un código de cobro.';

/// Qué sigue cuando la cuenta todavía no puede cobrar.
const String kMensajeQrAlActivar =
    'Cuando tu cuenta se active, aquí verás tu QR para imprimir.';

/// Barra de «Mi QR» con salida aunque la ruta se abra sin historial.
AppBar appBarMiQr() {
  return AppBar(leading: const BotonVolverMiQr(), title: const Text('Mi QR'));
}

/// Vuelve atrás, o a Inicio si no hay a dónde regresar.
class BotonVolverMiQr extends StatelessWidget {
  const BotonVolverMiQr({super.key});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: 'Volver',
      onPressed: () {
        if (context.canPop()) {
          context.pop();
        } else {
          context.go(kRutaInicio);
        }
      },
      icon: const Icon(Icons.arrow_back_rounded),
    );
  }
}

/// Pantalla «Mi QR»: código CoDi cobrable o bloqueo si la cuenta no está ACTIVE (C13).
///
/// [puedeMostrarQr] lo resuelve el contenedor (p. ej. tras alta QR en servidor).
/// Con [puedeMostrarQr] en `true`, [qrString] debe ser la cadena CoDi no vacía.
class QrGeneralImpresoPage extends StatelessWidget {
  const QrGeneralImpresoPage({
    super.key,
    required this.puedeMostrarQr,
    this.qrString,
    this.tituloBloqueo,
    this.mensajeSiguiente,
  });

  final bool puedeMostrarQr;
  final String? qrString;
  final String? tituloBloqueo;
  final String? mensajeSiguiente;

  @override
  Widget build(BuildContext context) {
    assert(() {
      if (puedeMostrarQr) {
        assert(
          qrString != null && qrString!.trim().isNotEmpty,
          'qrString no vacío cuando puedeMostrarQr es true',
        );
      }
      return true;
    }());

    final tema = Theme.of(context);

    return Scaffold(
      appBar: appBarMiQr(),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: Center(
                  child: TfPantalla(
                    padding: const EdgeInsets.symmetric(
                      horizontal: kMargenPantalla,
                      vertical: TfSpace.s6,
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (puedeMostrarQr)
                          Center(child: _MarcoQr(qrString: qrString!.trim()))
                        else
                          _EstadoCuentaPendiente(
                            titulo: tituloBloqueo ?? kMensajeCuentaNoActivaQr,
                            mensaje: mensajeSiguiente ?? kMensajeQrAlActivar,
                          ),
                        if (puedeMostrarQr) ...[
                          const SizedBox(height: TfSpace.s6),
                          Text(
                            'Tu cliente puede pagar con CoDi desde la app de su banco.',
                            textAlign: TextAlign.center,
                            style: tema.textTheme.bodyMedium?.copyWith(
                              color: tema.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ],
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

class _MarcoQr extends StatelessWidget {
  const _MarcoQr({required this.qrString});

  final String qrString;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(TfSpace.s4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(TfRadius.xl),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: QrImageView(
        data: qrString,
        size: kLadoMinimoQrPantalla,
        backgroundColor: Colors.white,
        errorCorrectionLevel: QrErrorCorrectLevel.H,
      ),
    );
  }
}

class _EstadoCuentaPendiente extends StatelessWidget {
  const _EstadoCuentaPendiente({
    required this.titulo,
    required this.mensaje,
  });

  final String titulo;
  final String mensaje;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final colores = tema.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: TfSpace.s5,
          vertical: TfSpace.s6,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: tf.pendingContainer,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Icon(
                Icons.schedule_rounded,
                size: 32,
                color: tf.pendingText,
              ),
            ),
            const SizedBox(height: TfSpace.s5),
            Text(
              titulo,
              textAlign: TextAlign.center,
              style: tema.textTheme.headlineSmall?.copyWith(
                color: colores.onSurface,
              ),
            ),
            const SizedBox(height: TfSpace.s2),
            Text(
              mensaje,
              textAlign: TextAlign.center,
              style: tema.textTheme.bodyMedium?.copyWith(
                color: colores.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
