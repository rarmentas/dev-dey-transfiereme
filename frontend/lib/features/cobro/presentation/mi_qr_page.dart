import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import 'cobro_providers.dart';
import 'qr_general_impreso_page.dart';

/// Contenedor de «Mi QR»: pide el QR general y lo muestra o explica el bloqueo.
class MiQrPage extends ConsumerWidget {
  const MiQrPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final qr = ref.watch(qrGeneralProvider);

    return qr.when(
      skipLoadingOnRefresh: false,
      data: (resultado) => resultado.cuentaNoActiva
          ? const QrGeneralImpresoPage(puedeMostrarQr: false)
          : QrGeneralImpresoPage(
              puedeMostrarQr: true,
              qrString: resultado.qrString,
            ),
      loading: () => Scaffold(
        appBar: AppBar(title: const Text('Mi QR')),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Scaffold(
        appBar: AppBar(title: const Text('Mi QR')),
        body: SafeArea(
          child: TfPantalla(
            padding: const EdgeInsets.all(kMargenPantalla),
            child: Center(
              child: TfAvisoError(
                titulo: 'No pudimos cargar tu código',
                mensaje: error.toString(),
                accion: OutlinedButton(
                  key: const Key('boton_reintentar_qr'),
                  onPressed: () => ref.invalidate(qrGeneralProvider),
                  child: const Text('Reintentar'),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
