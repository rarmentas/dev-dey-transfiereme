from django.urls import path

from webhooks.views import recibir_aviso_desarrollo, recibir_aviso_pey

urlpatterns = [
    path("pey/", recibir_aviso_pey, name="webhook-pey"),
    path("desarrollo/", recibir_aviso_desarrollo, name="webhook-desarrollo"),
]
