import logging
import re
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ambito.models import Comercio, Membresia
from sesion.correo import enviar_codigo_correo
from sesion.models import CodigoCorreo

User = get_user_model()
logger = logging.getLogger(__name__)

TTL_MINUTOS = 15
_MENSAJE_CODIGO = "El código no es válido o ya expiró. Solicite uno nuevo."
_MENSAJE_CORREO_NO_ENVIADO = (
    "No pudimos enviar el correo en este momento. Intente de nuevo más tarde."
)

_CORREO_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def correo_valido(correo: str) -> bool:
    return bool(correo) and len(correo) <= 254 and _CORREO_RE.match(correo) is not None


def usuario_con_correo_existe(correo: str) -> bool:
    return User.objects.filter(
        Q(username__iexact=correo) | Q(email__iexact=correo),
    ).exists()


def _buscar_usuario_por_correo(correo: str):
    por_username = User.objects.filter(username__iexact=correo)[:2]
    if por_username.count() == 1:
        return por_username[0]
    candidatos = User.objects.filter(email__iexact=correo)[:2]
    if candidatos.count() == 1:
        return candidatos[0]
    return None


def _generar_codigo_seis_digitos() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _usuario_provisional_alta(correo: str) -> User:
    return User(username=correo, email=correo)


def _bloquear_y_crear_solicitud(
    correo: str,
    proposito: str,
    *,
    contrasena_hash: str = "",
) -> str:
    """Crea una solicitud vigente; debe llamarse dentro de transaction.atomic."""
    list(
        CodigoCorreo.objects.select_for_update().filter(
            correo=correo,
            proposito=proposito,
        ),
    )
    CodigoCorreo.objects.filter(
        correo=correo,
        proposito=proposito,
        usado_en__isnull=True,
    ).delete()
    codigo = _generar_codigo_seis_digitos()
    CodigoCorreo.objects.create(
        correo=correo,
        proposito=proposito,
        codigo_hash=make_password(codigo),
        contrasena_hash=contrasena_hash,
        expira_en=timezone.now() + timedelta(minutes=TTL_MINUTOS),
    )
    return codigo


def _enviar_olvido_sin_propagar(correo: str, codigo: str) -> None:
    try:
        enviar_codigo_correo(correo, CodigoCorreo.Proposito.OLVIDO, codigo)
    except Exception:
        logger.exception(
            "No se pudo enviar el código de olvido (correo=%s)",
            correo,
        )


@transaction.atomic
def solicitar_alta(correo: str, contrasena: str) -> tuple[bool, str | None]:
    if not correo_valido(correo):
        return False, "Indique un correo válido."
    try:
        validate_password(contrasena, user=_usuario_provisional_alta(correo))
    except ValidationError as exc:
        return False, " ".join(exc.messages)

    if usuario_con_correo_existe(correo):
        return False, "Este correo ya tiene cuenta. Entre o restablezca su contraseña."

    codigo = _bloquear_y_crear_solicitud(
        correo,
        CodigoCorreo.Proposito.ALTA,
        contrasena_hash=make_password(contrasena),
    )
    try:
        enviar_codigo_correo(correo, CodigoCorreo.Proposito.ALTA, codigo)
    except Exception:
        logger.exception(
            "No se pudo enviar el código de alta (correo=%s)",
            correo,
        )
        transaction.set_rollback(True)
        return False, _MENSAJE_CORREO_NO_ENVIADO
    return True, None


@transaction.atomic
def confirmar_alta(correo: str, codigo: str) -> tuple[bool, str | None]:
    if not correo_valido(correo) or not codigo:
        return False, _MENSAJE_CODIGO

    if usuario_con_correo_existe(correo):
        return False, _MENSAJE_CODIGO

    solicitud = (
        CodigoCorreo.objects.select_for_update()
        .filter(
            correo=correo,
            proposito=CodigoCorreo.Proposito.ALTA,
            usado_en__isnull=True,
        )
        .order_by("-creado_en")
        .first()
    )
    if solicitud is None or solicitud.expira_en < timezone.now():
        return False, _MENSAJE_CODIGO
    if not check_password(codigo, solicitud.codigo_hash):
        return False, _MENSAJE_CODIGO

    user = User(username=correo, email=correo)
    user.password = solicitud.contrasena_hash
    user.save()

    comercio = Comercio.objects.create(nombre="Mi comercio")
    Membresia.objects.create(usuario=user, comercio=comercio)

    solicitud.usado_en = timezone.now()
    solicitud.save(update_fields=["usado_en"])
    return True, None


def solicitar_olvido(correo: str) -> None:
    if not correo_valido(correo):
        return

    usuario = _buscar_usuario_por_correo(correo)
    if usuario is None:
        return

    codigo: str | None = None
    with transaction.atomic():
        codigo = _bloquear_y_crear_solicitud(
            correo,
            CodigoCorreo.Proposito.OLVIDO,
        )
    if codigo is not None:
        _enviar_olvido_sin_propagar(correo, codigo)


@transaction.atomic
def restablecer_olvido(correo: str, codigo: str, contrasena: str) -> tuple[bool, str | None]:
    if not correo_valido(correo) or not codigo:
        return False, _MENSAJE_CODIGO

    usuario = _buscar_usuario_por_correo(correo)
    if usuario is None:
        return False, _MENSAJE_CODIGO

    solicitud = (
        CodigoCorreo.objects.select_for_update()
        .filter(
            correo=correo,
            proposito=CodigoCorreo.Proposito.OLVIDO,
            usado_en__isnull=True,
        )
        .order_by("-creado_en")
        .first()
    )
    if solicitud is None or solicitud.expira_en < timezone.now():
        return False, _MENSAJE_CODIGO
    if not check_password(codigo, solicitud.codigo_hash):
        return False, _MENSAJE_CODIGO

    try:
        validate_password(contrasena, user=usuario)
    except ValidationError as exc:
        return False, " ".join(exc.messages)

    usuario.set_password(contrasena)
    usuario.save(update_fields=["password"])

    solicitud.usado_en = timezone.now()
    solicitud.save(update_fields=["usado_en"])
    return True, None
