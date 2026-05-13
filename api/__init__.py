from flask import Flask, request as flask_request
from flask_restful import Api
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)
cors = CORS()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)

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
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 2592000
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_HOST"] = os.environ.get("REDIS_HOST", "localhost")
    app.config["CACHE_REDIS_PORT"] = int(os.environ.get("REDIS_PORT", 6379))
    app.config["CACHE_REDIS_DB"] = int(os.environ.get("REDIS_DB", 0))
    app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379/1"
    )

    if config:
        app.config.update(config)

    _origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")]
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
    cache.init_app(app)
    limiter.init_app(app)

    from api import models as _models  # noqa: F401 — registers models with SQLAlchemy metadata

    migrate.init_app(app, db)

    rest_api = Api(app, prefix="/api/v1")
    root_api = Api(app)

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
