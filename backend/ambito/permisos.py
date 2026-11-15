from ambito.exceptions import NoEsDuenoError


def requerir_dueno(request):
    if not getattr(request, "es_dueno", False):
        raise NoEsDuenoError("La operación requiere ser dueño del comercio.")
