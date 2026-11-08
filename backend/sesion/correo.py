from django.core.mail import send_mail
from django.conf import settings

from sesion.models import CodigoCorreo


def _asunto(proposito: str) -> str:
    if proposito == CodigoCorreo.Proposito.ALTA:
        return "Confirme su cuenta en Transfiéreme"
    return "Restablezca su contraseña en Transfiéreme"


def _cuerpo(proposito: str, codigo: str) -> str:
    if proposito == CodigoCorreo.Proposito.ALTA:
        return (
            "Recibimos su solicitud de cuenta en Transfiéreme.\n\n"
            f"Su código de confirmación es: {codigo}\n\n"
            "El código es de un solo uso y vence en 15 minutos.\n\n"
            "Si usted no solicitó esta cuenta, ignore este mensaje."
        )
    return (
        "Recibimos su solicitud para restablecer la contraseña en Transfiéreme.\n\n"
        f"Su código es: {codigo}\n\n"
        "El código es de un solo uso y vence en 15 minutos.\n\n"
        "Si usted no solicitó este cambio, ignore este mensaje."
    )


def enviar_codigo_correo(correo: str, proposito: str, codigo: str) -> None:
    send_mail(
        subject=_asunto(proposito),
        message=_cuerpo(proposito, codigo),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[correo],
        fail_silently=False,
    )
