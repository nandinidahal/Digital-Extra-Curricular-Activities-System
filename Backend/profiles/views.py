from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response

from . import services
from .authentication import OptionalJWTAuthentication
from .exceptions import ProfileNotFound
from .models import Profile
from .permissions import CanViewProfile, get_viewer_access
from .serializers import (
    ImageUploadSerializer,
    OwnProfileSerializer,
    PrivacySerializer,
    ProfileUpdateSerializer,
    ProfileViewSerializer,
)
from .throttles import ProfileUploadThrottle


def _own_payload(profile, request):
    return {"profile": OwnProfileSerializer(profile, context={"request": request}).data}


class OwnProfileView(APIView):
    """
    GET   /api/profiles/me/  -> own complete profile (created on first access if missing)
    PATCH /api/profiles/me/  -> partial update of the profile information
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        profile = services.get_or_create_profile(request.user)
        return success_response(_own_payload(profile, request))

    def patch(self, request):
        profile = services.get_or_create_profile(request.user)
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = services.update_profile(profile, serializer.validated_data)
        return success_response(_own_payload(profile, request), "Profile updated successfully.")


class OwnPrivacyView(APIView):
    """PATCH /api/profiles/me/privacy/ -> visibility and field-level privacy."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request):
        profile = services.get_or_create_profile(request.user)
        serializer = PrivacySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = services.update_privacy(profile, serializer.validated_data)
        return success_response(
            _own_payload(profile, request), "Privacy settings updated successfully."
        )


class _OwnImageView(APIView):
    """Shared by profile picture and cover photo. Upload field name is `image`."""

    field_name = None
    label = ""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ProfileUploadThrottle]

    def post(self, request):
        services.check_content_length(request, self.field_name)  # before the body is parsed
        serializer = ImageUploadSerializer(
            data=request.data, context={"field_name": self.field_name}
        )
        serializer.is_valid(raise_exception=True)
        profile = services.get_or_create_profile(request.user)
        profile = services.set_profile_image(
            profile,
            self.field_name,
            serializer.validated_data["image"],
            serializer.validated_data["image_format"],
        )
        return success_response(_own_payload(profile, request), f"{self.label} updated successfully.")

    def delete(self, request):
        profile = services.get_or_create_profile(request.user)
        profile = services.remove_profile_image(profile, self.field_name)
        return success_response(_own_payload(profile, request), f"{self.label} removed.")


class OwnPictureView(_OwnImageView):
    """POST / DELETE /api/profiles/me/picture/"""

    field_name = "profile_picture"
    label = "Profile picture"


class OwnCoverView(_OwnImageView):
    """POST / DELETE /api/profiles/me/cover/"""

    field_name = "cover_photo"
    label = "Cover photo"


class ProfileDetailView(APIView):
    """
    GET /api/profiles/<user_id>/

    Works for visitors and logged-in users. A bad/expired token is treated as
    "visitor" (see OptionalJWTAuthentication). Rules live in CanViewProfile.
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny, CanViewProfile]

    def get(self, request, user_id):
        profile = Profile.objects.select_related("user").filter(user_id=user_id).first()
        if profile is None:
            raise ProfileNotFound()
        self.check_object_permissions(request, profile)

        access = get_viewer_access(request.user, profile)
        context = {"request": request, "access": access}
        if access == "owner":
            data = OwnProfileSerializer(profile, context=context).data
        else:
            data = ProfileViewSerializer(profile, context=context).data
        return success_response({"profile": data})
