from rest_framework.authentication import SessionAuthentication


class SessionAuthenticationSinCsrf(SessionAuthentication):
    """Sesión por cookie sin exigir token CSRF en el encabezado (cierre con solo sessionid)."""

    def enforce_csrf(self, request) -> None:
        return
