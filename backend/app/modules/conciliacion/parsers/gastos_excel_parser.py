"""Lectura del registro de transferencias de gastos, sin ejecutar fórmulas."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import load_workbook

from app.modules.conciliacion.utils.normalization import normalize_text


def parse_gastos_excel(contenido: bytes) -> list[dict]:
    try:
        libro = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError("No se pudo leer el Excel. Selecciona un archivo .xlsx válido.") from exc
    registros = []
    try:
        for hoja in libro:
            columnas = None
            for numero, valores in enumerate(hoja.iter_rows(values_only=True), 1):
                if not any(v is not None for v in valores):
                    continue
                if columnas is None:
                    encabezados = {normalize_text(v): i for i, v in enumerate(valores) if v is not None}
                    if {'fecha', 'destinatario', 'monto'} <= encabezados.keys():
                        columnas = encabezados
                    continue
                def celda(nombre):
                    indice = columnas.get(nombre)
                    return valores[indice] if indice is not None and indice < len(valores) else None
                # Ignorar únicamente pies de tabla sin datos de transferencia.
                if not celda('fecha') and not celda('destinatario'):
                    continue
                referencia = f"{hoja.title}, fila {numero}"
                fecha = celda('fecha')
                if isinstance(fecha, datetime):
                    fecha = fecha.date()
                elif isinstance(fecha, str):
                    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                        try:
                            fecha = datetime.strptime(fecha.strip(), formato).date()
                            break
                        except ValueError:
                            pass
                if not isinstance(fecha, date):
                    raise ValueError(f"Fecha inválida en {referencia}.")
                destinatario = str(celda('destinatario') or '').strip()
                if not destinatario:
                    raise ValueError(f"Falta el destinatario en {referencia}.")
                try:
                    valor = celda('monto')
                    if isinstance(valor, str):
                        valor = valor.replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
                    monto = Decimal(str(valor))
                    if not monto.is_finite() or monto <= 0 or monto != monto.to_integral_value() or monto > 9223372036854775807:
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Monto inválido en {referencia}; debe ser un entero positivo en CLP.")
                estado = normalize_text(celda('estado') or '')
                if estado and estado not in ('aceptada', 'aceptado', 'aprobada', 'aprobado', 'pagada', 'pagado', 'realizada', 'realizado'):
                    raise ValueError(f"La transferencia de {referencia} no está aceptada ({celda('estado')}).")
                registros.append(dict(hoja=hoja.title, fila=numero, fecha=fecha,
                    destinatario=destinatario, monto=int(monto),
                    observacion=str(celda('observacion') or '').strip(),
                    rut=str(celda('rut') or '').strip()))
    finally:
        libro.close()
    if not registros:
        raise ValueError("No hay gastos. El Excel debe incluir FECHA, DESTINATARIO y MONTO.")
    return registros
