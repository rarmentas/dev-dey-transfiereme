import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../../cuenta/presentation/cuenta_pey_mensajes.dart';
import '../../cuenta/presentation/cuenta_providers.dart';
import 'cobro_providers.dart';
import 'qr_general_impreso_page.dart';

/// Contenedor de «Mi QR»: pide el QR general y lo muestra o explica el bloqueo.
class MiQrPage extends ConsumerWidget {
  const MiQrPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final qr = ref.watch(qrGeneralProvider);
    final estado = ref.watch(cuentaEstadoProvider);
    final est = estado.asData?.value;

    return qr.when(
      skipLoadingOnRefresh: false,
      data: (resultado) => resultado.cuentaNoActiva
          ? QrGeneralImpresoPage(
              puedeMostrarQr: false,
              tituloBloqueo: tituloBloqueoCuenta(est),
              mensajeSiguiente: mensajeSiguientePaso(est),
            )
          : QrGeneralImpresoPage(
              puedeMostrarQr: true,
              qrString: resultado.qrString,
            ),
      loading: () => Scaffold(
        appBar: appBarMiQr(),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Scaffold(
        appBar: appBarMiQr(),
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                child: ConstrainedBox(
                  constraints: BoxConstraints(minHeight: constraints.maxHeight),
                  child: Center(
                    child: TfPantalla(
                      padding: const EdgeInsets.all(kMargenPantalla),
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
              );
            },
          ),
        ),
      ),
    );
  }
}
