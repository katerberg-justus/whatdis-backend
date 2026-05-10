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
    from api.resources.battles import (
        BattleListResource,
        BattleResource,
        BattleAcceptResource,
        BattleGuessListResource,
    )
    from api.resources.challenge_packs import (
        ChallengePackListResource,
        ChallengePackResource,
        ChallengeListResource,
        ChallengeResource,
        PackAccessResource,
    )
    from api.resources.daily_challenges import (
        DailyChallengeListResource,
        DailyChallengeResource,
        DailyChallengeByDateResource,
    )

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

    # Battles
    rest_api.add_resource(BattleListResource,      "/battles")
    rest_api.add_resource(BattleResource,          "/battles/<string:battle_id>")
    rest_api.add_resource(BattleAcceptResource,    "/battles/<string:battle_id>/accept")
    rest_api.add_resource(BattleGuessListResource, "/battles/<string:battle_id>/guesses")

    # Challenge packs
    rest_api.add_resource(ChallengePackListResource, "/challenge-packs")
    rest_api.add_resource(ChallengePackResource,     "/challenge-packs/<string:pack_id>")
    rest_api.add_resource(ChallengeListResource,     "/challenge-packs/<string:pack_id>/challenges")
    rest_api.add_resource(ChallengeResource,         "/challenge-packs/<string:pack_id>/challenges/<string:challenge_id>")
    rest_api.add_resource(PackAccessResource,        "/challenge-packs/<string:pack_id>/access")

    # Daily challenges
    rest_api.add_resource(DailyChallengeListResource,   "/daily")
    rest_api.add_resource(DailyChallengeByDateResource, "/daily/<string:date_str>")
    rest_api.add_resource(DailyChallengeResource,       "/daily/id/<string:daily_id>")
