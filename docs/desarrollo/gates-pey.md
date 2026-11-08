# Gates pey antes del cobro real

Listas para hacerlas a mano en el despliegue. No sustituyen los tests. Ningún paso de esta lista se da por hecho con el adaptador de desarrollo.

Cada sección guarda evidencia (captura o texto) y cierra con firma.

## 1.7 Acceso real y aislamiento

1. En el despliegue, entra como vendedor del comercio A y como vendedor del comercio B (sesiones distintas).
2. Con A, `GET /api/movimientos/` solo lista movimientos de A.
3. Con A, `GET /api/ventas/<id>/` de un movimiento de B responde `404` con `{"detail": "No encontrado."}`.
4. Sin cookie de sesión, `GET /api/movimientos/` y `GET /api/ventas/<id>/` responden `403` con `{"detail": "Debe iniciar sesión."}`.
5. Repite el paso 3 al revés: B no ve el id de A.

Evidencia: las cuatro respuestas (lista de A, 404 cruzado, 403 sin sesión, lista de B) con fecha y host.

- [ ] Firma: ______________ Fecha: __________

## 1.8 Cuenta ACTIVE real

1. `PEY_API_KEY` vive solo en el archivo de entorno del servidor (variable File de GitLab). No está en Flutter, en el repo ni en el historial del chat.
2. En el servidor, con `DEBUG=False` y `PEY_ADAPTADOR=produccion`, registra la CLABE del comercio: `manage.py registrar_cuenta_pey … --confirmar` (historia 5.4). Contrato del comando y de los endpoints de app: [cuenta-pey-api.md](cuenta-pey-api.md).
3. `manage.py diagnostico_pey --correo …` muestra `codiStatus` `ACTIVE` y un `bankAccountId` (ULID).
4. Con la CLABE de pruebas `012180015826225713` la cuenta queda `ACTIVE` al momento. Una CLABE propia puede tardar días hábiles: no cobres hasta ver `ACTIVE`.

Evidencia: salida del diagnóstico (sin la API key) y confirmación de que el secreto no está en el cliente.

- [ ] Firma: ______________ Fecha: __________

## 1.9 Avisos firmados en URL pública

1. En [portal.mipey.mx/developers](https://portal.mipey.mx/developers), el webhook de la API key apunta a `WEBHOOK_BASE_URL` + `/api/webhooks/pey/`.
2. `PEY_WEBHOOK_SECRET` (`whsec_…`) está solo en el servidor. Si está vacío, la ruta responde `401`.
3. Un aviso de un cobro de prueba aparece como entrega exitosa en «Webhook Logs».
4. Reenviar ese mismo evento responde `duplicado` y deja un solo movimiento `pagado` (mismo `webhook-id`).

Evidencia: URL registrada, captura del log de entrega exitosa y de la respuesta `duplicado`.

- [ ] Firma: ______________ Fecha: __________

## Cobros de $0.01

Solo después de 1.7, 1.8 y 1.9, y solo con el adaptador de producción. El dinero no se devuelve. Cada cobro de producción lleva el `bankAccountId` del comercio; sin él, pey abonaría a la cuenta de la API key de la plataforma.

### 2.5 QR general

1. El comercio está `ACTIVE` y tiene `pey_bank_account_id`.
2. Muestra el QR general y paga **dos** veces $0.01 desde la app del banco.
3. `GET /api/movimientos/` muestra dos movimientos `pagado`, los dos de ese comercio, con montos `0.01`.

Evidencia: los dos movimientos (id, monto, `pagado_en`) y que el abono cayó en la CLABE del comercio, no en la de la plataforma.

- [ ] Firma: ______________ Fecha: __________

### 3.5 Venta (QR o notificación)

1. Crea una venta de $0.01 (QR de venta o notificación al celular).
2. Paga sin cerrar la pantalla de espera.
3. En menos de un ciclo de consulta (2 s, o el siguiente) la pantalla pasa a pagado, con monto y hora, sin recargar a mano.

Evidencia: la pantalla en pendiente y luego en pagado, y el movimiento `pagado` del comercio.

- [ ] Firma: ______________ Fecha: __________
