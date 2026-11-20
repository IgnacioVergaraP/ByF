"""Manejo centralizado de errores."""
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        return jsonify({
            "error": e.name,
            "message": e.description,
            "status": e.code
        }), e.code

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception):
        app.logger.exception("Error no controlado: %s", e)
        return jsonify({
            "error": "Internal Server Error",
            "message": "Ocurrió un error inesperado.",
            "status": 500
        }), 500