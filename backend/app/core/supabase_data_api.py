"""Cliente HTTP del backend para la Data API de Supabase."""
import json
import os
import re
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _SinRedirecciones(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ErrorDataAPI(Exception):
    def __init__(self, estado, codigo=None):
        self.estado = estado
        self.codigo = codigo
        detalle = f", {codigo}" if codigo else ""
        mensaje = f"HTTP {estado}{detalle}" if estado else "sin respuesta"
        super().__init__(f"Error de Supabase ({mensaje}).")


class SupabaseDataAPI:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.clave = os.getenv("SUPABASE_SECRET_KEY", "")
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", self.url):
            raise ValueError("Configura SUPABASE_URL con la URL HTTPS del proyecto.")
        if not self.clave.startswith("sb_secret_"):
            raise ValueError("Configura SUPABASE_SECRET_KEY con la clave secreta del backend.")
        self.http = build_opener(_SinRedirecciones())

    def importar_sqlite(self, filas):
        try:
            return self.rpc("importar_sqlite", {"p_filas": filas})
        except ErrorDataAPI as error:
            if error.codigo == "PGRST106":
                raise ValueError("Agrega inmobiliaria a los esquemas expuestos de la Data API.") from None
            if error.codigo == "PGRST202":
                raise ValueError("Ejecuta data_api.sql en el SQL Editor de Supabase.") from None
            if error.codigo == "23505":
                raise ValueError("Ya hay datos en el esquema de destino o hay filas duplicadas.") from None
            raise ValueError(str(error)) from None

    def rpc(self, nombre, parametros):
        cuerpo = json.dumps(parametros, ensure_ascii=False, allow_nan=False).encode("utf-8")
        solicitud = Request(
            self.url + "/rest/v1/rpc/" + nombre,
            data=cuerpo,
            headers={
                "apikey": self.clave,
                "Content-Type": "application/json",
                "Content-Profile": "inmobiliaria",
            },
        )
        try:
            with self.http.open(solicitud, timeout=60) as respuesta:
                return json.load(respuesta)
        except HTTPError as error:
            try:
                respuesta = json.load(error)
            except ValueError:
                respuesta = {}
            codigo = respuesta.get("code") if isinstance(respuesta, dict) else None
            raise ErrorDataAPI(error.code, codigo) from None
        except (OSError, ValueError):
            raise ErrorDataAPI(None) from None
