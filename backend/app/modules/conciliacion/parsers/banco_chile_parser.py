"""Parser de cartolas del Banco de Chile.

Los importes se asocian por sus coordenadas a la fecha y descripción de su
fila. La columna del importe determina si es un abono, independientemente
del texto de la transacción.
"""
import re
from datetime import date, datetime
from typing import BinaryIO, Optional

import fitz  # PyMuPDF

from .base_parser import BaseCartolaParser, ParsedCartola, ParsedMovimiento


# --- Metadatos (tolerantes a saltos de línea entre rótulo y valor) ---
_CUENTA_RE = re.compile(
    r"N[°ºo]\s*DE\s*CUENTA\s*[:\s]+([\d\-]{4,})",
    re.IGNORECASE,
)
_CARTOLA_NUM_RE = re.compile(
    r"CARTOLA\s*N[°ºo]\s*[:\s]+(\d+)",
    re.IGNORECASE,
)
_PERIODO_RE = re.compile(
    r"DESDE\s*:?\s*(\d{2}/\d{2}/\d{4})\s*HASTA\s*:?\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

# --- Filas de movimiento ---
_FECHA_CORTA_RE = re.compile(r"^(\d{2})/(\d{2})$")


def _parse_monto(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    cleaned = raw.strip().replace(".", "").replace(",", "").strip()
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def _extraer_depositante(descripcion: str) -> Optional[str]:
    m = re.search(r"TRASPASO\s+DE\s*:\s*(.+)", descripcion, re.IGNORECASE)
    if m:
        nombre = m.group(1).strip()
        nombre = re.split(
            r"\s+INTE\b|\s+INTERNET\b|\s+CEN\b|\s+TRAL\b|OF\.\s*CONCEPCION",
            nombre,
        )[0].strip()
        return nombre or None
    if "DEPOSITO EN EFECTIVO" in descripcion.upper():
        return "DEPOSITO EN EFECTIVO"
    return None


def _construir_fecha(dia: int, mes: int, anio: int) -> Optional[date]:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _anio_desde_periodo(periodo_hasta: Optional[date]) -> int:
    if periodo_hasta is not None:
        return periodo_hasta.year
    return date.today().year


class BancoChileParser(BaseCartolaParser):
    """Parser específico para cartolas del Banco de Chile."""

    def parse(self, file_stream: BinaryIO) -> ParsedCartola:
        data = file_stream.read()
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            return ParsedCartola(
                banco="Banco de Chile",
                numero_cuenta="",
                numero_cartola=None,
                periodo_desde=None,
                periodo_hasta=None,
                total_abonos_informado=None,
                total_cargos_informado=None,
                saldo_inicial_informado=None,
                saldo_final_informado=None,
                errores=[f"No se pudo abrir el PDF: {exc}"],
            )

        texto_completo = "\n".join(page.get_text("text", sort=True) for page in doc)

        cartola = ParsedCartola(
            banco="Banco de Chile",
            numero_cuenta="",
            numero_cartola=None,
            periodo_desde=None,
            periodo_hasta=None,
            total_abonos_informado=None,
            total_cargos_informado=None,
            saldo_inicial_informado=None,
            saldo_final_informado=None,
        )

        m = _CUENTA_RE.search(texto_completo)
        if m:
            cartola.numero_cuenta = m.group(1).strip()

        m = _CARTOLA_NUM_RE.search(texto_completo)
        if m:
            cartola.numero_cartola = m.group(1).strip()

        m = _PERIODO_RE.search(texto_completo)
        if m:
            try:
                cartola.periodo_desde = datetime.strptime(m.group(1), "%d/%m/%Y").date()
                cartola.periodo_hasta = datetime.strptime(m.group(2), "%d/%m/%Y").date()
            except ValueError:
                pass

        movimientos: list[ParsedMovimiento] = []
        cargos: list[ParsedMovimiento] = []
        for pagina, page in enumerate(doc, start=1):
            abonos_pagina, cargos_pagina = self._extraer_movimientos_pagina(
                page, pagina, cartola.periodo_hasta
            )
            movimientos.extend(abonos_pagina)
            cargos.extend(cargos_pagina)

        cartola.movimientos = movimientos
        cartola.cargos = cargos
        self._extraer_totales_informados(texto_completo, cartola)
        for page in doc:
            self._extraer_resumen_pagina(page, cartola)
        doc.close()

        if not cartola.movimientos and not cartola.cargos:
            cartola.errores.append(
                "No se detectaron movimientos de abono. Verifica el formato del PDF."
            )

        return cartola

    # ---------- Extracción de movimientos ----------
    def _extraer_movimientos_pagina(
        self, page, pagina: int, periodo_hasta: Optional[date]
    ) -> tuple[list[ParsedMovimiento], list[ParsedMovimiento]]:
        anio = _anio_desde_periodo(periodo_hasta)
        movimientos: list[ParsedMovimiento] = []
        cargos: list[ParsedMovimiento] = []

        try:
            tabs = page.find_tables()
        except Exception:
            return movimientos, cargos

        palabras = page.get_text("words")
        for tabla in tabs.tables:
            filas = tabla.extract()
            # Las columnas vacías que detecta PyMuPDF pueden variar. Identificar
            # las columnas por su encabezado, no por un índice fijo.
            encabezado = None
            for indice, fila in enumerate(filas):
                columnas = {
                    "fecha": next((i for i, c in enumerate(fila)
                                   if c and "DIA/MES" in c.upper()), None),
                    "detalle": next((i for i, c in enumerate(fila)
                                     if c and "DETALLE" in c.upper()), None),
                    "abono": next((i for i, c in enumerate(fila)
                                   if c and "ABONOS" in c.upper()), None),
                    "cargo": next((i for i, c in enumerate(fila)
                                   if c and "CARGOS" in c.upper()), None),
                }
                if all(columnas[nombre] is not None for nombre in ("fecha", "detalle")) \
                        and any(columnas[nombre] is not None for nombre in ("abono", "cargo")):
                    encabezado = indice
                    break
            if encabezado is None:
                continue

            for fila in tabla.rows[encabezado + 1:]:
                celdas = {
                    nombre: fila.cells[i] if i is not None and i < len(fila.cells) else None
                    for nombre, i in columnas.items()
                }
                if celdas["fecha"] is None or celdas["detalle"] is None:
                    continue
                fechas = sorted(
                    (p for p in palabras
                     if self._en_celda(p, celdas["fecha"])
                     and _FECHA_CORTA_RE.fullmatch(p[4])),
                    key=lambda p: p[1],
                )
                # Una celda puede abarcar todos los movimientos de la página.
                # Los puntos medios entre fechas delimitan cada fila real.
                for i, palabra_fecha in enumerate(fechas):
                    centro = (palabra_fecha[1] + palabra_fecha[3]) / 2
                    arriba = (celdas["fecha"][1] if i == 0 else
                              (centro + (fechas[i - 1][1] + fechas[i - 1][3]) / 2) / 2)
                    abajo = (celdas["fecha"][3] if i + 1 == len(fechas) else
                             (centro + (fechas[i + 1][1] + fechas[i + 1][3]) / 2) / 2)
                    detalle = self._texto_fila(palabras, celdas["detalle"], arriba, abajo)
                    dia, mes = map(int, palabra_fecha[4].split("/"))
                    fecha = _construir_fecha(dia, mes, anio)
                    if fecha is None:
                        continue
                    for campo, destino in (("abono", movimientos), ("cargo", cargos)):
                        if celdas[campo] is None:
                            continue
                        monto = _parse_monto(
                            self._texto_fila(palabras, celdas[campo], arriba, abajo)
                        )
                        if monto is None or monto <= 0:
                            continue
                        destino.append(ParsedMovimiento(
                            fecha=fecha,
                            descripcion_original=detalle,
                            depositante_original=(
                                _extraer_depositante(detalle) if campo == "abono" else None
                            ),
                            monto=monto,
                            pagina_origen=pagina,
                            orden_en_pagina=len(destino) + 1,
                        ))

        return movimientos, cargos

    @staticmethod
    def _en_celda(palabra, celda) -> bool:
        x = (palabra[0] + palabra[2]) / 2
        y = (palabra[1] + palabra[3]) / 2
        return celda[0] <= x < celda[2] and celda[1] <= y < celda[3]

    @classmethod
    def _texto_fila(cls, palabras, celda, arriba: float, abajo: float) -> str:
        seleccion = sorted(
            (p for p in palabras if cls._en_celda(p, celda)
             and arriba <= (p[1] + p[3]) / 2 < abajo),
            key=lambda p: (p[1], p[0]),
        )
        return " ".join(p[4] for p in seleccion)

    @staticmethod
    def _extraer_resumen_pagina(page, cartola: ParsedCartola) -> None:
        # Los rótulos del resumen y sus cifras están en líneas distintas.
        # Buscar la cifra bajo cada rótulo dentro de su columna visual.
        palabras = page.get_text("words")
        for rotulo, campo in (
            ("OTROS ABONOS", "total_abonos_informado"),
            ("OTROS CARGOS", "total_cargos_informado"),
        ):
            for rect in page.search_for(rotulo):
                candidatos = [p for p in palabras
                              if rect.y1 <= p[1] <= rect.y1 + 25
                              and rect.x0 <= (p[0] + p[2]) / 2 <= rect.x1
                              and _parse_monto(p[4]) is not None]
                if candidatos:
                    valor = min(candidatos, key=lambda p: p[1])
                    setattr(cartola, campo, _parse_monto(valor[4]))

    def _extraer_totales_informados(self, texto: str, cartola: ParsedCartola) -> None:
        m = re.search(r"OTROS\s+ABONOS\s*[\n\s]*([\d\.]+)", texto, re.IGNORECASE)
        if not m:
            m = re.search(
                r"TOTAL\s+ABONOS\s*[:\s]*\$?\s*([\d\.]+)", texto, re.IGNORECASE
            )
        if m:
            cartola.total_abonos_informado = _parse_monto(m.group(1))

        m = re.search(r"OTROS\s+CARGOS\s*[\n\s]*([\d\.]+)", texto, re.IGNORECASE)
        if not m:
            m = re.search(
                r"TOTAL\s+CARGOS\s*[:\s]*\$?\s*([\d\.]+)", texto, re.IGNORECASE
            )
        if m:
            cartola.total_cargos_informado = _parse_monto(m.group(1))

        m = re.search(r"SALDO\s+INICIAL\s*[\n\s]*([\d\.]+)", texto, re.IGNORECASE)
        if m:
            cartola.saldo_inicial_informado = _parse_monto(m.group(1))

        m = re.search(r"SALDO\s+FINAL\s*[\n\s]*([\d\.]+)", texto, re.IGNORECASE)
        if m:
            cartola.saldo_final_informado = _parse_monto(m.group(1))