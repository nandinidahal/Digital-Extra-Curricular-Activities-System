from django.conf import settings
from django.db import IntegrityError
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from .exceptions import InvalidRefreshToken
from .responses import success_response
from .serializers import (
    AccountTokenRefreshSerializer,
    ChangePasswordSerializer,
    EmailSerializer,
    LoginSerializer,
    LogoutSerializer,
    OTPVerifySerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UpdateAccountSerializer,
    UserSerializer,
)
from .throttles import (
    LoginEmailThrottle,
    LoginIPThrottle,
    OTPRequestEmailBurstThrottle,
    OTPRequestEmailThrottle,
    OTPRequestIPThrottle,
    OTPVerifyThrottle,
    PasswordChangeThrottle,
    PasswordResetThrottle,
    RegisterThrottle,
    TokenRefreshThrottle,
)

GENERIC_OTP_SENT = (
    "If an account exists for this email, a verification code has been sent."
)
GENERIC_RESET_SENT = (
    "If an account exists for this email, a password reset code has been sent."
)


class PublicAPIView(APIView):
    """
    Public endpoint. Authentication is switched off on purpose: otherwise an
    old or expired access token sent by the browser would cause a 401 even
    though the endpoint needs no login.
    """

    authentication_classes = []
    permission_classes = [AllowAny]


# ---------------------------------------------------------------------------
# Registration & email verification
# ---------------------------------------------------------------------------
class RegisterView(PublicAPIView):
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return success_response(
            {
                "user": UserSerializer(user).data,
                "email_verification_required": True,
                "otp_expires_in_minutes": settings.OTP_VALID_MINUTES,
            },
            "Account created. We sent a 6-digit verification code to your email.",
            status.HTTP_201_CREATED,
        )


class VerifyEmailView(PublicAPIView):
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.verify_email_address(
            serializer.validated_data["email"], serializer.validated_data["otp"]
        )
        return success_response(
            {"email_verified": True}, "Email verified successfully. You can now log in."
        )


class ResendOTPView(PublicAPIView):
    throttle_classes = [
        OTPRequestIPThrottle,
        OTPRequestEmailThrottle,
        OTPRequestEmailBurstThrottle,
    ]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_verification_otp(serializer.validated_data["email"])
        return success_response(
            {"otp_expires_in_minutes": settings.OTP_VALID_MINUTES}, GENERIC_OTP_SENT
        )


# ---------------------------------------------------------------------------
# Login / refresh / logout
# ---------------------------------------------------------------------------
class LoginView(PublicAPIView):
    throttle_classes = [LoginIPThrottle, LoginEmailThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = services.login_user(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        return success_response(
            {"user": UserSerializer(user).data, "tokens": tokens}, "Login successful."
        )


class RefreshView(TokenRefreshView):
    """Returns a new access token AND a new refresh token (rotation)."""

    serializer_class = AccountTokenRefreshSerializer
    throttle_classes = [TokenRefreshThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return success_response({"tokens": dict(response.data)}, "Token refreshed.")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            # A user may only log out their own refresh token.
            if str(token.get("user_id")) != str(request.user.pk):
                raise InvalidRefreshToken()
            token.blacklist()
        except TokenError:
            raise InvalidRefreshToken()
        return success_response({}, "Logged out successfully.")


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------
class ForgotPasswordView(PublicAPIView):
    throttle_classes = [
        OTPRequestIPThrottle,
        OTPRequestEmailThrottle,
        OTPRequestEmailBurstThrottle,
    ]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset_otp(serializer.validated_data["email"])
        return success_response(
            {"otp_expires_in_minutes": settings.OTP_VALID_MINUTES}, GENERIC_RESET_SENT
        )


class VerifyResetOTPView(PublicAPIView):
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token = services.verify_password_reset_otp(
            serializer.validated_data["email"], serializer.validated_data["otp"]
        )
        return success_response(
            {
                "reset_token": reset_token,
                "expires_in_minutes": settings.PASSWORD_RESET_TOKEN_MINUTES,
            },
            "Code verified. You can now set a new password.",
        )


class ResetPasswordView(PublicAPIView):
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.complete_password_reset(
            serializer.validated_data["token"], serializer.validated_data["new_password"]
        )
        return success_response({}, "Password reset successfully. You can now log in.")


# ---------------------------------------------------------------------------
# Authenticated account endpoints
# ---------------------------------------------------------------------------
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = services.change_password(
            request.user, serializer.validated_data["new_password"]
        )
        return success_response(
            {"tokens": tokens},
            "Password changed successfully. Other devices have been signed out.",
        )


class MeView(APIView):
    """
    GET   /api/auth/me/  -> the logged-in user's account
    PATCH /api/auth/me/  -> edit basic account information

    Only IsAuthenticated (not IsEmailVerified) on purpose: a user who just
    changed their email must still be able to see their account and the
    "please verify" state.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response({"user": UserSerializer(request.user).data})

    def patch(self, request):
        serializer = UpdateAccountSerializer(
            data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            user, email_changed = services.update_account(request.user, serializer.validated_data)
        except IntegrityError:
            raise drf_serializers.ValidationError(
                {"non_field_errors": ["Those details are already in use."]}
            )
        message = (
            "Account updated. We sent a verification code to your new email address."
            if email_changed
            else "Account updated successfully."
        )
        return success_response(
            {
                "user": UserSerializer(user).data,
                "email_verification_required": email_changed,
            },
            message,
        )
