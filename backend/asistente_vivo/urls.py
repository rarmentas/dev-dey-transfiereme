from django.urls import path

from asistente_vivo.views import TokenAsistenteVivoView

urlpatterns = [path("token/", TokenAsistenteVivoView.as_view(), name="token")]
