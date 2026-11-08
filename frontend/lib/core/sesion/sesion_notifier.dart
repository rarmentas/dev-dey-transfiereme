import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/providers.dart';
import '../router/sesion_router_refresh.dart';
import 'sesion_providers.dart';
import 'sesion_repository.dart';
import 'sesion_view_state.dart';

final sesionNotifierProvider =
    NotifierProvider<SesionNotifier, SesionViewState>(SesionNotifier.new);

String mensajeErrorSesionCliente(Object error) {
  if (error is SesionApiException) {
    return error.mensaje;
  }
  if (error is DioException) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'La solicitud tardó demasiado. Verifique su conexión e intente de nuevo.';
      case DioExceptionType.connectionError:
        return 'No pudimos conectar con el servidor. Verifique su conexión e intente de nuevo.';
      case DioExceptionType.badResponse:
        final codigo = error.response?.statusCode;
        if (codigo != null && codigo >= 500) {
          return 'El servidor no está disponible en este momento. Intente de nuevo más tarde.';
        }
        break;
      default:
        break;
    }
  }
  return 'No pudimos completar la solicitud. Intente de nuevo.';
}

class SesionNotifier extends Notifier<SesionViewState> {
  @override
  SesionViewState build() {
    final factory = ref.read(dioFactoryProvider);
    factory.onSesionPerdida = marcarCerrada;
    Future.microtask(refrescarAlArranque);
    return SesionViewState.inicial();
  }

  SesionRepository get _repo => ref.read(sesionRepositoryProvider);

  void _notificarRouter() {
    if (!ref.mounted) {
      return;
    }
    ref.read(sesionRouterRefreshProvider).notify();
  }

  Future<void> refrescarAlArranque() async {
    await cargarEstado();
  }

  Future<void> cargarEstado() async {
    if (!ref.mounted) {
      return;
    }
    state = state.copyWith(cargando: true, limpiarError: true);
    _notificarRouter();
    try {
      final datos = await _repo.cargarEstado();
      if (!ref.mounted) {
        return;
      }
      state = SesionViewState(
        resuelto: true,
        cargando: false,
        estado: datos,
      );
    } on SesionApiException catch (e) {
      if (!ref.mounted) {
        return;
      }
      state = SesionViewState(
        resuelto: true,
        cargando: false,
        errorMensaje: e.mensaje,
      );
    } catch (e) {
      if (!ref.mounted) {
        return;
      }
      state = SesionViewState(
        resuelto: true,
        cargando: false,
        errorMensaje: mensajeErrorSesionCliente(e),
      );
    } finally {
      _notificarRouter();
    }
  }

  Future<bool> entrar({
    required String correo,
    required String contrasena,
  }) async {
    if (!ref.mounted) {
      return false;
    }
    state = state.copyWith(cargando: true, limpiarError: true);
    _notificarRouter();
    try {
      await _repo.entrar(correo: correo, contrasena: contrasena);
      if (!ref.mounted) {
        return false;
      }
      final datos = await _repo.cargarEstado();
      if (!ref.mounted) {
        return false;
      }
      if (datos == null) {
        state = state.copyWith(
          resuelto: true,
          cargando: false,
          limpiarEstado: true,
          errorMensaje: 'No pudimos confirmar su sesión.',
        );
        _notificarRouter();
        return false;
      }
      state = SesionViewState(
        resuelto: true,
        cargando: false,
        estado: datos,
      );
      _notificarRouter();
      return true;
    } on SesionApiException catch (e) {
      if (!ref.mounted) {
        return false;
      }
      state = state.copyWith(
        resuelto: true,
        cargando: false,
        limpiarEstado: true,
        errorMensaje: e.mensaje,
      );
      _notificarRouter();
      return false;
    } catch (e) {
      if (!ref.mounted) {
        return false;
      }
      state = state.copyWith(
        resuelto: true,
        cargando: false,
        limpiarEstado: true,
        errorMensaje: mensajeErrorSesionCliente(e),
      );
      _notificarRouter();
      return false;
    }
  }

  Future<void> salir() async {
    if (!ref.mounted) {
      return;
    }
    state = state.copyWith(cargando: true, limpiarError: true);
    _notificarRouter();
    try {
      await _repo.salir();
    } on SesionApiException {
      // Cierra la sesión local aunque el API falle.
    } catch (_) {
      // Igual cierra en red o servidor.
    } finally {
      if (ref.mounted) {
        marcarCerrada();
      }
    }
  }

  void marcarCerrada() {
    if (!ref.mounted) {
      return;
    }
    state = const SesionViewState(
      resuelto: true,
      cargando: false,
    );
    _notificarRouter();
  }
}
