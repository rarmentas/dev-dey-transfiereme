"""Vistas de estado y registro de cuenta pey (ámbito por sesión)."""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.cuenta_pey_servicio import (
    AdaptadorNoProduccion,
    CuentaPeyYaRegistrada,
    SinClabeGuardada,
    _MENSAJE_ADAPTADOR,
    _MENSAJE_PEY_INCIERTO,
    _MENSAJE_PEY_NO_REGISTRO,
    _MENSAJE_SIN_CLABE,
    _MENSAJE_SYNC_PRONTO,
    _MENSAJE_YA_REGISTRADA,
    estado_cuenta_dict,
    registrar_cuenta_en_pey,
    SyncMuyPronto,
    sincronizar_cuenta_y_estado_candado,
    validar_registro_pey,
)
from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import preparar_operacion_cobro, requerir_comercio
from pey.tipos import ErrorPey, ParametroInvalido

logger = logging.getLogger(__name__)


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


def _booleano_reemplazar(valor: object) -> bool:
    if valor is True:
        return True
    if isinstance(valor, str) and valor.strip().lower() in {"true", "1", "si", "sí"}:
        return True
    return False


class EstadoCuentaPeyView(APIView):
    """Estado de la cuenta pey del comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            comercio = requerir_comercio(request)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)
        return Response(estado_cuenta_dict(comercio))


class RegistrarCuentaPeyView(APIView):
    """Registra la CLABE guardada en pey."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        try:
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        nombre_raw = datos.get("nombre")
        entidad_raw = datos.get("entidad")
        alias_raw = datos.get("alias")
        reemplazar = _booleano_reemplazar(datos.get("reemplazar"))
        nombre = nombre_raw if isinstance(nombre_raw, str) else ""
        entidad = entidad_raw if isinstance(entidad_raw, str) else ""
        alias = alias_raw if isinstance(alias_raw, str) else ""

        try:
            validar_registro_pey(nombre=nombre, entidad=entidad)
        except ParametroInvalido as exc:
            return Response({"detail": str(exc)}, status=400)

        try:
            comercio, _codi_pey = registrar_cuenta_en_pey(
                comercio.pk,
                nombre=nombre,
                entidad=entidad,
                alias=alias,
                reemplazar=reemplazar,
            )
        except AdaptadorNoProduccion:
            return Response(
                {"detail": _MENSAJE_ADAPTADOR, "codigo": "ADAPTADOR_NO_PRODUCCION"},
                status=503,
            )
        except SinClabeGuardada:
            return Response(
                {"detail": _MENSAJE_SIN_CLABE, "codigo": "SIN_CLABE"},
                status=400,
            )
        except CuentaPeyYaRegistrada:
            return Response(
                {"detail": _MENSAJE_YA_REGISTRADA, "codigo": "CUENTA_PEY_YA_REGISTRADA"},
                status=409,
            )
        except ParametroInvalido as exc:
            return Response({"detail": str(exc)}, status=400)
        except ErrorPey as exc:
            logger.warning(
                "pey no registró cuenta tipo=%s request_id=%s comercio_id=%s",
                exc.tipo,
                exc.request_id,
                comercio.pk,
            )
            if exc.puede_haberse_creado:
                return Response(
                    {
                        "detail": _MENSAJE_PEY_INCIERTO,
                        "tipo": exc.tipo,
                        "codigo": "PEY_INCIERTO",
                        "request_id": exc.request_id,
                    },
                    status=503,
                )
            return Response(
                {
                    "detail": _MENSAJE_PEY_NO_REGISTRO,
                    "tipo": exc.tipo,
                    "request_id": exc.request_id,
                },
                status=502,
            )

        return Response(estado_cuenta_dict(comercio))


class SincronizarCuentaPeyView(APIView):
    """Consulta pey y actualiza codiStatus del comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        try:
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        try:
            cuerpo, error = sincronizar_cuenta_y_estado_candado(comercio.pk)
        except SyncMuyPronto as exc:
            return Response(
                {
                    "detail": _MENSAJE_SYNC_PRONTO,
                    "reintento_en_segundos": exc.reintento_en_segundos,
                },
                status=429,
            )
        if error is not None and error.tipo != "BANK_ACCOUNT_NOT_FOUND":
            logger.warning(
                "sync cuenta pey tipo=%s request_id=%s comercio_id=%s",
                error.tipo,
                error.request_id,
                comercio.pk,
            )
        return Response(cuerpo)
