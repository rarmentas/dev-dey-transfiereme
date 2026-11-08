import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../theme/transfiereme_theme.dart';

/// Lado mínimo del QR en pantalla (`qr-screen` en diseño).
const double kLadoMinimoQrPantalla = 232;

/// Alineado con [CuentaNoActiveError] del API `POST /api/cobro/qr-general/`.
const String kMensajeCuentaNoActivaQr =
    'Su cuenta aún no está activa para generar un código de cobro.';

/// Pantalla «Mi QR»: código CoDi cobrable o bloqueo si la cuenta no está ACTIVE (C13).
///
/// [puedeMostrarQr] lo resuelve el contenedor (p. ej. tras alta QR en servidor).
/// Con [puedeMostrarQr] en `true`, [qrString] debe ser la cadena CoDi no vacía.
class QrGeneralImpresoPage extends StatelessWidget {
  const QrGeneralImpresoPage({
    super.key,
    required this.puedeMostrarQr,
    this.qrString,
  });

  final bool puedeMostrarQr;
  final String? qrString;

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
      appBar: AppBar(title: const Text('Mi QR')),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                puedeMostrarQr
                    ? _MarcoQr(qrString: qrString!.trim())
                    : const _EstadoCuentaPendiente(),
                if (puedeMostrarQr) ...[
                  const SizedBox(height: 24),
                  Text(
                    'Su cliente puede pagar con CoDi desde la aplicación de su banco.',
                    textAlign: TextAlign.center,
                    style: tema.textTheme.bodyLarge,
                  ),
                ],
              ],
            ),
          ),
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
    final tf = Theme.of(context).extension<TfColors>()!;
    const marcoRadius = BorderRadius.all(Radius.circular(20));

    return DecoratedBox(
      decoration: BoxDecoration(
        color: tf.accent,
        borderRadius: marcoRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: DecoratedBox(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: marcoRadius,
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: QrImageView(
              data: qrString,
              size: kLadoMinimoQrPantalla,
              backgroundColor: Colors.white,
              errorCorrectionLevel: QrErrorCorrectLevel.H,
            ),
          ),
        ),
      ),
    );
  }
}

class _EstadoCuentaPendiente extends StatelessWidget {
  const _EstadoCuentaPendiente();

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    const marcoRadius = BorderRadius.all(Radius.circular(20));

    return DecoratedBox(
      decoration: BoxDecoration(
        color: tf.accent,
        borderRadius: marcoRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: DecoratedBox(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: marcoRadius,
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 32),
            child: SizedBox(
              width: kLadoMinimoQrPantalla,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: tf.pendingContainer,
                      shape: BoxShape.circle,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Icon(
                        Icons.schedule,
                        size: 56,
                        color: tf.pendingText,
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    kMensajeCuentaNoActivaQr,
                    textAlign: TextAlign.center,
                    style: tema.textTheme.bodyLarge?.copyWith(
                      // Tarjeta interior siempre blanca: tinta del tema claro (AA).
                      color: TfColors.light.pendingText,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
