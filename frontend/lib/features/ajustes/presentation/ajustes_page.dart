import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';

/// Ajustes: datos de la cuenta, opciones y salir.
class AjustesPage extends ConsumerWidget {
  const AjustesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sesion = ref.watch(sesionNotifierProvider);
    final estado = sesion.estado;
    final tema = Theme.of(context);
    final suave = tema.colorScheme.onSurfaceVariant;

    final nombre = estado == null
        ? ''
        : [
            estado.nombre.trim(),
            estado.apellidos.trim(),
          ].where((p) => p.isNotEmpty).join(' ');
    final correo = estado?.correo.trim() ?? '';
    final comercio = estado?.comercio?.nombre ?? 'Sin comercio asignado';
    final fuenteInicial = estado == null ? '' : estado.nombreParaSaludo.trim();
    final inicial = fuenteInicial.isEmpty
        ? 'U'
        : fuenteInicial.substring(0, 1).toUpperCase();

    return Scaffold(
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                kMargenPantalla,
                TfSpace.s6,
                kMargenPantalla,
                TfSpace.s6,
              ),
              children: [
                Text('Ajustes', style: tema.textTheme.headlineLarge),
                const SizedBox(height: TfSpace.s5),
                if (estado != null)
                  Card(
                    margin: EdgeInsets.zero,
                    child: Padding(
                      padding: const EdgeInsets.all(TfSpace.s5),
                      child: Row(
                        children: [
                          ExcludeSemantics(
                            child: Container(
                              width: 48,
                              height: 48,
                              decoration: BoxDecoration(
                                color: tema.colorScheme.primaryContainer,
                                shape: BoxShape.circle,
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                inicial,
                                style: tema.textTheme.headlineSmall?.copyWith(
                                  color: tema.colorScheme.onPrimaryContainer,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: TfSpace.s4),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (nombre.isNotEmpty)
                                  Text(
                                    nombre,
                                    style: tema.textTheme.titleMedium,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                if (correo.isNotEmpty)
                                  Text(
                                    correo,
                                    style: tema.textTheme.bodyMedium?.copyWith(
                                      color: suave,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                const SizedBox(height: TfSpace.s1),
                                Text(
                                  comercio,
                                  style: tema.textTheme.bodyMedium?.copyWith(
                                    color: suave,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: TfSpace.s4),
                Card(
                  margin: EdgeInsets.zero,
                  clipBehavior: Clip.antiAlias,
                  child: Column(
                    children: [
                      ListTile(
                        key: const Key('boton_registrar_clabe'),
                        minTileHeight: TfSize.touchMin + 8,
                        leading: const Icon(Icons.account_balance_rounded),
                        title: const Text('Registrar CLABE'),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => context.push(kRutaRegistrarClabe),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        key: const Key('opcion_mi_qr'),
                        minTileHeight: TfSize.touchMin + 8,
                        leading: const Icon(Icons.qr_code_rounded),
                        title: const Text('Mi QR'),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => context.push(kRutaMiQr),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: TfSpace.s8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    key: const Key('boton_salir'),
                    onPressed: sesion.cargando
                        ? null
                        : () async {
                            await ref
                                .read(sesionNotifierProvider.notifier)
                                .salir();
                            if (context.mounted) {
                              context.go(kRutaEntrar);
                            }
                          },
                    icon: sesion.cargando
                        ? const SizedBox.shrink()
                        : const Icon(Icons.logout_rounded, size: 20),
                    label: sesion.cargando
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Salir'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: tema.colorScheme.onSurfaceVariant,
                      disabledForegroundColor:
                          tema.colorScheme.onSurfaceVariant,
                      minimumSize: const Size.fromHeight(TfSize.touchMin),
                      side: BorderSide(color: tema.colorScheme.outlineVariant),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(TfRadius.md),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
