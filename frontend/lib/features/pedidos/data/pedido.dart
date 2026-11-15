import '../../movimientos/data/movimiento.dart';

String formatearCentavos(int centavos) => formatearMonto(
  '${centavos ~/ 100}.${(centavos % 100).toString().padLeft(2, '0')}',
);

class PedidoResumen {
  PedidoResumen.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      numero = json['numero'] as int,
      estado = json['estado'] as String,
      cliente = json['cliente_etiqueta'] as String? ?? '',
      pendientes = json['renglones_pendientes'] as int,
      total = json['total_comercial_centavos'] as int?;
  final String id;
  final int numero;
  final String estado;
  final String cliente;
  final int pendientes;
  final int? total;
}

class Pedido {
  Pedido.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      numero = json['numero'] as int,
      version = json['version'] as int,
      estado = json['estado'] as String,
      cliente = json['cliente_etiqueta'] as String? ?? '',
      renglones = (json['renglones'] as List)
          .map((e) => Renglon.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      cotizacion = json['cotizacion'] == null
          ? null
          : Cotizacion.fromJson(
              Map<String, dynamic>.from(json['cotizacion'] as Map),
            ),
      aceptado = json['aceptacion'] != null;
  final String id;
  final int numero;
  final int version;
  final String estado;
  final String cliente;
  final List<Renglon> renglones;
  final Cotizacion? cotizacion;
  final bool aceptado;
}

class Cotizacion {
  Cotizacion.fromJson(Map<String, dynamic> json)
    : revision = json['revision'] as int,
      total = json['total_comercial_centavos'] as int,
      efectivo = json['importe_efectivo_centavos'] as int,
      demo = json['demo_mode'] as bool,
      token = json['token_resumen'] as String;
  final int revision;
  final int total;
  final int efectivo;
  final bool demo;
  final String token;
}

class Renglon {
  Renglon.fromJson(Map<String, dynamic> json)
    : id = json['renglon_id'] as String,
      solicitado = json['texto_solicitado'] as String,
      descripcion = json['descripcion'] as String? ?? '',
      cantidad = json['cantidad'] as String? ?? '',
      unidad = json['unidad'] as String? ?? '',
      precio = json['precio_unitario_centavos'] as int?,
      resolucion = json['resolucion'] as String,
      motivo = json['motivo_exclusion'] as String? ?? '',
      subtotal = json['subtotal_centavos'] as int?;
  final String id;
  final String solicitado;
  String descripcion;
  String cantidad;
  String unidad;
  int? precio;
  String resolucion;
  String motivo;
  final int? subtotal;

  Map<String, dynamic> toJson() => {
    'renglon_id': id,
    'descripcion': descripcion,
    'cantidad': cantidad.isEmpty ? null : cantidad,
    'unidad': unidad,
    'precio_unitario_centavos': precio,
    'resolucion': resolucion,
    'motivo_exclusion': motivo,
  };
}
