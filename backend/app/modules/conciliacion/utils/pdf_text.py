"""Extracción de texto y renderizado de páginas desde PDF."""
import io
from typing import Optional

import fitz  # PyMuPDF


MIN_TEXT_LEN = 100


def extraer_texto_paginas(data: bytes) -> list[str]:
    """Devuelve una lista con el texto de cada página del PDF."""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return [page.get_text("text") or "" for page in doc]
    finally:
        doc.close()


def texto_suficiente(texto: str) -> bool:
    """¿Hay texto seleccionable suficiente para parsear sin OCR?"""
    return len((texto or "").strip()) >= MIN_TEXT_LEN


def renderizar_pagina_png(data: bytes, numero_pagina: int, dpi: int = 300) -> Optional[bytes]:
    """Renderiza una página del PDF como PNG para pasarla a OCR."""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        if numero_pagina < 1 or numero_pagina > len(doc):
            return None
        page = doc[numero_pagina - 1]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()


def cantidad_paginas(data: bytes) -> int:
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return len(doc)
    finally:
        doc.close()