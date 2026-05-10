from flask import Flask
from flask_restful import Api
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mariadb+mariadbconnector://"
        f"{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', 3306)}"
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
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_HOST"] = os.environ.get("REDIS_HOST", "localhost")
    app.config["CACHE_REDIS_PORT"] = int(os.environ.get("REDIS_PORT", 6379))
    app.config["CACHE_REDIS_DB"] = int(os.environ.get("REDIS_DB", 0))
    app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379/1"
    )

    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)

    from api import models as _models  # noqa: F401 — registers models with SQLAlchemy metadata

    migrate.init_app(app, db)

    rest_api = Api(app)

    from api.resources import register_resources
    register_resources(rest_api)

    from api.common.errors import register_error_handlers
    register_error_handlers(app)

    return app
