from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class VersionedJWTAuthentication(JWTAuthentication):
    """Reject access tokens issued before the user's last password reset."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get("tv", 0) != user.token_version:
            raise InvalidToken("Token is no longer valid. Please log in again.")
        return user
