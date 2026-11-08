# Backlog — pantalla de inicio de sesión y home

Elementos visibles en la app que aún no tienen API en el backend.

## Recuperación de contraseña

- Enlace en login: «¿Olvidó su contraseña?»
- Hoy muestra: «Esta opción estará disponible pronto.»
- Falta: flujo de correo o token, vista de restablecimiento y endpoints bajo `/api/sesion/` (o módulo de identidad).

## Alta de cuenta

- Enlace en login: «¿Nuevo? Cree su cuenta»
- Hoy muestra el mismo aviso provisional.
- Falta: registro de vendedor, validación y posible alta de comercio; el middleware ya reserva `RUTAS_ALTA_EXENTAS` en `sesion/middleware.py` para futuras rutas públicas.

## Home completo (mockup pantalla 2)

Fuera del alcance de la historia 1.13: «Hoy llevas», **Cobrar**, **Mi QR**, últimos cobros y barra de navegación inferior.
