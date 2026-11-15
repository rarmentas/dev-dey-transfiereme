from django.urls import path

from ambito.views_cuentas import CuentasView

urlpatterns = [
    path("", CuentasView.as_view()),
    path("<uuid:cuenta_id>/registro/", CuentasView.as_view(), {"accion": "registro"}),
    path("<uuid:cuenta_id>/sincronizar/", CuentasView.as_view(), {"accion": "sync"}),
    path(
        "<uuid:cuenta_id>/predeterminada/", CuentasView.as_view(), {"accion": "default"}
    ),
]
