from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """
    For endpoints that anonymous visitors may call. A valid token identifies the
    viewer; a missing, expired or invalid token simply means "visitor", so a
    stale token kept by the browser cannot break a public profile page.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:  # InvalidToken is a subclass
            return None
