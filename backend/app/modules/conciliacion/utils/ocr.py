"""Lectura OCR con Tesseract local o con su biblioteca en Vercel."""
import io
import os
import re

import pytesseract
from PIL import Image, ImageDraw


def _quitar_lineas_tabla(imagen: Image.Image) -> Image.Image:
    """Borra trazos largos de la grilla para que Tesseract lea sus celdas."""
    limpia = imagen.convert("L")
    mascara = limpia.point(lambda pixel: 0 if pixel < 180 else 255)
    dibujo = ImageDraw.Draw(limpia)
    for vertical, plano in (
        (False, mascara),
        (True, mascara.transpose(Image.Transpose.TRANSPOSE)),
    ):
        ancho, alto = plano.size
        minimo = max(80, int(ancho * 0.08))
        patron = re.compile(b"\x00{" + str(minimo).encode() + b",}")
        pixeles = plano.tobytes()
        for y in range(alto):
            for tramo in patron.finditer(pixeles[y * ancho:(y + 1) * ancho]):
                if vertical:
                    rect = (y - 1, tramo.start(), y + 1, tramo.end() - 1)
                else:
                    rect = (tramo.start(), y - 1, tramo.end() - 1, y + 1)
                dibujo.rectangle(rect, fill=255)
    return limpia


def ocr_png(png_bytes: bytes, idioma: str = "spa+eng", tablas: bool = False) -> str:
    """Ejecuta OCR sobre una imagen PNG y devuelve el texto."""
    try:
        imagen = Image.open(io.BytesIO(png_bytes))
        if tablas:
            imagen = _quitar_lineas_tabla(imagen)
        tessdata = os.getenv("OCR_TESSDATA_DIR")
        if not tessdata:
            config = "--psm 6" if tablas else ""
            return pytesseract.image_to_string(imagen, lang=idioma, config=config) or ""

        from tesserocr import PSM, PyTessBaseAPI

        modo = PSM.SINGLE_BLOCK if tablas else PSM.AUTO
        with PyTessBaseAPI(path=tessdata, lang=idioma, psm=modo) as ocr:
            ocr.SetImage(imagen)
            ocr.SetSourceResolution(round(imagen.info.get("dpi", (300, 300))[1]))
            return ocr.GetUTF8Text() or ""
    except Exception:
        return ""


def tesseract_disponible() -> bool:
    try:
        tessdata = os.getenv("OCR_TESSDATA_DIR")
        if tessdata:
            from tesserocr import get_languages

            _, idiomas = get_languages(tessdata)
            return {"spa", "eng"}.issubset(idiomas)
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
