import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../theme/transfiereme_theme.dart';

/// Lado mínimo del QR en pantalla (`qr-screen` en diseño).
const double kLadoMinimoQrPantalla = 232;

/// Muestra el QR general codificado desde [qrString] (mensaje CoDi, C8).
class QrGeneralImpresoPage extends StatelessWidget {
  const QrGeneralImpresoPage({super.key, required this.qrString});

  final String qrString;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    const marcoRadius = BorderRadius.all(Radius.circular(20));

    return Scaffold(
      appBar: AppBar(title: const Text('Mi QR')),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                DecoratedBox(
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
                ),
                const SizedBox(height: 24),
                Text(
                  'Su cliente puede pagar con CoDi desde la aplicación de su banco.',
                  textAlign: TextAlign.center,
                  style: tema.textTheme.bodyLarge,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
