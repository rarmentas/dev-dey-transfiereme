import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/movimientos/presentation/resumen_movimientos_page.dart';
import '../../features/sesion/presentation/home_autenticado_page.dart';
import '../../features/sesion/presentation/login_page.dart';
import '../sesion/sesion_notifier.dart';
import 'sesion_router_refresh.dart';

const kRutaEntrar = '/entrar';
const kRutaInicio = '/inicio';
const kRutaMovimientos = '/movimientos';

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ref.watch(sesionRouterRefreshProvider);

  return GoRouter(
    initialLocation: kRutaEntrar,
    refreshListenable: refresh,
    redirect: (BuildContext context, GoRouterState state) {
      final sesion = ref.read(sesionNotifierProvider);
      if (!sesion.resuelto) {
        return null;
      }
      final ubicacion = state.matchedLocation;
      final enEntrar = ubicacion == kRutaEntrar;
      if (!sesion.autenticado && !enEntrar) {
        return kRutaEntrar;
      }
      if (sesion.autenticado && enEntrar) {
        return kRutaInicio;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: kRutaEntrar,
        builder: (context, state) => const LoginPage(),
      ),
      GoRoute(
        path: kRutaInicio,
        builder: (context, state) => const HomeAutenticadoPage(),
      ),
      GoRoute(
        path: kRutaMovimientos,
        builder: (context, state) => const ResumenMovimientosPage(),
      ),
    ],
  );
});
