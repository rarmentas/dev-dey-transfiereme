import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Dispara reevaluación de `redirect` en GoRouter al cambiar la sesión.
class SesionRouterRefresh extends ChangeNotifier {
  void notify() {
    notifyListeners();
  }
}

final sesionRouterRefreshProvider = Provider<SesionRouterRefresh>((ref) {
  return SesionRouterRefresh();
});
