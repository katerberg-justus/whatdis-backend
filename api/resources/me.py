from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.models.user import User
from api.models.friendship import Friendship, PENDING, ACCEPTED


def _current_user() -> User:
    user = db.session.get(User, get_jwt_identity())
    if user is None:
        abort(401)
    return user


class MeResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        user = _current_user()
        return _serialize_user(user), 200

    def put(self):
        user = _current_user()
        data = request.get_json(silent=True) or {}
        if "name" in data:
            user.name = data["name"]
        if "email" in data:
            user.email = data["email"]
        if "password" in data:
            user.set_password(data["password"])
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Username or email already taken"}, 409
        return _serialize_user(user), 200

    def delete(self):
        user = _current_user()
        db.session.delete(user)
        db.session.commit()
        return {}, 204


class FriendListResource(Resource):
    """GET /me/friends — accepted friends; POST — send invite by email."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        rows = db.session.execute(
            db.select(Friendship).where(
                Friendship.status == ACCEPTED,
                or_(Friendship.requester_id == uid, Friendship.addressee_id == uid),
            )
        ).scalars().all()
        return [_serialize_friendship(f, uid) for f in rows], 200

    def post(self):
        me = _current_user()
        data = request.get_json(silent=True) or {}
        if not data.get("email"):
            return {"error": "email required"}, 400

        target = db.session.execute(
            db.select(User).where(User.email == data["email"])
        ).scalar_one_or_none()
        if target is None:
            return {"error": "User not found"}, 404
        if target.id == me.id:
            return {"error": "Cannot invite yourself"}, 400

        # reject if any friendship record already exists in either direction
        existing = db.session.execute(
            db.select(Friendship).where(
                or_(
                    (Friendship.requester_id == me.id) & (Friendship.addressee_id == target.id),
                    (Friendship.requester_id == target.id) & (Friendship.addressee_id == me.id),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return {"error": "Friendship already exists or pending"}, 409

        friendship = Friendship(requester_id=me.id, addressee_id=target.id, status=PENDING)
        db.session.add(friendship)
        db.session.commit()
        return _serialize_friendship(friendship, me.id), 201


class FriendRequestListResource(Resource):
    """GET /me/friends/requests — incoming pending invites."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        rows = db.session.execute(
            db.select(Friendship).where(
                Friendship.addressee_id == uid,
                Friendship.status == PENDING,
            )
        ).scalars().all()
        return [_serialize_friendship(f, uid) for f in rows], 200


class FriendResource(Resource):
    """PUT /me/friends/<id> — accept; DELETE — remove or decline."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def put(self, friendship_id):
        uid = get_jwt_identity()
        friendship = db.get_or_404(Friendship, friendship_id)

        if friendship.addressee_id != uid:
            abort(403)
        if friendship.status == ACCEPTED:
            return {"error": "Already accepted"}, 409

        friendship.status = ACCEPTED
        db.session.commit()
        return _serialize_friendship(friendship, uid), 200

    def delete(self, friendship_id):
        uid = get_jwt_identity()
        friendship = db.get_or_404(Friendship, friendship_id)

        if uid not in (friendship.requester_id, friendship.addressee_id):
            abort(403)

        db.session.delete(friendship)
        db.session.commit()
        return {}, 204


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _serialize_friendship(f: Friendship, viewer_id: str) -> dict:
    friend = f.addressee if f.requester_id == viewer_id else f.requester
    return {
        "id": f.id,
        "friend": {"id": friend.id, "name": friend.name, "email": friend.email},
        "status": "pending" if f.status == PENDING else "accepted",
        "direction": "sent" if f.requester_id == viewer_id else "received",
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
