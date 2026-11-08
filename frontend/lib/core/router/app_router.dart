import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/movimientos/presentation/resumen_movimientos_page.dart';
import '../../features/sesion/presentation/home_autenticado_page.dart';
import '../../features/sesion/presentation/login_page.dart';
import '../../features/tablero/presentation/tablero_page.dart';
import '../sesion/sesion_notifier.dart';
import 'sesion_router_refresh.dart';

const kRutaEntrar = '/entrar';
const kRutaInicio = '/inicio';
const kRutaMovimientos = '/movimientos';
const kRutaTablero = '/tablero';

const _rutasPublicasSinSesion = <String>{
  kRutaEntrar,
};

bool _rutaPublicaSinSesion(String ubicacion) {
  return _rutasPublicasSinSesion.contains(ubicacion);
}

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
      if (!sesion.autenticado && !_rutaPublicaSinSesion(ubicacion)) {
        return kRutaEntrar;
      }
      if (sesion.autenticado && (enEntrar || _rutaPublicaSinSesion(ubicacion))) {
        return kRutaInicio;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: kRutaEntrar,
        builder: (context, state) {
          final aviso = state.uri.queryParameters['aviso'];
          return LoginPage(
            key: ValueKey(aviso ?? ''),
            mensajeInicial: aviso,
          );
        },
      ),
      GoRoute(
        path: kRutaInicio,
        builder: (context, state) => const HomeAutenticadoPage(),
      ),
      GoRoute(
        path: kRutaMovimientos,
        builder: (context, state) => const ResumenMovimientosPage(),
      ),
      GoRoute(
        path: kRutaTablero,
        builder: (context, state) => const TableroPage(),
      ),
    ],
  );
});
