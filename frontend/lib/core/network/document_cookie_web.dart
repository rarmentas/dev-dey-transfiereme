import 'package:web/web.dart' as web;

String? leerCsrfDesdeDocumento() {
  final raw = web.document.cookie;
  if (raw.isEmpty) {
    return null;
  }
  for (final parte in raw.split(';')) {
    final par = parte.trim().split('=');
    if (par.length >= 2 && par.first == 'csrftoken') {
      return par.sublist(1).join('=');
    }
  }
  return null;
}
