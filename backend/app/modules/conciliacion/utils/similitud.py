"""Utilidades de similitud de texto para sugerencias."""
import re
import unicodedata
from difflib import SequenceMatcher


_STOP_WORDS = {
    "spa", "ltda", "limitada", "sa", "s.a", "eirl", "cia", "compania",
    "de", "la", "el", "los", "las", "y", "e",
}


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokens(texto: str) -> set[str]:
    return {t for t in normalizar(texto).split() if t and t not in _STOP_WORDS}


def similitud_razon_social(a: str, b: str) -> float:
    """Similitud 0..1 combinando tres señales:

    - SequenceMatcher sobre el string completo (forma).
    - Jaccard de tokens (solapamiento léxico).
    - Contención de tokens (bonus si una entidad está contenida en la otra).
    """
    if not a or not b:
        return 0.0
    na, nb = normalizar(a), normalizar(b)
    if not na or not nb:
        return 0.0

    seq = SequenceMatcher(None, na, nb).ratio()

    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return round(seq, 4)

    jaccard = len(ta & tb) / len(ta | tb)

    # Bonus de contención: si los tokens "cortos" están todos dentro del "largo"
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    contencion = len(small & large) / len(small) if small else 0.0

    # Pesos: 30% forma, 40% jaccard, 30% contención
    score = (seq * 0.3) + (jaccard * 0.4) + (contencion * 0.3)
    return round(min(1.0, score), 4)


def similitud_codigo_propiedad(codigo_factura: str, nombre_propiedad: str) -> float:
    """Similitud entre 'LOCAL 13-14' y 'LOCAL 13-14' o 'Local 13/14'."""
    if not codigo_factura or not nombre_propiedad:
        return 0.0
    a = normalizar(codigo_factura)
    b = normalizar(nombre_propiedad)
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()