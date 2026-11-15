"""Proyección compatible y rutas anteriores de cuenta pey."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.cuenta_pey_servicio import estado_cuenta_dict
from ambito.exceptions import SinAmbitoError
from ambito.scope import requerir_comercio


class EstadoCuentaPeyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return Response(estado_cuenta_dict(requerir_comercio(request)))
        except SinAmbitoError as exc:
            return Response({"detail": str(exc)}, status=403)


class RegistrarCuentaPeyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({"codigo": "USAR_CUENTAS"}, status=409)


class SincronizarCuentaPeyView(RegistrarCuentaPeyView):
    pass
