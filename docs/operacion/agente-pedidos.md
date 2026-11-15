# Agente de pedidos

El agente de LangGraph atiende únicamente pedidos del canal autenticado. El modelo devuelve una propuesta estructurada; el servidor resuelve productos y precios de la lista del comercio. El núcleo conserva registro, corrección, versiones, aceptación con token y cobro. La revisión y publicación siguen a cargo del tendero en Pedidos.

## Instalación y activación

1. Instalar `backend/requirements-canal.txt` y aplicar migraciones de Django.
2. Configurar `AGENTE_PEDIDOS_API_KEY` o `OPENAI_API_KEY`, `AGENTE_PEDIDOS_MODELO` y opcionalmente `AGENTE_PEDIDOS_TIMEOUT_S` en el entorno del worker. La clave específica del agente tiene prioridad. No guardar la clave en el repositorio. En GitLab, `OPENAI_API_KEY` puede estar dentro de la variable File `PROD_ENV_FILE` o como variable protegida independiente del job de producción.
3. En la app, abrir **Pedidos → Lista de precios**. Registrar nombre, alias, unidad, precio unitario en centavos y disponibilidad. Un producto sin precio queda pendiente de cotizar.
4. El dueño del comercio activa **Agente de pedidos** en esa pantalla. La bandera inicia apagada para cada comercio. Apagarla restaura el flujo guiado y conserva los pedidos existentes. Sin clave del modelo, el worker arranca normalmente si la bandera está apagada.

El despliegue copia `AGENTE_PEDIDOS_API_KEY` y/o `OPENAI_API_KEY`, `AGENTE_PEDIDOS_MODELO` y `AGENTE_PEDIDOS_TIMEOUT_S` a `.env.canal`; ninguna clave del modelo se copia a los entornos de cobros o STT. Si `OPENAI_API_KEY` está en el archivo y también como variable independiente, prevalece la del archivo. El agente puede listar los productos disponibles y consultar coincidencias por nombre con sus precios autorizados, sin crear pedidos. El cliente puede agregar, corregir y quitar renglones, siempre que quede al menos uno; para dejar un pedido vacío debe pedir revisión al tendero. Un pedido nuevo después del cierre crea otro registro y conserva el anterior.

El modelo admite un máximo de 4 000 caracteres de entrada, 100 nombres de catálogo en el prompt, 100 renglones por mensaje, 650 tokens de salida, un reintento de proveedor y un timeout de hasta 45 segundos. El lease por conversación es de 120 segundos; antes de escribir se vuelve a verificar el token y la fecha del lease bajo bloqueo. Un lease vencido descarta la propuesta de ese worker. El mensaje conserva texto y propuesta validada para reintentos. La salida usa la clave durable `mensaje:<id>`.

No hay checkpointer separado: el estado de negocio se almacena en `MensajeEntrante`, `Pedido`, `RenglonPedido` y `SalidaCanal`. El modelo no recibe herramientas de cobro, aceptación, publicación ni escritura libre. Los importes se calculan con `pedidos.contratos.calculo`; una fila pendiente impide mostrar total definitivo. El precio de cada renglón queda congelado en su versión, mientras la cotización publicada conserva su snapshot.

Para verificar sin mensajes ni cobros reales, ejecutar pruebas de `asistente_pedidos.tests`, `canales.tests` y `pedidos.tests` con un PostgreSQL de prueba. Los modelos falsos están en `asistente_pedidos/tests/test_agente.py`.
