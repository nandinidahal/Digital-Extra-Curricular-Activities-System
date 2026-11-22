"""
API of the Achievements module (/api/achievements/, /api/achievement-categories/).

Read endpoints accept visitors (they see verified PUBLIC achievements only). Writes need a JWT.
Review endpoints need a moderator (admin or coordinator) who is not the owner.
"""
from django.contrib.auth import get_user_model
from django.http import FileResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response
from common.exceptions import ResourceNotFound, check_content_length
from common.pagination import paginate
from common.permissions import IsModerator, ReadAnyWriteAuthenticated, is_authenticated, is_moderator
from common.relationships import is_blocked_between
from common.signing import read_download_token
from profiles.authentication import OptionalJWTAuthentication

from . import services
from .models import Achievement, AchievementCategory
from .serializers import (
    EVIDENCE_TOKEN_KIND,
    AchievementCategorySerializer,
    AchievementFilterSerializer,
    AchievementSerializer,
    AchievementWriteSerializer,
    EvidenceSerializer,
    EvidenceUploadSerializer,
    ResubmitSerializer,
    ReviewHistorySerializer,
    ReviewSerializer,
)
from .throttles import AchievementReviewThrottle, AchievementUploadThrottle, AchievementWriteThrottle


def _filters(request):
    serializer = AchievementFilterSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _detail(request, achievement_id, message="", status_code=status.HTTP_200_OK):
    achievement = services.with_relations(Achievement.objects.filter(pk=achievement_id)).prefetch_related("evidence").get()
    data = AchievementSerializer(achievement, context={"request": request, "include_evidence": True}).data
    return success_response({"achievement": data}, message, status_code)


def _list(request, queryset, params):
    queryset = services.apply_filters(services.with_relations(queryset), params)
    return paginate(request, queryset, AchievementSerializer)


class _Optional(APIView):
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [ReadAnyWriteAuthenticated]


class _Authenticated(APIView):
    permission_classes = [IsAuthenticated]


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
class AchievementListCreateView(_Optional):
    """
    GET  /api/achievements/   verified achievements the viewer may see (filters: category, level ...)
    POST /api/achievements/   create (JSON). Starts as "pending" for review.
    """

    throttle_classes = [AchievementWriteThrottle]

    def get(self, request):
        params = _filters(request)
        params.pop("status", None)
        params.pop("q", None)  # text search is the authenticated /search/ endpoint
        return _list(request, services.visible_achievements(request.user), params)

    def post(self, request):
        serializer = AchievementWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        achievement = services.create_achievement(request.user, serializer.validated_data)
        return _detail(request, achievement.pk, "Achievement submitted for verification.", status.HTTP_201_CREATED)


class MyAchievementsView(_Authenticated):
    """GET /api/achievements/me/?status=pending  -> own achievements, every status and visibility"""

    def get(self, request):
        return _list(request, Achievement.objects.filter(user=request.user), _filters(request))


class UserAchievementsView(_Optional):
    """GET /api/achievements/users/<user_id>/  -> that user's verified achievements the viewer may see"""

    def get(self, request, user_id):
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if user is None or (is_authenticated(request.user) and is_blocked_between(request.user, user)):
            raise ResourceNotFound("This user does not exist.", code="user_not_found")
        params = _filters(request)
        params.pop("status", None)
        return _list(request, services.visible_achievements(request.user).filter(user=user), params)


class FeaturedAchievementsView(_Optional):
    """GET /api/achievements/featured/?user_id=<uuid>"""

    def get(self, request):
        import uuid

        queryset = services.visible_achievements(request.user).filter(is_featured=True)
        user_id = request.query_params.get("user_id")
        if user_id:
            try:
                queryset = queryset.filter(user_id=uuid.UUID(user_id))
            except ValueError:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"user_id": ["Must be a valid UUID."]})
        params = _filters(request)
        params.pop("status", None)
        return _list(request, queryset, params)


class SearchView(_Authenticated):
    """GET /api/achievements/search/?q=robotics&level=national&skill=python"""

    def get(self, request):
        params = _filters(request)
        params.pop("status", None)
        return _list(request, services.visible_achievements(request.user), params)


class PendingReviewView(APIView):
    """GET /api/achievements/pending/  (reviewers) - review queue, oldest first, own excluded"""

    permission_classes = [IsAuthenticated, IsModerator]

    def get(self, request):
        queryset = services.review_queue().exclude(user=request.user)
        status_filter = request.query_params.get("status")
        if status_filter in services.REVIEWABLE_STATUSES:
            queryset = queryset.filter(verification_status=status_filter)
        return paginate(request, queryset, AchievementSerializer)


class StatsView(_Authenticated):
    """
    GET /api/achievements/stats/                 -> the user's own statistics
    GET /api/achievements/stats/?scope=platform  -> platform-wide (reviewers only)
    """

    def get(self, request):
        if request.query_params.get("scope") == "platform":
            if not is_moderator(request.user):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Only reviewers can see platform statistics.")
            queryset = Achievement.objects.filter(user__is_active=True)
            scope = "platform"
        else:
            queryset = Achievement.objects.filter(user=request.user)
            scope = "me"
        return success_response({"scope": scope, "statistics": services.statistics(queryset)})


# ---------------------------------------------------------------------------
# Single achievement
# ---------------------------------------------------------------------------
class AchievementDetailView(_Optional):
    throttle_classes = [AchievementWriteThrottle]

    def get(self, request, achievement_id):
        services.get_visible_achievement(request.user, achievement_id)
        return _detail(request, achievement_id)

    def patch(self, request, achievement_id):
        before = services.get_visible_achievement(request.user, achievement_id).verification_status
        serializer = AchievementWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        achievement = services.update_achievement(request.user, achievement_id, serializer.validated_data)
        message = "Achievement updated."
        if before == Achievement.VerificationStatus.VERIFIED and not achievement.is_verified:
            message = "Achievement updated. It was sent back for verification because verified details changed."
        return _detail(request, achievement_id, message)

    def delete(self, request, achievement_id):
        services.get_visible_achievement(request.user, achievement_id)
        services.delete_achievement(request.user, achievement_id)
        return success_response(message="Achievement deleted.")


class FeatureView(_Authenticated):
    def post(self, request, achievement_id):
        services.get_visible_achievement(request.user, achievement_id)
        services.set_featured(request.user, achievement_id, True)
        return _detail(request, achievement_id, "Achievement featured.")

    def delete(self, request, achievement_id):
        services.get_visible_achievement(request.user, achievement_id)
        services.set_featured(request.user, achievement_id, False)
        return _detail(request, achievement_id, "Achievement is no longer featured.")


class ResubmitView(_Authenticated):
    throttle_classes = [AchievementWriteThrottle]

    def post(self, request, achievement_id):
        services.get_visible_achievement(request.user, achievement_id)
        serializer = ResubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.resubmit(request.user, achievement_id, serializer.validated_data.get("note", ""))
        return _detail(request, achievement_id, "Achievement resubmitted for verification.")


class _ReviewView(APIView):
    permission_classes = [IsAuthenticated, IsModerator]
    throttle_classes = [AchievementReviewThrottle]
    decision = None
    message = ""

    def post(self, request, achievement_id):
        services.get_achievement(achievement_id)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.review(request.user, achievement_id, self.decision, serializer.validated_data.get("comments", ""))
        return _detail(request, achievement_id, self.message)


class VerifyView(_ReviewView):
    decision, message = "verify", "Achievement verified."


class RejectView(_ReviewView):
    decision, message = "reject", "Achievement rejected."


class RequestInformationView(_ReviewView):
    decision, message = "request_information", "More information requested."


class HistoryView(_Authenticated):
    """GET /api/achievements/<id>/history/  (owner and reviewers)"""

    def get(self, request, achievement_id):
        achievement = services.get_achievement(achievement_id)
        if not services.can_view_evidence(request.user, achievement):
            raise services.AchievementNotFound()
        reviews = achievement.reviews.select_related("reviewer")
        return success_response({"history": ReviewHistorySerializer(reviews, many=True).data})


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
EVIDENCE_BODY_LIMIT = 10 * 10 * 1024 * 1024 + 256 * 1024


class EvidenceUploadView(_Authenticated):
    """POST /api/achievements/<id>/evidence/  multipart: files=@a.pdf files=@b.jpg"""

    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AchievementUploadThrottle]

    def post(self, request, achievement_id):
        check_content_length(request, EVIDENCE_BODY_LIMIT)
        services.get_visible_achievement(request.user, achievement_id)
        serializer = EvidenceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _achievement, created = services.add_evidence(request.user, achievement_id, serializer.validated_data["uploads"])
        return success_response(
            {"evidence": EvidenceSerializer(created, many=True, context={"request": request}).data},
            "Evidence uploaded.", status.HTTP_201_CREATED,
        )


class EvidenceDeleteView(_Authenticated):
    def delete(self, request, evidence_id):
        services.delete_evidence(request.user, evidence_id)
        return success_response(message="Evidence removed.")


class EvidenceDownloadView(APIView):
    """
    GET /api/achievements/evidence/<id>/download/
    Authorised by a JWT (owner or reviewer) OR by the signed `?token=` from `download_url`.
    Always served as an attachment with the stored (detected) content type.
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, evidence_id):
        from django.conf import settings
        from django.contrib.auth import get_user_model

        user = request.user if is_authenticated(request.user) else None
        token = request.query_params.get("token")
        if token:
            user_id = read_download_token(
                token, kind=EVIDENCE_TOKEN_KIND, object_id=evidence_id,
                max_age=getattr(settings, "ACHIEVEMENT_EVIDENCE_URL_MAX_AGE_SECONDS", 600),
            )
            user = get_user_model().objects.filter(pk=user_id, is_active=True).first() if user_id else None
        if user is None:
            from common.exceptions import AuthenticationRequired

            raise AuthenticationRequired("Log in or use a valid download link.")
        evidence = services.get_evidence_for_download(user, evidence_id)
        try:
            handle = evidence.file.open("rb")
        except (FileNotFoundError, OSError):
            raise services.EvidenceNotFound()
        response = FileResponse(handle, as_attachment=True, filename=evidence.original_name, content_type=evidence.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class AchievementCategoryListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return success_response(
            {"results": AchievementCategorySerializer(AchievementCategory.objects.filter(is_active=True), many=True).data}
        )
