import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/ui/ui.dart';
import '../../../movimientos/data/movimiento.dart';
import '../../data/venta.dart';

/// Pantalla completa «¡Te pagaron!» en color primary.
class VentaPagadaView extends StatefulWidget {
  const VentaPagadaView({super.key, required this.venta, this.referencia});

  final Venta venta;
  final String? referencia;

  @override
  State<VentaPagadaView> createState() => _VentaPagadaViewState();
}

class _VentaPagadaViewState extends State<VentaPagadaView> {
  @override
  void initState() {
    super.initState();
    HapticFeedback.mediumImpact();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final colores = tema.colorScheme;
    final venta = widget.venta;
    final ref = widget.referencia ?? venta.referencia;
    final detalle = ref == null || ref.isEmpty
        ? venta.concepto
        : '${venta.concepto} · Ref $ref';
    final textoSobre = tema.textTheme.bodyLarge?.copyWith(
      color: colores.onPrimary,
    );
    final iconosClaros =
        ThemeData.estimateBrightnessForColor(colores.primary) ==
            Brightness.dark;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle(
        statusBarColor: colores.primary,
        statusBarIconBrightness:
            iconosClaros ? Brightness.light : Brightness.dark,
        statusBarBrightness: iconosClaros ? Brightness.dark : Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: colores.primary,
        body: SafeArea(
          child: TfPantalla(
            padding: const EdgeInsets.symmetric(horizontal: kMargenPantalla),
            child: Column(
              children: [
                Expanded(
                  child: Center(
                    child: SingleChildScrollView(
                      child: TweenAnimationBuilder<double>(
                        tween: Tween(begin: 0.9, end: 1),
                        duration: const Duration(milliseconds: 200),
                        curve: Curves.easeOut,
                        builder: (context, escala, hijo) =>
                            Transform.scale(scale: escala, child: hijo),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 176,
                              height: 176,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: colores.onPrimary.withValues(
                                  alpha: 0.2,
                                ),
                              ),
                              child: Container(
                                width: 128,
                                height: 128,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: colores.onPrimary,
                                ),
                                child: Icon(
                                  Icons.check_rounded,
                                  size: 80,
                                  color: colores.primary,
                                ),
                              ),
                            ),
                            const SizedBox(height: TfSpace.s8),
                            Text(
                              '¡Te pagaron!',
                              style: tema.textTheme.displayMedium?.copyWith(
                                color: colores.onPrimary,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: TfSpace.s2),
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              child: Text(
                                formatearMonto(venta.monto),
                                style: tema.textTheme.displayLarge?.copyWith(
                                  color: colores.onPrimary,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            const SizedBox(height: TfSpace.s3),
                            if (venta.horaPagado.isNotEmpty)
                              Text(
                                venta.horaPagado,
                                style: textoSobre,
                                textAlign: TextAlign.center,
                              ),
                            Text(
                              detalle,
                              style: textoSobre,
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: FilledButton(
                    onPressed: () => context.go(kRutaNuevaVenta),
                    style: FilledButton.styleFrom(
                      backgroundColor: colores.onPrimary,
                      foregroundColor: colores.primary,
                      minimumSize: const Size(double.infinity, 56),
                    ),
                    child: const Text('Nuevo cobro'),
                  ),
                ),
                const SizedBox(height: TfSpace.s2),
                SizedBox(
                  height: TfSize.touchMin,
                  child: TextButton(
                    onPressed: () => context.go(kRutaInicio),
                    style: TextButton.styleFrom(
                      foregroundColor: colores.onPrimary,
                    ),
                    child: const Text('Listo'),
                  ),
                ),
                const SizedBox(height: TfSpace.s4),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
