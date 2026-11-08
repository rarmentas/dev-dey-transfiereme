import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/fecha/dia_cdmx.dart';
import '../../../core/network/providers.dart';
import '../data/tablero.dart';
import '../data/tablero_repository.dart';

final tableroRepositoryProvider = Provider<TableroRepository>((ref) {
  return TableroRepository(ref.watch(dioProvider));
});

/// Sin reintentos automáticos: la pantalla ofrece «Reintentar».
final tableroProvider = FutureProvider.autoDispose<Tablero>(
  (ref) => ref.watch(tableroRepositoryProvider).obtener(),
  retry: (_, _) => null,
);

/// Reloj del tablero (hora de CDMX «naive»); las pruebas lo sustituyen.
final tableroAhoraProvider = Provider<DateTime>((ref) => ahoraCdmx());

/// Rango de días civiles, ambos extremos inclusivos.
typedef RangoTablero = ({DateTime desde, DateTime hasta});

/// Tablero de un rango concreto. Sin reintentos automáticos.
final tableroRangoProvider = FutureProvider.autoDispose
    .family<Tablero, RangoTablero>(
      (ref, rango) => ref
          .watch(tableroRepositoryProvider)
          .obtener(desde: rango.desde, hasta: rango.hasta),
      retry: (_, _) => null,
    );

enum PeriodoTablero {
  hoy('Hoy', 'ayer'),
  semana('Esta semana', 'semana pasada'),
  mes('Este mes', 'mes pasado');

  const PeriodoTablero(this.etiqueta, this.anterior);

  final String etiqueta;

  /// Texto de la comparación: «vs. semana pasada».
  final String anterior;

  RangoTablero rango(DateTime ahora) {
    final hoy = DateTime(ahora.year, ahora.month, ahora.day);
    return switch (this) {
      PeriodoTablero.hoy => (desde: hoy, hasta: hoy),
      PeriodoTablero.semana => (
        desde: lunesDe(hoy),
        hasta: hoy,
      ),
      PeriodoTablero.mes => (desde: DateTime(hoy.year, hoy.month), hasta: hoy),
    };
  }

  /// Periodo previo de igual duración.
  RangoTablero rangoAnterior(DateTime ahora) {
    final actual = rango(ahora);
    switch (this) {
      case PeriodoTablero.hoy:
        final ayer = DateTime(actual.desde.year, actual.desde.month, actual.desde.day - 1);
        return (desde: ayer, hasta: ayer);
      case PeriodoTablero.semana:
        return (
          desde: DateTime(actual.desde.year, actual.desde.month, actual.desde.day - 7),
          hasta: DateTime(actual.hasta.year, actual.hasta.month, actual.hasta.day - 7),
        );
      case PeriodoTablero.mes:
        final inicio = DateTime(actual.desde.year, actual.desde.month - 1);
        final ultimo = DateTime(inicio.year, inicio.month + 1, 0).day;
        final dia = actual.hasta.day < ultimo ? actual.hasta.day : ultimo;
        return (desde: inicio, hasta: DateTime(inicio.year, inicio.month, dia));
    }
  }
}
