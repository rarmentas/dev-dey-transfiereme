# Cobro CoDi en la app del banco

Recorrido actual, antes de Cody. El comercio arma el cobro dentro de la app de su banco. El cliente autoriza en la suya. SPEI abona la cuenta y los dos reciben confirmación.

```mermaid
flowchart TD
    alta["Alta previa: validar CLABE, tarjeta o celular"] --> abrir["1. Abrir la app del banco y buscar CoDi"]
    abrir --> capturar["2. Capturar monto, concepto y referencia"]
    capturar --> canal{"3. Canal de cobro"}

    canal -->|QR| qr["Mostrar el QR en pantalla, imagen o impreso"]
    canal -->|Sin monto| fijo["QR reutilizable: el cliente escribe el monto"]
    canal -->|Notificación| push["Enviar el cobro al celular del cliente"]
    canal -->|NFC| nfc["Acercar los dos teléfonos"]

    qr --> autorizar["4. El cliente revisa y autoriza con NIP o huella"]
    fijo --> autorizar
    push --> autorizar
    nfc --> autorizar

    push -.-> rechazar["Rechaza o pospone"]
    autorizar --> spei["5. SPEI abona la cuenta del comercio"]
    spei --> aviso["Aviso de confirmación a ambos"]
```
