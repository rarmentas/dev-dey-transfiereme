from django.conf import settings
from django.core.mail import send_mail
from django.utils.html import escape

from sesion.models import CodigoCorreo

_FONT = "system-ui, -apple-system, Segoe UI, Inter, sans-serif"


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


def _bloque_codigo_html(etiqueta: str, codigo: str) -> str:
    codigo_seguro = escape(codigo)
    return (
        f'<p style="margin:24px 0 8px;font-family:{_FONT};font-size:15px;'
        f'line-height:22px;color:#4F5D76;">{etiqueta}</p>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%" style="margin:0 0 8px;">'
        f'<tr><td align="center" style="background-color:#DCE7FB;border-radius:12px;'
        f'padding:20px 16px;">'
        f'<span style="font-family:{_FONT};font-size:36px;font-weight:800;'
        f'letter-spacing:0.08em;color:#0F3270;font-variant-numeric:tabular-nums;">'
        f"{codigo_seguro}</span>"
        f"</td></tr></table>"
    )


def _cuerpo_html(proposito: str, codigo: str) -> str:
    if proposito == CodigoCorreo.Proposito.ALTA:
        intro = "Recibimos su solicitud de cuenta en Transfiéreme."
        bloque = _bloque_codigo_html("Su código de confirmación es:", codigo)
        pie = "Si usted no solicitó esta cuenta, ignore este mensaje."
    else:
        intro = (
            "Recibimos su solicitud para restablecer la contraseña en Transfiéreme."
        )
        bloque = _bloque_codigo_html("Su código es:", codigo)
        pie = "Si usted no solicitó este cambio, ignore este mensaje."

    return f"""<!DOCTYPE html>
<html lang="es-MX">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F4F6FA;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
style="background-color:#F4F6FA;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
style="max-width:600px;background-color:#FFFFFF;border:1px solid #DCE3EE;border-radius:16px;">
<tr><td style="padding:32px 28px;font-family:{_FONT};">
<p style="margin:0 0 24px;font-size:22px;font-weight:700;line-height:28px;color:#1E4FA3;">
Transfiéreme</p>
<p style="margin:0 0 8px;font-size:15px;line-height:22px;color:#111A2B;">{intro}</p>
{bloque}
<p style="margin:16px 0 24px;font-size:15px;line-height:22px;color:#4F5D76;">
El código es de un solo uso y vence en 15 minutos.</p>
<p style="margin:0;font-size:13px;line-height:18px;color:#4F5D76;">{pie}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def enviar_codigo_correo(correo: str, proposito: str, codigo: str) -> None:
    send_mail(
        subject=_asunto(proposito),
        message=_cuerpo(proposito, codigo),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[correo],
        html_message=_cuerpo_html(proposito, codigo),
        fail_silently=False,
    )
