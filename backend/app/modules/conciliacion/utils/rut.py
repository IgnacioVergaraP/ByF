"""Validación y normalización de RUT chileno."""
import re


def _limpiar(rut: str) -> str:
    """Quita puntos, guiones y espacios. Devuelve solo dígitos + DV."""
    if not rut:
        return ""
    return re.sub(r"[^0-9kK]", "", str(rut)).upper()


def _calcular_dv(cuerpo: str) -> str:
    """Calcula el dígito verificador (módulo 11)."""
    if not cuerpo.isdigit():
        return ""
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = suma % 11
    dv = 11 - resto
    if dv == 11:
        return "0"
    if dv == 10:
        return "K"
    return str(dv)


def validar_rut(rut: str) -> bool:
    """Valida un RUT chileno con su dígito verificador."""
    limpio = _limpiar(rut)
    if len(limpio) < 2:
        return False
    cuerpo = limpio[:-1]
    dv = limpio[-1]
    if not cuerpo.isdigit():
        return False
    return _calcular_dv(cuerpo) == dv


def normalizar_rut(rut: str) -> str:
    """Devuelve 'XXXXXXXX-DV' o '' si no es válido."""
    if not validar_rut(rut):
        return ""
    limpio = _limpiar(rut)
    return f"{limpio[:-1]}-{limpio[-1]}"