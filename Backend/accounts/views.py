from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from .models import OTPPurpose
from .serializers import (
    EmailOnlySerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyEmailSerializer,
    VerifyResetOTPSerializer,
)

User = get_user_model()


class PublicAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class OTPView(PublicAuthView):
    throttle_scope = "otp"


def _get_user_by_email(email):
    return User.objects.filter(email__iexact=email.strip()).first()


class RegisterView(PublicAuthView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"message": "Account created. A 6-digit verification code was sent to your email.",
             "email": user.email},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(OTPView):
    def post(self, request):
        s = VerifyEmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _get_user_by_email(s.validated_data["email"])
        if user is None:
            raise ValidationError({"otp": [services.GENERIC_OTP_ERROR]})
        if user.is_email_verified:
            return Response({"message": "Email is already verified. You can log in."})
        services.verify_otp(user, OTPPurpose.EMAIL_VERIFICATION, s.validated_data["otp"])
        user.is_active = True
        user.is_email_verified = True
        user.save(update_fields=["is_active", "is_email_verified"])
        return Response({"message": "Email verified successfully. You can now log in."})


class ResendOTPView(OTPView):
    def post(self, request):
        s = EmailOnlySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _get_user_by_email(s.validated_data["email"])
        if user is not None and not user.is_email_verified:
            services.issue_otp(user, OTPPurpose.EMAIL_VERIFICATION)
        # Same response either way: do not reveal which emails are registered.
        return Response({"message": "If this account is awaiting verification, a new code has been sent."})


class LoginView(PublicAuthView):
    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        identifier = s.validated_data["identifier"].strip()
        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()

        if user is None or not user.check_password(s.validated_data["password"]):
            return Response({"detail": "Invalid email/username or password."},
                            status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_email_verified:
            return Response(
                {"detail": "Email not verified. Please verify your email with the OTP we sent you.",
                 "code": "email_not_verified", "email": user.email},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.is_active:
            return Response({"detail": "This account has been disabled."}, status=status.HTTP_403_FORBIDDEN)

        return Response({**services.tokens_for_user(user), "user": UserSerializer(user).data})


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = LogoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            token = RefreshToken(s.validated_data["refresh"])
            if token.get("user_id") != str(request.user.pk) and token.get("user_id") != request.user.pk:
                raise TokenError("Token does not belong to this user.")
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Logged out successfully."})


class ForgotPasswordView(OTPView):
    def post(self, request):
        s = EmailOnlySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _get_user_by_email(s.validated_data["email"])
        if user is not None and user.is_active and user.is_email_verified:
            services.issue_otp(user, OTPPurpose.PASSWORD_RESET)
        return Response({"message": "If an account exists for this email, a reset code has been sent."})


class VerifyResetOTPView(OTPView):
    def post(self, request):
        s = VerifyResetOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _get_user_by_email(s.validated_data["email"])
        if user is None:
            raise ValidationError({"otp": [services.GENERIC_OTP_ERROR]})
        token = services.verify_reset_otp_and_issue_token(user, s.validated_data["otp"])
        return Response({
            "message": "Code verified. You may now set a new password.",
            "reset_token": token,
            "expires_in": services.settings.RESET_TOKEN_EXPIRY_SECONDS,
        })


class ResetPasswordView(OTPView):
    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _get_user_by_email(s.validated_data["email"])
        if user is None:
            raise ValidationError({"reset_token": ["Invalid or expired reset authorization."]})

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(s.validated_data["new_password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)})

        with transaction.atomic():
            services.consume_reset_token(user, s.validated_data["reset_token"])
            user.set_password(s.validated_data["new_password"])
            user.save(update_fields=["password"])
            services.revoke_all_sessions(user)
        return Response({"message": "Password updated. Please log in with your new password."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
