from flask import request, make_response
from flask_restful import Resource
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from api import db, limiter
from api.models.user import User


class LoginResource(Resource):
    decorators = [limiter.limit("10 per minute")]

    def post(self):
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return {"error": "email (or username) and password required"}, 400

        user = db.session.execute(
            db.select(User).where((User.email == email) | (User.name == email))
        ).scalar_one_or_none()

        if user is None or not user.check_password(password):
            return {"error": "Invalid credentials"}, 401

        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        resp = make_response({"message": "Logged in"}, 200)
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        return resp


class RefreshResource(Resource):
    decorators = [jwt_required(refresh=True), limiter.limit("20 per minute")]

    def post(self):
        access_token = create_access_token(identity=get_jwt_identity())
        resp = make_response({"message": "Token refreshed"}, 200)
        set_access_cookies(resp, access_token)
        return resp


class LogoutResource(Resource):
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def delete(self):
        resp = make_response({"message": "Logged out"}, 200)
        unset_jwt_cookies(resp)
        return resp
