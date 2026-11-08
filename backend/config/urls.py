from django.urls import path

from config.views import salud

urlpatterns = [
    path("api/salud/", salud, name="salud"),
]
