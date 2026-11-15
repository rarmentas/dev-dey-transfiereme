import 'package:dio/dio.dart';

class AsistenteVivoException implements Exception {
  AsistenteVivoException(this.mensaje);
  final String mensaje;
  @override
  String toString() => mensaje;
}

class TokenAsistenteVivo {
  const TokenAsistenteVivo({required this.token, required this.modelo});
  final String token;
  final String modelo;
}

class AsistenteVivoRepository {
  AsistenteVivoRepository(this._dio);
  final Dio _dio;

  Future<TokenAsistenteVivo> pedirToken() async {
    try {
      final response = await _dio.post<dynamic>('/api/asistente-vivo/token/');
      final data = Map<String, dynamic>.from(response.data as Map);
      return TokenAsistenteVivo(
        token: data['token'] as String,
        modelo: data['modelo'] as String,
      );
    } on DioException catch (error) {
      final data = error.response?.data;
      final mapa = data is Map
          ? Map<String, dynamic>.from(data)
          : const <String, dynamic>{};
      if (error.response?.statusCode == 503) {
        throw AsistenteVivoException(
          'Asistente no disponible. Intenta más tarde.',
        );
      }
      throw AsistenteVivoException(
        mapa['mensaje'] as String? ?? 'No pudimos iniciar el asistente.',
      );
    }
  }
}
