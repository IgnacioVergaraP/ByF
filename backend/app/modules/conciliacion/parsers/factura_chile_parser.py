"""Parser de facturas electrónicas chilenas."""
import re
from datetime import date, datetime
from typing import Optional

from app.modules.conciliacion.parsers.base_factura_parser import (
    BaseFacturaParser, ParsedDetalle, ParsedFactura,
)
from app.modules.conciliacion.utils.ocr import ocr_png
from app.modules.conciliacion.utils.pdf_text import (
    cantidad_paginas, extraer_texto_paginas, renderizar_pagina_png,
    texto_suficiente,
)
from app.modules.conciliacion.utils.rut import normalizar_rut


def _parse_monto(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    # Acepta "40.127", "40 875.099", "40875099", "$940.127"
    limpio = re.sub(r"[^\d]", "", str(raw))
    if not limpio:
        return None
    try:
        return int(limpio)
    except ValueError:
        return None


def _parse_fecha(raw: str) -> Optional[date]:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


class FacturaChileParser(BaseFacturaParser):
    def parse(self, data: bytes, archivo_nombre: str) -> ParsedFactura:
        parsed = ParsedFactura()
        n_paginas = cantidad_paginas(data)
        textos = extraer_texto_paginas(data)
        texto_tablas = ""

        if not all(texto_suficiente(t) for t in textos):
            textos = []
            for i in range(1, n_paginas + 1):
                png = renderizar_pagina_png(data, i)
                textos.append(ocr_png(png) if png else "")
                if i == 1 and png:
                    texto_tablas = ocr_png(png, tablas=True)
            parsed.metodo_extraccion = "ocr"
        else:
            parsed.metodo_extraccion = "texto"

        texto = textos[0] if textos else ""
        if not texto:
            parsed.errores.append("No se pudo extraer texto de la factura.")
            return parsed

        # Detectar tipo de factura
        self._detectar_tipo(texto, parsed)

        self._extraer_identidad(texto_tablas or texto, parsed)
        self._extraer_totales(texto_tablas or texto, parsed)
        self._extraer_detalles(texto_tablas or texto, parsed)

        return parsed

    # ---------- Tipo de documento ----------
    def _detectar_tipo(self, texto: str, parsed: ParsedFactura) -> None:
        upper = texto.upper()
        if "FACTURA NO AFECTA" in upper or "FACTURA EXENTA" in upper:
            parsed.tipo_documento = "FACTURA_EXENTA_ELECTRONICA"
        elif "BOLETA" in upper:
            parsed.tipo_documento = "BOLETA_ELECTRONICA"
        else:
            parsed.tipo_documento = "FACTURA_ELECTRONICA"

    # ---------- Identidad ----------
    def _extraer_identidad(self, texto: str, parsed: ParsedFactura) -> None:
        m = re.search(r"N[º°o]\s*([\d\.]+)", texto, re.IGNORECASE)
        if m:
            parsed.folio = re.sub(r"\D", "", m.group(1))

        ruts = re.findall(r"R\.?U\.?T\.?\s*:?\s*([\d\.\s]+-[\dkK])", texto, re.IGNORECASE)
        if ruts:
            parsed.rut_emisor = normalizar_rut(ruts[0])
            if len(ruts) > 1:
                parsed.rut_receptor = normalizar_rut(ruts[1])

        emisor_corte = re.search(
            r"(?:R\.?U\.?T\.?\s*:|FACTURA\s+ELECTR[ÓO]NICA)",
            texto, re.IGNORECASE,
        )
        if emisor_corte:
            emisor_raw = texto[:emisor_corte.start()].strip()
            parsed.razon_social_emisor = re.sub(r"\s+", " ", emisor_raw)[:255].strip()

        m = re.search(
            r"Cliente\s*:?\s*(.+?)(?:R\.?U\.?T\.?|Giro|Direcci[óo]n|Comuna|Emisi[óo]n|Fecha)",
            texto, re.IGNORECASE | re.DOTALL,
        )
        if m:
            receptor = re.sub(r"\s+", " ", m.group(1)).strip()
            parsed.razon_social_receptor = receptor[:255]

        # En las plantillas con giro bajo el nombre, la razón social puede
        # compartir sus líneas con el recuadro del RUT y tipo de documento.
        cabecera = re.split(r"\bCOMPRA\s*,", texto, maxsplit=1, flags=re.IGNORECASE)
        if len(cabecera) == 2:
            nombre = re.sub(
                r"R\.?U\.?T\.?\s*:?\s*[\d.\s]+-[\dkK]", "", cabecera[0],
                flags=re.IGNORECASE,
            )
            nombre = re.sub(r"FACTURA[^\n]*", "", nombre, flags=re.IGNORECASE)
            nombre = re.sub(r"^[^\w\n]*[a-zA-Z]{1,2}[ \t]+(?=[A-ZÁÉÍÓÚÑ]{3})", "", nombre,
                            flags=re.MULTILINE)
            lineas = [linea for linea in nombre.splitlines()
                      if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3}", linea)]
            parsed.razon_social_emisor = re.sub(r"\s+", " ", " ".join(lineas)).strip()[:255]

        # Emisión: acepta "Emisión:", "Fecha :"
        m = re.search(
            r"(?:Emisi[oó]n|Fecha)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            texto, re.IGNORECASE,
        )
        if m:
            parsed.fecha_emision = _parse_fecha(m.group(1))

        # Vencimiento: acepta "Vence:", "Vto :"
        m = re.search(
            r"(?:Venc[e]?|Vto)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            texto, re.IGNORECASE,
        )
        if m:
            parsed.fecha_vencimiento = _parse_fecha(m.group(1))

    # ---------- Totales ----------
    def _extraer_totales(self, texto: str, parsed: ParsedFactura) -> None:
        texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
        texto = texto.replace("|", " ")
        monto = r"(?:\d{1,3}(?:[. \t]\d{3})+|\d+)"

        # Caso 1: factura afecta — Neto / Exento / IVA / TOTAL
        m = re.search(
            rf"Neto\s+(?:Monto\s+)?Exento\s+IVA\s*(?:19\s*%)?\s+"
            rf"TOTAL\s*\$?\s*({monto})\s+({monto})\s+({monto})\s+({monto})(?![\d.])",
            texto, re.IGNORECASE,
        )
        if m:
            parsed.neto, parsed.exento, parsed.iva, parsed.total = (
                _parse_monto(valor) for valor in m.groups()
            )
            return

        # Caso 2: factura exenta — NETO / DESCUENTOS / TOTAL (sin IVA)
        m = re.search(
            rf"NETO\s*\$?\s*({monto})\s+"
            rf"DESCUENTOS?\s*\$?\s*({monto})\s+"
            rf"TOTAL\s*\$?\s*({monto})(?![\d.])",
            texto, re.IGNORECASE,
        )
        if m:
            neto = _parse_monto(m.group(1))
            total = _parse_monto(m.group(3))
            parsed.neto = 0
            parsed.exento = neto
            parsed.iva = 0
            parsed.total = total
            return

        # Caso 3: fallback por etiqueta
        def buscar(etiqueta: str) -> Optional[int]:
            m = re.search(
                rf"\b{etiqueta}\s*:?\s*\$?\s*({monto})(?![\d.])",
                texto, re.IGNORECASE,
            )
            return _parse_monto(m.group(1)) if m else None

        parsed.neto = buscar(r"Neto")
        parsed.exento = buscar(r"(?:Monto\s+)?Exento")
        parsed.iva = buscar(r"IVA\s*19\s*%?")
        parsed.total = buscar(r"TOTAL")

        # Si el tipo es exento y no hay IVA, asignar 0
        if parsed.tipo_documento == "FACTURA_EXENTA_ELECTRONICA":
            parsed.iva = parsed.iva or 0
            # El rótulo NETO de esta plantilla representa el monto exento.
            # Guardarlo como base afecta duplicaría el importe al validar.
            if parsed.exento is None and parsed.neto is not None:
                parsed.exento = parsed.neto
            if parsed.exento is not None:
                parsed.neto = 0

    # ---------- Detalles ----------
    def _extraer_detalles(self, texto: str, parsed: ParsedFactura) -> None:
        entero = r"(?:\d{1,3}(?:[. \t]\d{3})+|\d+)"
        espacio = r"[ \t]*"
        patron = re.compile(
            rf"^(LOCAL[ \t]*[\d\-]+|Rol[ \t]*[\d\-]+|GGCC|(?-i:[A-Z][A-Z0-9_-]*)(?=[ \t])){espacio}"
            rf"([^\n]+?){espacio}(\d+(?:[.,]\d{{1,3}})?){espacio}"
            rf"([A-Z]{{2,4}}){espacio}\$?{espacio}"
            rf"({entero}(?:,\d{{2}})?){espacio}\$?{espacio}"
            rf"({entero})[ \t]*$",
            re.IGNORECASE | re.MULTILINE,
        )
        for m in patron.finditer(texto):
            precio = re.sub(r"[. \t]", "", m.group(5)).replace(",", ".")
            parsed.detalles.append(ParsedDetalle(
                codigo=m.group(1).strip(),
                descripcion=re.sub(r"\s+", " ", m.group(2)).strip(),
                cantidad=float(m.group(3).replace(",", ".")),
                unidad=m.group(4).strip(),
                precio_unitario=float(precio),
                total_linea=_parse_monto(m.group(6)),
            ))
