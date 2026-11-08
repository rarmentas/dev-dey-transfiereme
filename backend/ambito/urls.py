from django.urls import path

from ambito.views import GuardarClabeView

urlpatterns = [
    path("clabe/", GuardarClabeView.as_view(), name="cuenta-clabe"),
]
