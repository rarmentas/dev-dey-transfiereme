import '../data/cuenta_estado.dart';
import '../../cobro/presentation/qr_general_impreso_page.dart';

/// Título principal del bloqueo de cobro según el paso del comercio.
String tituloBloqueoCuenta(EstadoCuentaPey? estado) {
  if (estado == null || estado.puedeCobrar) {
    return kMensajeCuentaNoActivaQr;
  }
  return switch (estado.paso) {
    1 => 'Guarda tu CLABE para poder cobrar',
    2 => 'Registra tu cuenta en pey',
    3 => kMensajeCuentaNoActivaQr,
    _ => kMensajeCuentaNoActivaQr,
  };
}

/// Texto secundario con el paso concreto (1–3).
String mensajeSiguientePaso(EstadoCuentaPey? estado) {
  if (estado == null) {
    return kMensajeQrAlActivar;
  }
  if (estado.puedeCobrar) {
    return 'Tu cuenta ya puede cobrar con CoDi.';
  }
  return switch (estado.paso) {
    1 =>
      'Paso 1 de 3: en Ajustes, toca «Registrar CLABE» y guarda los 18 dígitos de tu cuenta.',
    2 =>
      'Paso 2 de 3: registra el titular y la entidad (persona o negocio) en pey.',
    3 =>
      'Paso 3 de 3: espera que pey active tu cuenta. Usa «Revisar estado» para actualizar.',
    _ => kMensajeQrAlActivar,
  };
}

String etiquetaFase(EstadoCuentaPey estado) {
  return switch (estado.fase) {
    'sin_clabe' => 'Sin CLABE',
    'pendiente_registro' => 'Pendiente de registro en pey',
    'pendiente_activacion' => 'Pendiente de activación',
    'activa' => 'Cuenta activa',
    _ => estado.fase,
  };
}

String detalleCuentaPey(EstadoCuentaPey estado) {
  final partes = <String>[];
  if (estado.clabeEnmascarada.isNotEmpty) {
    partes.add('CLABE ${estado.clabeEnmascarada}');
  }
  if (estado.tieneCuentaPey && estado.peyBankAccountIdSufijo.isNotEmpty) {
    partes.add('Cuenta pey …${estado.peyBankAccountIdSufijo}');
  }
  if (partes.isEmpty) {
    return etiquetaFase(estado);
  }
  return '${etiquetaFase(estado)} · ${partes.join(' · ')}';
}
