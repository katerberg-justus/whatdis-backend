from flask import Flask, request as flask_request
from flask_restful import Api as RestfulApi
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cache = Cache()
cors = CORS()


def rate_limit_identity() -> str:
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return f"user:{user_id}"
    except Exception:
        pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=rate_limit_identity)


def _proxy_fix_count(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _apply_proxy_fix(app: Flask) -> None:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=_proxy_fix_count("PROXY_FIX_X_FOR", 1),
        x_proto=_proxy_fix_count("PROXY_FIX_X_PROTO", 1),
        x_host=_proxy_fix_count("PROXY_FIX_X_HOST", 1),
        x_port=_proxy_fix_count("PROXY_FIX_X_PORT", 0),
        x_prefix=_proxy_fix_count("PROXY_FIX_X_PREFIX", 0),
    )


class Api(RestfulApi):
    def handle_error(self, error):
        error_config = self.errors.get(type(error).__name__)
        if error_config and error_config.get("status", 500) < 500:
            data = {"message": "Internal Server Error", **error_config}
            response = self.make_response(data, error_config["status"])
            if error_config["status"] == 401:
                return self.unauthorized(response)
            return response

        return super().handle_error(error)


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    _apply_proxy_fix(app)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    db_host = "localhost" if os.environ.get("FLASK_ENV") == "development" else os.environ['DB_HOST']
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mariadb+mariadbconnector://"
        f"{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{db_host}:{os.environ.get('DB_PORT', 3306)}"
        f"/{os.environ['DB_NAME']}"
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = int(
        os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 3600)
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = int(
        os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", 2592000)
    )
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
    app.config["JWT_COOKIE_SAMESITE"] = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")
    app.config["JWT_SESSION_COOKIE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"
    app.config["JWT_REFRESH_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"
    app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
    app.config["JWT_REFRESH_COOKIE_PATH"] = "/auth/refresh"
    app.config["JWT_ACCESS_CSRF_COOKIE_PATH"] = "/"
    app.config["JWT_REFRESH_CSRF_COOKIE_PATH"] = "/"
    app.config["JWT_ACCESS_CSRF_COOKIE_NAME"] = "csrf_access_token"
    app.config["JWT_REFRESH_CSRF_COOKIE_NAME"] = "csrf_refresh_token"
    app.config["CACHE_TYPE"] = "RedisCache"
    default_redis_host = "localhost" if os.environ.get("FLASK_ENV") == "development" else "redis"
    redis_host = os.environ.get("REDIS_HOST", default_redis_host)
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    app.config["CACHE_REDIS_HOST"] = redis_host
    app.config["CACHE_REDIS_PORT"] = redis_port
    app.config["CACHE_REDIS_DB"] = int(os.environ.get("REDIS_DB", 0))
    app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
        "RATELIMIT_STORAGE_URI", f"redis://{redis_host}:{redis_port}/1"
    )

    if config:
        app.config.update(config)

    default_cors_origins = (
        "http://localhost:3000,http://localhost:5173"
        if os.environ.get("FLASK_ENV") == "development"
        else "https://app.whatdis.nl,https://whatdis.nl"
    )
    _origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", default_cors_origins).split(",")
        if origin.strip()
    ]
    cors.init_app(app,
        origins=_origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "X-CSRF-TOKEN"],
    )

    # Preflight requests must never reach JWT or rate-limit middleware.
    @app.before_request
    def _handle_options():
        if flask_request.method == "OPTIONS":
            return {}, 200

    db.init_app(app)
    jwt.init_app(app)

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return {"msg": reason}, 401

    @jwt.expired_token_loader
    def _expired_token(jwt_header, jwt_payload):
        return {"msg": "Token has expired"}, 401

    @jwt.unauthorized_loader
    def _missing_token(reason):
        return {"msg": reason}, 401

    @app.errorhandler(CSRFError)
    def _csrf_error(error):
        return {"msg": str(error)}, 401

    cache.init_app(app)
    limiter.init_app(app)

    from api import models as _models  # noqa: F401 — registers models with SQLAlchemy metadata

    migrate.init_app(app, db)

    api_errors = {
        "CSRFError": {
            "message": "Missing or invalid CSRF token",
            "status": 401,
        },
        "NoAuthorizationError": {
            "message": "Missing or invalid authorization",
            "status": 401,
        },
        "ExpiredSignatureError": {
            "message": "Token has expired",
            "status": 401,
        }
    }
    rest_api = Api(app, prefix="/api/v1", errors=api_errors)
    root_api = Api(app, errors=api_errors)

    from api.resources import register_resources, register_root_resources
    register_resources(rest_api)
    register_root_resources(root_api)

    from api.common.errors import register_error_handlers
    register_error_handlers(app)

    @app.cli.command("purge-guests")
    def purge_guests():
        """Delete guest accounts older than 30 days that were never claimed."""
        import click
        from datetime import timedelta
        from api.models.user import User
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = db.session.execute(
            db.delete(User).where(User.is_guest == True, User.created_at < cutoff)
        )
        db.session.commit()
        click.echo(f"Purged {result.rowcount} guest account(s).")

    return app
