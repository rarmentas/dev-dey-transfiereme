import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';

/// Lado mínimo del QR en pantalla (`qr-screen` en diseño).
const double kLadoMinimoQrPantalla = 232;

/// Alineado con [CuentaNoActiveError] del API `POST /api/cobro/qr-general/`.
const String kMensajeCuentaNoActivaQr =
    'Tu cuenta aún no está activa para generar un código de cobro.';

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
      appBar: AppBar(
        title: Text(
          'Mi QR',
          style: tema.textTheme.headlineMedium,
        ),
      ),
      body: SafeArea(
        child: TfPantalla(
          padding: const EdgeInsets.symmetric(
            horizontal: kMargenPantalla,
            vertical: TfSpace.s6,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: puedeMostrarQr
                    ? _MarcoQr(qrString: qrString!.trim())
                    : const _EstadoCuentaPendiente(),
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
  const _EstadoCuentaPendiente();

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;

    return Container(
      width: kLadoMinimoQrPantalla + (TfSpace.s4 * 2),
      padding: const EdgeInsets.symmetric(
        horizontal: TfSpace.s5,
        vertical: TfSpace.s8,
      ),
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
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(TfSpace.s4),
            decoration: BoxDecoration(
              color: tf.pendingContainer,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.schedule_rounded,
              size: 56,
              color: tf.pendingText,
            ),
          ),
          const SizedBox(height: TfSpace.s5),
          Text(
            kMensajeCuentaNoActivaQr,
            textAlign: TextAlign.center,
            style: (tema.textTheme.bodyMedium ?? const TextStyle()).copyWith(
              color: TfColors.light.pendingText,
            ),
          ),
        ],
      ),
    );
  }
}
