"""Webhook autenticado de WAHA."""

import json

from django.db import OperationalError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from canales.hmac_waha import FirmaInvalida, verificar_firma
from canales.recepcion import recibir


@csrf_exempt
@require_POST
def recibir_waha(request):
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 262144:
            return JsonResponse({"codigo": "CUERPO_DEMASIADO_GRANDE"}, status=413)
        cuerpo = request.body
        if len(cuerpo) > 262144:
            return JsonResponse({"codigo": "CUERPO_DEMASIADO_GRANDE"}, status=413)
        verificar_firma(cuerpo, request.headers)
        datos = json.loads(cuerpo)
        estado = recibir(datos, request.headers.get("X-Webhook-Id", ""))
    except FirmaInvalida:
        return JsonResponse({"codigo": "FIRMA_INVALIDA"}, status=401)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"codigo": "PAYLOAD_INVALIDO"}, status=400)
    except OperationalError:
        return JsonResponse({"codigo": "SERVICIO_NO_DISPONIBLE"}, status=503)
    return JsonResponse({"estado": estado})
