def register_root_resources(api):
    from api.resources.auth import LoginResource, RefreshResource, LogoutResource, GuestLoginResource
    from api.resources.subscriptions import StripeWebhookResource

    api.add_resource(LoginResource,      "/auth/login")
    api.add_resource(GuestLoginResource, "/auth/guest")
    api.add_resource(RefreshResource,    "/auth/refresh")
    api.add_resource(LogoutResource,     "/auth/logout")

    api.add_resource(StripeWebhookResource, "/webhooks/stripe")


def register_resources(api):
    from api.resources.users import UserListResource, UserResource, UserAvailabilityResource
    from api.resources.me import (
        MeResource,
        ClaimResource,
        FriendListResource,
        FriendRequestListResource,
        FriendResource,
    )
    from api.resources.games import GameListResource, GameResource
    from api.resources.guesses import GuessListResource, GuessResource, HintListResource
    from api.resources.battles import (
        BattleListResource,
        BattleChallengeListResource,
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
    from api.resources.subscriptions import (
        SubscriptionPlanListResource,
        CheckoutSessionResource,
        NrgBoosterListResource,
        NrgBoosterCheckoutSessionResource,
        MeSubscriptionResource,
        StripeWebhookResource,
    )
    from api.resources.achievements import AchievementListResource, MeAchievementListResource
    from api.resources.push_subscriptions import (
        PushSubscriptionListResource,
        PushSubscriptionResource,
        PushVapidPublicKeyResource,
    )
    from api.resources.analytics import AnalyticsResource
    from api.resources.challenge_ratings import ChallengeRatingResource
    from api.resources.custom_challenges import (
        CustomChallengeListResource,
        MyCustomChallengeListResource,
        MyCustomChallengeResource,
        CustomChallengeRedeemResource,
        CustomChallengeResource,
    )

    # Self
    api.add_resource(MeResource,                "/me")
    api.add_resource(ClaimResource,             "/me/claim")
    api.add_resource(FriendListResource,        "/me/friends")
    api.add_resource(FriendRequestListResource, "/me/friends/requests")
    api.add_resource(FriendResource,            "/me/friends/<string:friendship_id>")
    api.add_resource(MeSubscriptionResource,    "/me/subscription")
    api.add_resource(MeAchievementListResource, "/me/achievements")
    api.add_resource(PushSubscriptionListResource, "/me/push-subscriptions")
    api.add_resource(PushSubscriptionResource,     "/me/push-subscriptions/<string:subscription_id>")
    api.add_resource(PushVapidPublicKeyResource,   "/push/vapid-public-key")

    # Users
    api.add_resource(UserListResource,         "/users")
    api.add_resource(UserAvailabilityResource, "/users/check")
    api.add_resource(UserResource,             "/users/<string:user_id>")

    # Games
    api.add_resource(GameListResource, "/games")
    api.add_resource(GameResource,     "/games/<string:game_id>")

    # Guesses (nested under game)
    api.add_resource(GuessListResource, "/games/<string:game_id>/guesses")
    api.add_resource(GuessResource,     "/games/<string:game_id>/guesses/<string:guess_id>")
    api.add_resource(HintListResource,  "/games/<string:game_id>/hints")

    # Battles
    api.add_resource(BattleListResource,      "/battles")
    api.add_resource(BattleChallengeListResource, "/battles/challenge-packs/<string:pack_id>/challenges")
    api.add_resource(BattleResource,          "/battles/<string:battle_id>")
    api.add_resource(BattleAcceptResource,    "/battles/<string:battle_id>/accept")
    api.add_resource(BattleGuessListResource, "/battles/<string:battle_id>/guesses")

    # Challenge packs
    api.add_resource(ChallengePackListResource, "/challenge-packs")
    api.add_resource(ChallengePackResource,     "/challenge-packs/<string:pack_id>")
    api.add_resource(ChallengeListResource,     "/challenge-packs/<string:pack_id>/challenges")
    api.add_resource(ChallengeResource,         "/challenge-packs/<string:pack_id>/challenges/<string:challenge_id>")
    api.add_resource(PackAccessResource,        "/challenge-packs/<string:pack_id>/access")
    api.add_resource(ChallengeRatingResource,    "/challenges/<string:challenge_id>/rating")

    # Daily challenges
    api.add_resource(DailyChallengeListResource,   "/daily")
    api.add_resource(DailyChallengeByDateResource, "/daily/<string:date_str>")
    api.add_resource(DailyChallengeResource,       "/daily/id/<string:daily_id>")

    # Subscriptions
    api.add_resource(SubscriptionPlanListResource, "/subscriptions")
    api.add_resource(CheckoutSessionResource,      "/subscriptions/checkout")
    api.add_resource(NrgBoosterListResource,       "/nrg-boosters")
    api.add_resource(NrgBoosterCheckoutSessionResource, "/nrg-boosters/checkout")
    api.add_resource(StripeWebhookResource,        "/webhooks/stripe", endpoint="stripe_webhook_v1")

    # Achievements
    api.add_resource(AchievementListResource, "/achievements")

    # Admin analytics
    api.add_resource(AnalyticsResource, "/analytics")

    # Custom challenges (user-authored, share-link gated)
    api.add_resource(MyCustomChallengeListResource, "/me/custom-challenges")
    api.add_resource(MyCustomChallengeResource,     "/me/custom-challenges/<string:challenge_id>")
    api.add_resource(CustomChallengeListResource,   "/custom-challenges")
    api.add_resource(CustomChallengeRedeemResource, "/custom-challenges/redeem")
    api.add_resource(CustomChallengeResource,       "/custom-challenges/<string:challenge_id>")
