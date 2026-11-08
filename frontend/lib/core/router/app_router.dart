import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/movimientos/presentation/resumen_movimientos_page.dart';
import '../../features/sesion/presentation/home_autenticado_page.dart';
import '../../features/sesion/presentation/login_page.dart';
import '../../features/sesion/presentation/olvido_contrasena_page.dart';
import '../../features/sesion/presentation/olvido_restablecer_page.dart';
import '../../features/sesion/presentation/registro_confirmar_page.dart';
import '../../features/sesion/presentation/registro_page.dart';
import '../sesion/sesion_notifier.dart';
import 'sesion_router_refresh.dart';

const kRutaEntrar = '/entrar';
const kRutaInicio = '/inicio';
const kRutaRegistro = '/registro';
const kRutaRegistroConfirmar = '/registro/confirmar';
const kRutaOlvido = '/olvido-contrasena';
const kRutaOlvidoRestablecer = '/olvido-contrasena/restablecer';
const kRutaMovimientos = '/movimientos';

const _rutasPublicasSinSesion = <String>{
  kRutaEntrar,
  kRutaRegistro,
  kRutaRegistroConfirmar,
  kRutaOlvido,
  kRutaOlvidoRestablecer,
};

bool _rutaPublicaSinSesion(String ubicacion) {
  return _rutasPublicasSinSesion.contains(ubicacion);
}

String _correoDesdeExtra(Object? extra) {
  if (extra is String && extra.trim().isNotEmpty) {
    return extra.trim();
  }
  return '';
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
        path: kRutaRegistro,
        builder: (context, state) => const RegistroPage(),
      ),
      GoRoute(
        path: kRutaRegistroConfirmar,
        builder: (context, state) {
          final correo = _correoDesdeExtra(state.extra);
          if (correo.isEmpty) {
            return const RegistroPage();
          }
          return RegistroConfirmarPage(correo: correo);
        },
      ),
      GoRoute(
        path: kRutaOlvido,
        builder: (context, state) => const OlvidoContrasenaPage(),
      ),
      GoRoute(
        path: kRutaOlvidoRestablecer,
        builder: (context, state) {
          final correo = _correoDesdeExtra(state.extra);
          if (correo.isEmpty) {
            return const OlvidoContrasenaPage();
          }
          return OlvidoRestablecerPage(correo: correo);
        },
      ),
      GoRoute(
        path: kRutaMovimientos,
        builder: (context, state) => const ResumenMovimientosPage(),
      ),
    ],
  );
});
