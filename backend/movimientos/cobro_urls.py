from django.urls import path

from movimientos.views_cobro import AltaQrGeneralView

urlpatterns = [
    path("qr-general/", AltaQrGeneralView.as_view(), name="cobro-qr-general"),
]
