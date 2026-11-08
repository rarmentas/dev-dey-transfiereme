import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/widgets.dart';

/// Margen horizontal estándar de pantalla en teléfonos (18 px).
const double kMargenPantalla = 18.0;

/// Ancho máximo de contenido centrado en tablet y escritorio (480 px).
const double kMaxAnchoContenido = 480.0;

/// Escala de espaciado Transfiéreme (base 4/8).
abstract final class TfSpace {
  /// 4 px
  static const double s1 = 4.0;

  /// 8 px
  static const double s2 = 8.0;

  /// 12 px
  static const double s3 = 12.0;

  /// 16 px
  static const double s4 = 16.0;

  /// 20 px
  static const double s5 = 20.0;

  /// 24 px
  static const double s6 = 24.0;

  /// 32 px
  static const double s8 = 32.0;

  /// 40 px
  static const double s10 = 40.0;

  /// 48 px
  static const double s12 = 48.0;

  /// 64 px
  static const double s16 = 64.0;
}

/// Radios de esquina del sistema de diseño Transfiéreme.
abstract final class TfRadius {
  /// 8 px (reusa [TfTheme.rSm]).
  static const double sm = TfTheme.rSm;

  /// 12 px (reusa [TfTheme.rMd]).
  static const double md = TfTheme.rMd;

  /// 16 px (reusa [TfTheme.rLg]).
  static const double lg = TfTheme.rLg;

  /// 24 px (reusa [TfTheme.rXl]).
  static const double xl = TfTheme.rXl;

  /// 999 px (píldoras completas).
  static const double full = 999.0;

  /// [Radius] circular de 8 px.
  static const Radius rSm = Radius.circular(sm);

  /// [Radius] circular de 12 px.
  static const Radius rMd = Radius.circular(md);

  /// [Radius] circular de 16 px.
  static const Radius rLg = Radius.circular(lg);

  /// [Radius] circular de 24 px.
  static const Radius rXl = Radius.circular(xl);

  /// [Radius] circular completo (píldora).
  static const Radius rFull = Radius.circular(full);

  /// [BorderRadius] de 8 px.
  static const BorderRadius brSm = BorderRadius.all(rSm);

  /// [BorderRadius] de 12 px.
  static const BorderRadius brMd = BorderRadius.all(rMd);

  /// [BorderRadius] de 16 px.
  static const BorderRadius brLg = BorderRadius.all(rLg);

  /// [BorderRadius] de 24 px.
  static const BorderRadius brXl = BorderRadius.all(rXl);

  /// [BorderRadius] completo (píldora).
  static const BorderRadius brFull = BorderRadius.all(rFull);
}

/// Tamaños clave de componentes Transfiéreme.
abstract final class TfSize {
  /// Altura / ancho mínimo de cualquier objetivo táctil (48 px).
  static const double touchMin = 48.0;

  /// Altura estándar de campos de entrada (56 px).
  static const double inputH = 56.0;

  /// Altura del botón principal Cobrar (64 px).
  static const double buttonXl = 64.0;

  /// Tamaño estándar de íconos de acción (24 px).
  static const double icon = 24.0;

  /// Lado mínimo del código QR en pantalla (232 px).
  static const double qrScreen = 232.0;
}
