"""Entrada de Vercel para Flask y la compilación de Angular."""
import os
from pathlib import Path
import sys

from flask import send_from_directory

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402

os.environ["FLASK_ENV"] = "production"
os.environ.setdefault("OCR_TESSDATA_DIR", str(BACKEND / "tessdata"))

app = create_app()
WEB = BACKEND / "web" / "browser"


@app.get("/")
@app.get("/conciliacion")
@app.get("/conciliacion/<path:ruta>")
def angular(ruta=None):
    return send_from_directory(WEB, "index.html")


@app.get("/<path:archivo>")
def angular_asset(archivo):
    return send_from_directory(WEB, archivo)
