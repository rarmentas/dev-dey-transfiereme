from django.urls import path

from canales.views import recibir_waha

urlpatterns = [path("", recibir_waha, name="webhook-waha")]
