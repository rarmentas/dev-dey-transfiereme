from django.urls import path

from webhooks.views import recibir_aviso_pey

urlpatterns = [
    path("pey/", recibir_aviso_pey, name="webhook-pey"),
]
