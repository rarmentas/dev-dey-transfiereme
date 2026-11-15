"""Proveedor opcional. Nunca se instancia cuando la bandera está apagada."""

from django.conf import settings


def crear_modelo(modelo=None):
    if modelo is not None:
        return modelo
    if not settings.AGENTE_PEDIDOS_API_KEY:
        raise RuntimeError("Falta AGENTE_PEDIDOS_API_KEY")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.AGENTE_PEDIDOS_API_KEY,
        model=settings.AGENTE_PEDIDOS_MODELO,
        temperature=0,
        timeout=settings.AGENTE_PEDIDOS_TIMEOUT_S,
        max_retries=1,
        max_tokens=650,
    )
