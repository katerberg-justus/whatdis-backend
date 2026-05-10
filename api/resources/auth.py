from flask import request
from flask_restful import Resource
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from api import limiter


class LoginResource(Resource):
    decorators = [limiter.limit("10 per minute")]

    def post(self):
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return {"error": "username and password required"}, 400

        # TODO: look up user from db and verify password hash
        # user = User.query.filter_by(username=username).first()
        # if not user or not user.check_password(password):
        #     return {"error": "Invalid credentials"}, 401

        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)
        return {"access_token": access_token, "refresh_token": refresh_token}, 200


class RefreshResource(Resource):
    decorators = [jwt_required(refresh=True), limiter.limit("20 per minute")]

    def post(self):
        identity = get_jwt_identity()
        access_token = create_access_token(identity=identity)
        return {"access_token": access_token}, 200


class LogoutResource(Resource):
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def delete(self):
        # TODO: add jti to a Redis blocklist for token revocation
        return {"message": "Logged out"}, 200
