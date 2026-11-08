"""Validación de CLABE (18 dígitos, dígito verificador Banxico)."""

_PESOS = (3, 7, 1)


def clabe_es_valida(clabe: str) -> bool:
    """Devuelve True si la CLABE tiene formato y dígito verificador válidos."""
    if not isinstance(clabe, str) or len(clabe) != 18 or not clabe.isdigit():
        return False
    cuerpo = clabe[:17]
    verificador = int(clabe[17])
    total = 0
    for i, digito in enumerate(cuerpo):
        total += int(digito) * _PESOS[i % 3]
    esperado = (10 - (total % 10)) % 10
    return verificador == esperado
