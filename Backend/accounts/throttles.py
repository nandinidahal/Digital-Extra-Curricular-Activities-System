"""
Rate limits for the sensitive endpoints.

Rates live in settings.AUTH_THROTTLE_RATES. Some throttles are keyed by client
IP, others by the e-mail address in the request body. Keying by e-mail applies
to every address, whether or not an account exists, so it does not reveal
which accounts are real.
"""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class _AuthThrottle(SimpleRateThrottle):
    def get_rate(self):
        # Read at request time so tests can override the settings.
        return settings.AUTH_THROTTLE_RATES[self.scope]


class _IPThrottle(_AuthThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class _EmailThrottle(_AuthThrottle):
    def get_cache_key(self, request, view):
        data = request.data
        email = data.get("email") if hasattr(data, "get") else None
        if not isinstance(email, str) or not email.strip():
            return None  # nothing to key on; validation will reject the request
        return self.cache_format % {"scope": self.scope, "ident": email.strip().lower()}


class _UserThrottle(_AuthThrottle):
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RegisterThrottle(_IPThrottle):
    scope = "register"


class LoginIPThrottle(_IPThrottle):
    scope = "login"


class LoginEmailThrottle(_EmailThrottle):
    scope = "login_email"


class OTPVerifyThrottle(_IPThrottle):
    scope = "otp_verify"


class OTPRequestIPThrottle(_IPThrottle):
    scope = "otp_request_ip"


class OTPRequestEmailThrottle(_EmailThrottle):
    scope = "otp_request_email"


class OTPRequestEmailBurstThrottle(_EmailThrottle):
    scope = "otp_request_email_burst"


class PasswordResetThrottle(_IPThrottle):
    scope = "password_reset"


class TokenRefreshThrottle(_IPThrottle):
    scope = "token_refresh"


class PasswordChangeThrottle(_UserThrottle):
    scope = "password_change"
