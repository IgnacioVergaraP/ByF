"""Utilidades para llaves de idempotencia en operaciones de pago."""
import uuid
from datetime import datetime, timezone


def generar_llave() -> str:
    """Genera una llave única basada en UUID4 + timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{ts}-{uuid.uuid4()}"


def es_valida(llave: str) -> bool:
    if not llave:
        return False
    if len(llave) > 128:
        return False
    return True