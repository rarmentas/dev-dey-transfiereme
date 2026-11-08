from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def salud(request: Request) -> Response:
    """Comprueba que Django responde y puede hablar con Postgres."""
    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_ok = cursor.fetchone()[0] == 1
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degradado"
    http_status = 200 if db_ok else 503
    return Response(
        {
            "estado": status,
            "base_datos": db_ok,
            "mensaje": "Cody API en línea" if db_ok else "API sin conexión a Postgres",
        },
        status=http_status,
    )
