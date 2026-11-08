import 'sesion_models.dart';

class SesionViewState {
  const SesionViewState({
    required this.resuelto,
    required this.cargando,
    this.estado,
    this.errorMensaje,
  });

  final bool resuelto;
  final bool cargando;
  final EstadoSesion? estado;
  final String? errorMensaje;

  bool get autenticado => estado != null;

  factory SesionViewState.inicial() {
    return const SesionViewState(resuelto: false, cargando: true);
  }

  SesionViewState copyWith({
    bool? resuelto,
    bool? cargando,
    EstadoSesion? estado,
    bool limpiarEstado = false,
    String? errorMensaje,
    bool limpiarError = false,
  }) {
    return SesionViewState(
      resuelto: resuelto ?? this.resuelto,
      cargando: cargando ?? this.cargando,
      estado: limpiarEstado ? null : (estado ?? this.estado),
      errorMensaje:
          limpiarError ? null : (errorMensaje ?? this.errorMensaje),
    );
  }
}
