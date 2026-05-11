from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.models.user import User
from api.common.base_model import utc_isoformat


class UserListResource(Resource):
    """POST /users — public registration."""

    def post(self):
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("name", "email", "password") if not data.get(f)]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400

        user = User(name=data["name"], email=data["email"])
        user.set_password(data["password"])
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Username or email already taken"}, 409

        return _serialize(user), 201


class UserResource(Resource):
    """GET /users/<id> — look up any user by id (friends need this)."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, user_id):
        user = db.get_or_404(User, user_id)
        return _serialize(user), 200


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "created_at": utc_isoformat(u.created_at),
        "updated_at": utc_isoformat(u.updated_at),
    }
