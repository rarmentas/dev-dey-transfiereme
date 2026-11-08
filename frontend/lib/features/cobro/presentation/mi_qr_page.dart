import 'package:flutter/material.dart';

/// Contenedor de «Mi QR». (Provisional: lo completa el lote de inicio.)
class MiQrPage extends StatelessWidget {
  const MiQrPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mi QR')),
      body: const SizedBox.shrink(),
    );
  }
}
