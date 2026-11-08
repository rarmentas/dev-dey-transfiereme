class ComercioResumen {
  const ComercioResumen({required this.id, required this.nombre});

  final int id;
  final String nombre;

  factory ComercioResumen.fromJson(Map<String, dynamic> json) {
    return ComercioResumen(
      id: json['id'] as int,
      nombre: json['nombre'] as String? ?? '',
    );
  }
}

class EstadoSesion {
  const EstadoSesion({
    required this.usuario,
    required this.correo,
    required this.nombre,
    required this.apellidos,
    required this.comercio,
  });

  final String usuario;
  final String correo;
  final String nombre;
  final String apellidos;
  final ComercioResumen? comercio;

  factory EstadoSesion.fromJson(Map<String, dynamic> json) {
    ComercioResumen? comercio;
    final rawComercio = json['comercio'];
    if (rawComercio is Map<String, dynamic>) {
      comercio = ComercioResumen.fromJson(rawComercio);
    }
    return EstadoSesion(
      usuario: json['usuario'] as String? ?? '',
      correo: json['correo'] as String? ?? '',
      nombre: json['nombre'] as String? ?? '',
      apellidos: json['apellidos'] as String? ?? '',
      comercio: comercio,
    );
  }

  /// Texto para el saludo según decisión del plan.
  String get nombreParaSaludo {
    if (nombre.trim().isNotEmpty) {
      return nombre.trim();
    }
    if (correo.trim().isNotEmpty) {
      return correo.trim();
    }
    return usuario;
  }
}
