# ThemeData de Flutter

Material 3, esquemas claro y oscuro, listo para pegar en `lib/theme/transfiereme_theme.dart` (Flutter 3.27 o superior por `CardThemeData` y `Color.withValues`). Mapeo: `secondary` = Amarillo Cobro, `tertiary` = Pagado, `error` = Vencido. Los colores de estado y el acento también viven en la extensión `TfColors`. El archivo completo está además en Archivos › `flutter/transfiereme_theme.dart`.

```dart
// transfiereme_theme.dart — Transfiéreme · Material 3 (Flutter 3.27 o superior)
//
// pubspec.yaml (fuentes locales, recomendado para web y Android):
//   flutter:
//     fonts:
//       - family: PlusJakartaSans
//         fonts:
//           - asset: assets/fonts/PlusJakartaSans-SemiBold.ttf
//             weight: 600
//           - asset: assets/fonts/PlusJakartaSans-Bold.ttf
//             weight: 700
//           - asset: assets/fonts/PlusJakartaSans-ExtraBold.ttf
//             weight: 800
//       - family: Inter
//         fonts:
//           - asset: assets/fonts/Inter-Regular.ttf
//           - asset: assets/fonts/Inter-Medium.ttf
//             weight: 500
//           - asset: assets/fonts/Inter-SemiBold.ttf
//             weight: 600
//
// Uso:
//   MaterialApp(
//     theme: TfTheme.light,
//     darkTheme: TfTheme.dark,
//     themeMode: ThemeMode.system,
//   );
//   final tf = Theme.of(context).extension<TfColors>()!;   // pagado / pendiente / vencido
//   FilledButton(style: TfTheme.cobrar(context), onPressed: ..., child: const Text('Cobrar'));

import 'package:flutter/material.dart';

const String kDisplayFont = 'PlusJakartaSans';
const String kUiFont = 'Inter';

/// Cifras tabulares para montos en listas y tarjetas.
const List<FontFeature> kTabular = [FontFeature.tabularFigures()];

/// Colores de estado y acento que Material 3 no trae como rol propio.
@immutable
class TfColors extends ThemeExtension<TfColors> {
  const TfColors({required this.accent, required this.onAccent, required this.paid, required this.paidText, required this.paidContainer, required this.pending, required this.pendingText, required this.pendingContainer, required this.expired, required this.expiredText, required this.expiredContainer});

  final Color accent;
  final Color onAccent;
  final Color paid;
  final Color paidText;
  final Color paidContainer;
  final Color pending;
  final Color pendingText;
  final Color pendingContainer;
  final Color expired;
  final Color expiredText;
  final Color expiredContainer;

  static const light = TfColors(
    accent: Color(0xFFFFC233),
    onAccent: Color(0xFF111A2B),
    paid: Color(0xFF1F9D55),
    paidText: Color(0xFF157A45),
    paidContainer: Color(0xFFE2F3E9),
    pending: Color(0xFFF2811D),
    pendingText: Color(0xFFA04A00),
    pendingContainer: Color(0xFFFFEBD6),
    expired: Color(0xFFC2412D),
    expiredText: Color(0xFFA8361F),
    expiredContainer: Color(0xFFFBE6E1),
  );

  static const dark = TfColors(
    accent: Color(0xFFFFD15C),
    onAccent: Color(0xFF0B1120),
    paid: Color(0xFF3DD68C),
    paidText: Color(0xFF3DD68C),
    paidContainer: Color(0xFF16352A),
    pending: Color(0xFFFF9F4A),
    pendingText: Color(0xFFFF9F4A),
    pendingContainer: Color(0xFF3A2414),
    expired: Color(0xFFE8735F),
    expiredText: Color(0xFFE8735F),
    expiredContainer: Color(0xFF3D221D),
  );

  @override
  TfColors copyWith({Color? accent, Color? onAccent, Color? paid, Color? paidText, Color? paidContainer, Color? pending, Color? pendingText, Color? pendingContainer, Color? expired, Color? expiredText, Color? expiredContainer}) =>
      TfColors(accent: accent ?? this.accent, onAccent: onAccent ?? this.onAccent, paid: paid ?? this.paid, paidText: paidText ?? this.paidText, paidContainer: paidContainer ?? this.paidContainer, pending: pending ?? this.pending, pendingText: pendingText ?? this.pendingText, pendingContainer: pendingContainer ?? this.pendingContainer, expired: expired ?? this.expired, expiredText: expiredText ?? this.expiredText, expiredContainer: expiredContainer ?? this.expiredContainer);

  @override
  TfColors lerp(ThemeExtension<TfColors>? other, double t) {
    if (other is! TfColors) return this;
    return TfColors(
      accent: Color.lerp(accent, other.accent, t)!,
      onAccent: Color.lerp(onAccent, other.onAccent, t)!,
      paid: Color.lerp(paid, other.paid, t)!,
      paidText: Color.lerp(paidText, other.paidText, t)!,
      paidContainer: Color.lerp(paidContainer, other.paidContainer, t)!,
      pending: Color.lerp(pending, other.pending, t)!,
      pendingText: Color.lerp(pendingText, other.pendingText, t)!,
      pendingContainer: Color.lerp(pendingContainer, other.pendingContainer, t)!,
      expired: Color.lerp(expired, other.expired, t)!,
      expiredText: Color.lerp(expiredText, other.expiredText, t)!,
      expiredContainer: Color.lerp(expiredContainer, other.expiredContainer, t)!,
    );
  }
}

const ColorScheme tfLightScheme = ColorScheme(
  brightness: Brightness.light,
  primary: Color(0xFF1E4FA3),
  onPrimary: Color(0xFFFFFFFF),
  primaryContainer: Color(0xFFDCE7FB),
  onPrimaryContainer: Color(0xFF0F3270),
  // Secundario = Amarillo Cobro (botón Cobrar, QR impreso)
  secondary: Color(0xFFFFC233),
  onSecondary: Color(0xFF111A2B),
  secondaryContainer: Color(0xFFFFEBD6),
  onSecondaryContainer: Color(0xFFA04A00),
  // Terciario = Pagado
  tertiary: Color(0xFF157A45),
  onTertiary: Color(0xFFFFFFFF),
  tertiaryContainer: Color(0xFFE2F3E9),
  onTertiaryContainer: Color(0xFF157A45),
  error: Color(0xFFC2412D),
  onError: Color(0xFFFFFFFF),
  errorContainer: Color(0xFFFBE6E1),
  onErrorContainer: Color(0xFFA8361F),
  surface: Color(0xFFF4F6FA),
  onSurface: Color(0xFF111A2B),
  onSurfaceVariant: Color(0xFF4F5D76),
  surfaceContainerLowest: Color(0xFFFFFFFF),
  surfaceContainerLow: Color(0xFFFFFFFF),
  surfaceContainer: Color(0xFFFFFFFF),
  surfaceContainerHigh: Color(0xFFE8EDF5),
  surfaceContainerHighest: Color(0xFFE8EDF5),
  outline: Color(0xFF74819A),
  outlineVariant: Color(0xFFDCE3EE),
  inverseSurface: Color(0xFF111A2B),
  onInverseSurface: Color(0xFFF4F6FA),
  inversePrimary: Color(0xFF7FAEF5),
  shadow: Color(0xFF000000),
  scrim: Color(0xFF000000),
  surfaceTint: Color(0x00000000),
);

const ColorScheme tfDarkScheme = ColorScheme(
  brightness: Brightness.dark,
  primary: Color(0xFF7FAEF5),
  onPrimary: Color(0xFF0B1120),
  primaryContainer: Color(0xFF1C2D4D),
  onPrimaryContainer: Color(0xFFE8EDF6),
  // Secundario = Amarillo Cobro (botón Cobrar, QR impreso)
  secondary: Color(0xFFFFD15C),
  onSecondary: Color(0xFF0B1120),
  secondaryContainer: Color(0xFF3A2414),
  onSecondaryContainer: Color(0xFFFF9F4A),
  // Terciario = Pagado
  tertiary: Color(0xFF3DD68C),
  onTertiary: Color(0xFF0B1120),
  tertiaryContainer: Color(0xFF16352A),
  onTertiaryContainer: Color(0xFF3DD68C),
  error: Color(0xFFE8735F),
  onError: Color(0xFF0B1120),
  errorContainer: Color(0xFF3D221D),
  onErrorContainer: Color(0xFFE8735F),
  surface: Color(0xFF0B1120),
  onSurface: Color(0xFFE8EDF6),
  onSurfaceVariant: Color(0xFFA2AEC4),
  surfaceContainerLowest: Color(0xFF0A100E),
  surfaceContainerLow: Color(0xFF141C2E),
  surfaceContainer: Color(0xFF141C2E),
  surfaceContainerHigh: Color(0xFF1D2740),
  surfaceContainerHighest: Color(0xFF1D2740),
  outline: Color(0xFF65728C),
  outlineVariant: Color(0xFF26314A),
  inverseSurface: Color(0xFFE8EDF6),
  onInverseSurface: Color(0xFF0B1120),
  inversePrimary: Color(0xFF1E4FA3),
  shadow: Color(0xFF000000),
  scrim: Color(0xFF000000),
  surfaceTint: Color(0x00000000),
);

TextTheme _textTheme(ColorScheme s) {
  TextStyle d(double size, double lh, FontWeight w, [double ls = 0]) => TextStyle(
      fontFamily: kDisplayFont, fontSize: size, height: lh / size, fontWeight: w,
      letterSpacing: ls * size, color: s.onSurface);
  TextStyle u(double size, double lh, FontWeight w, [double ls = 0]) => TextStyle(
      fontFamily: kUiFont, fontSize: size, height: lh / size, fontWeight: w,
      letterSpacing: ls * size, color: s.onSurface);
  return TextTheme(
    displayLarge: d(56, 60, FontWeight.w800, -0.02).copyWith(fontFeatures: kTabular), // monto-xl
    displayMedium: d(40, 44, FontWeight.w800, -0.02), // display
    displaySmall: d(36, 40, FontWeight.w800, -0.01).copyWith(fontFeatures: kTabular), // monto-l
    headlineLarge: d(28, 34, FontWeight.w800, -0.01), // titulo-1
    headlineMedium: d(22, 28, FontWeight.w700), // titulo-2
    headlineSmall: d(18, 24, FontWeight.w700), // titulo-3
    titleLarge: d(20, 24, FontWeight.w800), // boton-cobrar
    titleMedium: u(16, 20, FontWeight.w600).copyWith(fontFeatures: kTabular), // monto-lista
    titleSmall: u(14, 20, FontWeight.w600), // etiqueta
    bodyLarge: u(17, 24, FontWeight.w400), // cuerpo-l
    bodyMedium: u(15, 22, FontWeight.w400), // cuerpo
    bodySmall: u(13, 18, FontWeight.w400).copyWith(color: s.onSurfaceVariant), // cuerpo-s
    labelLarge: u(16, 20, FontWeight.w600), // boton
    labelMedium: u(12, 16, FontWeight.w600, 0.06), // sobretitulo (en mayúsculas)
    labelSmall: u(11, 14, FontWeight.w600), // micro
  );
}

class TfTheme {
  TfTheme._();

  static const double touchMin = 48;
  static const double inputHeight = 56;
  static const double cobrarHeight = 64;
  static const double rSm = 8, rMd = 12, rLg = 16, rXl = 24;

  static ThemeData get light => _build(tfLightScheme, TfColors.light);
  static ThemeData get dark => _build(tfDarkScheme, TfColors.dark);

  /// Estilo del botón Cobrar (Amarillo Cobro). Úsalo con FilledButton.
  static ButtonStyle cobrar(BuildContext context) {
    final tf = Theme.of(context).extension<TfColors>()!;
    final t = Theme.of(context).textTheme;
    return FilledButton.styleFrom(
      backgroundColor: tf.accent,
      foregroundColor: tf.onAccent,
      minimumSize: const Size.fromHeight(cobrarHeight),
      textStyle: t.titleLarge,
      elevation: 2,
      shadowColor: tf.accent.withValues(alpha: 0.5),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(rLg)),
    );
  }

  static ThemeData _build(ColorScheme s, TfColors tf) {
    final text = _textTheme(s);
    final rMdShape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(rMd));
    OutlineInputBorder border(Color c, double w) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(rMd), borderSide: BorderSide(color: c, width: w));

    return ThemeData(
      useMaterial3: true,
      brightness: s.brightness,
      colorScheme: s,
      scaffoldBackgroundColor: s.surface,
      fontFamily: kUiFont,
      textTheme: text,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      visualDensity: VisualDensity.standard,
      extensions: [tf],
      appBarTheme: AppBarTheme(
        backgroundColor: s.surface,
        foregroundColor: s.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: text.headlineMedium,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(touchMin, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          textStyle: text.labelLarge,
          shape: rMdShape,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: s.primary,
          minimumSize: const Size(touchMin, 52),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          side: BorderSide(color: s.primary, width: 2),
          textStyle: text.labelLarge,
          shape: rMdShape,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: s.primary,
          minimumSize: const Size(touchMin, touchMin),
          textStyle: text.labelLarge,
          shape: rMdShape,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: s.surfaceContainerLowest,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        constraints: const BoxConstraints(minHeight: inputHeight),
        labelStyle: text.titleSmall,
        floatingLabelBehavior: FloatingLabelBehavior.always,
        hintStyle: text.bodyLarge?.copyWith(color: s.onSurfaceVariant),
        helperStyle: text.bodySmall,
        errorStyle: text.bodySmall?.copyWith(color: tf.expiredText, fontWeight: FontWeight.w500),
        prefixStyle: text.bodyLarge?.copyWith(color: s.onSurfaceVariant),
        border: border(s.outline, 1.5),
        enabledBorder: border(s.outline, 1.5),
        focusedBorder: border(s.primary, 2),
        errorBorder: border(tf.expired, 2),
        focusedErrorBorder: border(tf.expired, 2),
      ),
      cardTheme: CardThemeData(
        color: s.surfaceContainerLow,
        surfaceTintColor: Colors.transparent,
        elevation: s.brightness == Brightness.light ? 1 : 0,
        shadowColor: const Color(0x2914201C),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(rLg)),
      ),
      chipTheme: ChipThemeData(
        shape: const StadiumBorder(),
        side: BorderSide.none,
        labelStyle: text.titleSmall,
        backgroundColor: s.surfaceContainerHigh,
        selectedColor: s.primaryContainer,
        padding: const EdgeInsets.symmetric(horizontal: 8),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: SegmentedButton.styleFrom(
          minimumSize: const Size(touchMin, touchMin),
          selectedBackgroundColor: s.primaryContainer,
          selectedForegroundColor: s.onPrimaryContainer,
          textStyle: text.titleSmall,
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 72,
        backgroundColor: s.surfaceContainerLow,
        indicatorColor: s.primaryContainer,
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStatePropertyAll(text.labelSmall),
        iconTheme: WidgetStateProperty.resolveWith((states) => IconThemeData(
              color: states.contains(WidgetState.selected) ? s.onPrimaryContainer : s.onSurfaceVariant,
              size: 24,
            )),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: s.inverseSurface,
        contentTextStyle: text.bodyMedium?.copyWith(color: s.onInverseSurface),
        actionTextColor: s.brightness == Brightness.light ? Color(0xFFDCE7FB) : Color(0xFF1E4FA3),
        shape: rMdShape,
      ),
      dividerTheme: DividerThemeData(color: s.outlineVariant, thickness: 1, space: 1),
      progressIndicatorTheme: ProgressIndicatorThemeData(color: tf.pending, linearTrackColor: s.surfaceContainerHigh),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: s.surfaceContainerLow,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(rXl))),
      ),
    );
  }
}
```
