"""API de cuentas del comercio de la sesión."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.cuenta_pey_servicio import AdaptadorNoProduccion
from ambito.cuentas_servicio import alta, cuenta_dict, elegir_default
from ambito.exceptions import ComercioEnCuerpoError, NoEsDuenoError, SinAmbitoError
from ambito.models import CuentaCobro
from ambito.operaciones_cuenta import ErrorOperacion, registrar, sincronizar
from ambito.permisos import requerir_dueno
from ambito.scope import (
    rechazar_comercio_en_cuerpo,
    rechazar_comercio_en_query,
    requerir_comercio,
)


class CuentasView(APIView):
    permission_classes = [IsAuthenticated]

    def _ejecutar(self, request, accion, cuenta_id=None):
        try:
            rechazar_comercio_en_query(request.query_params)
        except ComercioEnCuerpoError:
            return Response({"codigo": "COMERCIO_EN_QUERY"}, status=400)
        try:
            datos = request.data if isinstance(request.data, dict) else {}
            rechazar_comercio_en_cuerpo(datos)
            comercio = requerir_comercio(request)
            requerir_dueno(request)
            cuenta = None
            if cuenta_id:
                cuenta = CuentaCobro.objects.filter(
                    pk=cuenta_id, comercio=comercio
                ).first()
                if cuenta is None:
                    raise ErrorOperacion("CUENTA_NO_ENCONTRADA", 404)
            if accion == "lista":
                cuentas = [
                    cuenta_dict(c, comercio)
                    for c in comercio.cuentas.order_by("creada_en")
                ]
                return Response(
                    {
                        "cuentas": cuentas,
                        "predeterminada_id": str(comercio.cuenta_por_defecto_id)
                        if comercio.cuenta_por_defecto_id
                        else None,
                    }
                )
            if accion == "alta":
                cuenta = alta(comercio, datos.get("clabe"))
                return Response({"cuenta": cuenta_dict(cuenta, comercio)}, status=201)
            if accion == "registro":
                cuenta, replay = registrar(
                    cuenta,
                    nombre=datos.get("nombre"),
                    entidad=datos.get("entidad"),
                    alias=datos.get("alias"),
                    clave=datos.get("command_key"),
                    version=datos.get("expected_version"),
                )
                return Response(
                    {"cuenta": cuenta_dict(cuenta, comercio), "replayed": replay}
                )
            if accion == "sync":
                cuenta = sincronizar(cuenta)
            if accion == "default":
                cuenta = elegir_default(comercio, cuenta, datos.get("expected_version"))
                comercio.cuenta_por_defecto_id = cuenta.pk
                return Response(
                    {
                        "predeterminada_id": str(cuenta.pk),
                        "cuenta": cuenta_dict(cuenta, comercio),
                    }
                )
            return Response({"cuenta": cuenta_dict(cuenta, comercio)})
        except ComercioEnCuerpoError:
            return Response({"codigo": "COMERCIO_EN_CUERPO"}, status=400)
        except (NoEsDuenoError, SinAmbitoError):
            return Response({"codigo": "NO_ES_DUENO"}, status=403)
        except AdaptadorNoProduccion:
            return Response({"codigo": "ADAPTADOR_NO_PRODUCCION"}, status=503)
        except ErrorOperacion as exc:
            return Response({"codigo": exc.codigo, **exc.datos}, status=exc.status)

    def get(self, request):
        return self._ejecutar(request, "lista")

    def post(self, request, cuenta_id=None, accion="alta"):
        return self._ejecutar(request, accion, cuenta_id)
