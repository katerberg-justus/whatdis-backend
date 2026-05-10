def register_resources(rest_api):
    from api.resources.auth import LoginResource, RefreshResource, LogoutResource
    from api.resources.users import UserListResource, UserResource
    from api.resources.me import (
        MeResource,
        FriendListResource,
        FriendRequestListResource,
        FriendResource,
    )
    from api.resources.games import GameListResource, GameResource
    from api.resources.guesses import GuessListResource, GuessResource

    # Auth
    rest_api.add_resource(LoginResource,   "/auth/login")
    rest_api.add_resource(RefreshResource, "/auth/refresh")
    rest_api.add_resource(LogoutResource,  "/auth/logout")

    # Self
    rest_api.add_resource(MeResource,                "/me")
    rest_api.add_resource(FriendListResource,        "/me/friends")
    rest_api.add_resource(FriendRequestListResource, "/me/friends/requests")
    rest_api.add_resource(FriendResource,            "/me/friends/<string:friendship_id>")

    # Users (lookup only — no list)
    rest_api.add_resource(UserListResource, "/users")
    rest_api.add_resource(UserResource,     "/users/<string:user_id>")

    # Games
    rest_api.add_resource(GameListResource, "/games")
    rest_api.add_resource(GameResource,     "/games/<string:game_id>")

    # Guesses (nested under game)
    rest_api.add_resource(GuessListResource, "/games/<string:game_id>/guesses")
    rest_api.add_resource(GuessResource,     "/games/<string:game_id>/guesses/<string:guess_id>")
