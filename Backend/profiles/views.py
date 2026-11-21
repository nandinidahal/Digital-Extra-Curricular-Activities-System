from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.views import PublicAuthView
from achievements.serializers import OwnerAchievementSerializer, PublicAchievementSerializer
from announcements.pagination import StandardPagination

from . import selectors, services
from .permissions import CanViewProfile
from .serializers import (
    AccountSerializer,
    DeactivateAccountSerializer,
    EmailChangeConfirmSerializer,
    EmailChangeRequestSerializer,
    OwnerProfileSerializer,
    PrivacySettingsSerializer,
    PrivacySettingsUpdateSerializer,
    ProfilePictureUploadSerializer,
    ProfileUpdateSerializer,
    PublicProfileSerializer,
    ReactivateSerializer,
)

User = get_user_model()
PARSERS = [MultiPartParser, FormParser, JSONParser]


def _ctx(request):
    return {"request": request}


def _owner_data(request, profile):
    return OwnerProfileSerializer(profile, context=_ctx(request)).data


# --------------------------------------------------------------------------- own profile
class ProfileMeView(APIView):
    """GET /api/profile/me/: the complete profile, including all of the user's own achievements."""

    def get(self, request):
        profile = selectors.ensure_profile(request.user)
        data = _owner_data(request, profile)
        data["achievement_counts"] = selectors.achievement_counts(request.user)
        recent = selectors.own_achievements(request.user)[: selectors.RECENT_ACHIEVEMENTS]
        data["achievements"] = OwnerAchievementSerializer(recent, many=True, context=_ctx(request)).data
        return Response(data)


class ProfileUpdateView(APIView):
    """PUT/PATCH /api/profile/me/update/: always updates the authenticated user, never another."""

    parser_classes = PARSERS

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        profile = selectors.ensure_profile(request.user)
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=partial, context=_ctx(request))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile.refresh_from_db()
        return Response(_owner_data(request, profile))


class ProfilePictureUploadView(APIView):
    """POST /api/profile/me/upload-picture/ (multipart, field ``profile_picture``). Replaces any existing one."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ProfilePictureUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = selectors.ensure_profile(request.user)
        had_picture = bool(profile.profile_picture)
        services.set_profile_picture(profile, serializer.validated_data["profile_picture"])
        return Response(
            {"message": "Profile picture updated." if had_picture else "Profile picture uploaded.",
             "profile_picture_url": _owner_data(request, profile)["profile_picture_url"]},
            status=status.HTTP_200_OK if had_picture else status.HTTP_201_CREATED,
        )


class ProfilePictureRemoveView(APIView):
    """DELETE /api/profile/me/remove-picture/"""

    def delete(self, request):
        profile = selectors.ensure_profile(request.user)
        if not services.remove_profile_picture(profile):
            return Response({"detail": "You do not have a profile picture."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "Profile picture removed.", "profile_picture_url": None})


# --------------------------------------------------------------------------- settings
class PrivacySettingsView(APIView):
    """GET/PATCH /api/profile/me/settings/

    Profile, e-mail, date-of-birth and bio visibility. Visibility of each *achievement* is
    separate and stays with the achievements API (PATCH /api/achievements/<id>/); the counts
    below show how many are public/private right now.
    """

    def get(self, request):
        profile = selectors.ensure_profile(request.user)
        data = PrivacySettingsSerializer(profile).data
        data["achievements"] = {
            **selectors.achievement_counts(request.user),
            "note": "Each achievement has its own visibility; manage it through the achievements API.",
        }
        return Response(data)

    def patch(self, request):
        profile = selectors.ensure_profile(request.user)
        serializer = PrivacySettingsUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PrivacySettingsSerializer(profile).data)


class AccountView(APIView):
    """GET /api/profile/me/account/: account information and status."""

    def get(self, request):
        profile = selectors.ensure_profile(request.user)
        return Response(AccountSerializer(profile).data)


class EmailChangeRequestView(APIView):
    """POST /api/profile/me/email/change/: sends a 6-digit code to the NEW address."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        s = EmailChangeRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        new_email = services.request_email_change(
            request.user, s.validated_data["new_email"], s.validated_data["current_password"]
        )
        return Response({"message": "A 6-digit confirmation code was sent to the new email address.",
                         "new_email": new_email})


class EmailChangeConfirmView(APIView):
    """POST /api/profile/me/email/confirm/"""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        s = EmailChangeConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = services.confirm_email_change(request.user, s.validated_data["otp"])
        return Response({"message": "Email address updated.", "email": user.email})


class DeactivateAccountView(APIView):
    """POST /api/profile/me/deactivate/: disables the account (reversible). Nothing is deleted."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        s = DeactivateAccountSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not request.user.check_password(s.validated_data["current_password"]):
            return Response({"current_password": ["Current password is incorrect."]},
                            status=status.HTTP_400_BAD_REQUEST)
        profile = selectors.ensure_profile(request.user)
        services.deactivate_account(request.user, profile)
        return Response({"message": "Your account has been deactivated. Log in again with POST "
                                    "/api/profile/reactivate/ to restore it."})


class ReactivateAccountView(PublicAuthView):
    """POST /api/profile/reactivate/: public (a deactivated user cannot hold a valid token).

    Needs the account's e-mail/username and password. Only accounts that the USER deactivated can
    be reactivated here; accounts disabled by an administrator or never verified cannot.
    """

    def post(self, request):
        s = ReactivateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        identifier = s.validated_data["identifier"].strip()
        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        if user is None or not user.check_password(s.validated_data["password"]):
            return Response({"detail": "Invalid email/username or password."}, status=status.HTTP_401_UNAUTHORIZED)
        if user.is_active:
            return Response({"detail": "This account is already active."}, status=status.HTTP_400_BAD_REQUEST)
        profile = selectors.ensure_profile(user)
        if not user.is_email_verified or profile.deactivated_at is None:
            return Response({"detail": "This account cannot be reactivated. Please contact support."},
                            status=status.HTTP_403_FORBIDDEN)
        services.reactivate_account(user, profile)
        return Response({"message": "Your account has been reactivated. You can now log in."})


class DashboardView(APIView):
    """GET /api/profile/me/dashboard/"""

    def get(self, request):
        profile = selectors.ensure_profile(request.user)
        data = _owner_data(request, profile)
        data["achievement_counts"] = selectors.achievement_counts(request.user)
        return Response(data)


# --------------------------------------------------------------------------- other users
class PublicProfileView(APIView):
    """GET /api/profile/<user_id>/

    Owner: complete profile. Others: 403 if the profile is Private, otherwise only what the
    owner chose to share plus PUBLIC achievements. Unknown or deactivated users are 404.
    """

    permission_classes = [IsAuthenticated, CanViewProfile]

    def get(self, request, user_id):
        profile = selectors.get_active_profile_or_404(user_id)
        self.check_object_permissions(request, profile)  # 403 for a private profile of someone else
        if profile.user_id == request.user.id:
            data = _owner_data(request, profile)
            data["achievement_counts"] = selectors.achievement_counts(request.user)
            recent = selectors.own_achievements(request.user)[: selectors.RECENT_ACHIEVEMENTS]
            data["achievements"] = OwnerAchievementSerializer(recent, many=True, context=_ctx(request)).data
            return Response(data)

        data = PublicProfileSerializer(profile, context=_ctx(request)).data
        public = selectors.public_achievements(profile.user)
        data["public_achievements_count"] = public.count()
        data["achievements"] = PublicAchievementSerializer(
            public[: selectors.RECENT_ACHIEVEMENTS], many=True, context=_ctx(request)
        ).data
        return Response(data)


class ProfileAchievementsView(generics.ListAPIView):
    """GET /api/profile/<user_id>/achievements/ (paginated)

    Same gate as the profile itself. Visitors get PUBLIC achievements only; the owner gets all.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def _profile(self):
        profile = selectors.get_active_profile_or_404(self.kwargs["user_id"])
        self.check_object_permissions(self.request, profile)
        return profile

    def get_permissions(self):
        return [IsAuthenticated(), CanViewProfile()]

    def get_serializer_class(self):
        return OwnerAchievementSerializer if self.kwargs["user_id"] == self.request.user.id else PublicAchievementSerializer

    def get_queryset(self):
        profile = self._profile()
        if profile.user_id == self.request.user.id:
            return selectors.own_achievements(profile.user)
        return selectors.public_achievements(profile.user)
