# Productos demo de tienda de abarrotes

Los archivos `backend/pedidos/datos_demo/abarrotes.csv`, `bebidas_botanas.csv` y
`limpieza_higiene.csv` contienen 36 productos típicos de una tienda mexicana. Sus
precios en centavos son **ilustrativos**: no representan precios vigentes ni deben
usarse como lista comercial sin revisión.

Cada CSV tiene las columnas `nombre`, `alias`, `unidad` y `precio_centavos`.
Separe varios alias con `|`. Para productos empacados, `pieza` significa un
paquete o envase de la presentación indicada en el nombre; la tortilla se vende
por `kg`.

La carga es manual. Con la base migrada y el comercio ya creado:

```bash
cd backend
.venv/bin/python manage.py sembrar_productos_demo --comercio-id 1
```

Para cargar solo uno o varios archivos, repita `--dataset`:

```bash
.venv/bin/python manage.py sembrar_productos_demo --comercio-id 1 --dataset abarrotes --dataset bebidas_botanas
```

El comercio debe tener `es_demo=True` o, con `DEBUG=True`,
`semilla_active_dev=True`. El comando no crea comercios, no se ejecuta
automáticamente en despliegues y no modifica productos existentes con el mismo
nombre. Puede repetirse sin duplicarlos. Revise y ajuste los precios desde el
catálogo del comercio antes de usarlo para pedidos.
