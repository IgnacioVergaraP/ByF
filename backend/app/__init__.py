"""Application Factory del backend."""
from hmac import compare_digest

from flask import Flask, jsonify, request
from flask_cors import CORS

from app.config import get_config
from app.core.database import init_db
from app.core.errors import register_error_handlers


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config())

    if app.config.get("PRIVATE_ACCESS"):
        _require_private_access(app)
    else:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Manejo centralizado de errores
    register_error_handlers(app)

    # Base de datos
    init_db(app)

    # Health global
    @app.route("/api/health", methods=["GET"])
    def api_health():
        return jsonify({
            "status": "ok",
            "service": "plataforma-inmobiliaria-backend",
            "version": "0.2.0"
        }), 200

    # Blueprints modulares
    from app.modules.conciliacion.routes import bp as conciliacion_bp
    app.register_blueprint(conciliacion_bp, url_prefix="/api/conciliacion")
    if app.config["USE_DATA_API"]:
        from app.core.supabase_persistencia import habilitar_supabase

        habilitar_supabase(app, conciliacion_bp.name)

    return app


def _require_private_access(app: Flask) -> None:
    username = app.config["APP_USERNAME"].encode("utf-8")
    password = app.config["APP_PASSWORD"].encode("utf-8")

    @app.before_request
    def authenticate():
        if request.path == "/api/health" and request.method in ("GET", "HEAD"):
            return None
        auth = request.authorization
        if auth is None or auth.type != "basic":
            authorized = False
        else:
            user_matches = compare_digest((auth.username or "").encode("utf-8"), username)
            password_matches = compare_digest((auth.password or "").encode("utf-8"), password)
            authorized = user_matches and password_matches
        if not authorized:
            return (
                jsonify(error="Se requiere iniciar sesión."),
                401,
                {"WWW-Authenticate": 'Basic realm="Plataforma inmobiliaria", charset="UTF-8"'},
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            if request.headers.get("Sec-Fetch-Site") == "cross-site" or (
                origin and origin != f"https://{request.host}"
            ):
                return jsonify(error="Origen de la solicitud no permitido."), 403
        return None

    @app.after_request
    def private_response(response):
        response.cache_control.no_store = True
        return response
