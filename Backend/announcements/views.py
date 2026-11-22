"""
API of the Announcements module.

Public (no login):   GET /api/announcements/public/, GET /api/announcements/<id>/,
                     GET /api/announcements/slug/<slug>/, GET /api/categories/
Everything else needs a JWT. Visitors calling an authenticated endpoint get 401.
"""
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response
from common.exceptions import check_content_length
from common.pagination import StandardPagination, paginate
from common.relationships import hidden_user_ids
from common.permissions import IsAdminRole, IsModerator, ReadAnyWriteAuthenticated, is_admin
from profiles.authentication import OptionalJWTAuthentication

from . import services
from .models import Announcement, AnnouncementReport, Category
from .serializers import (
    AnnouncementCardSerializer,
    AnnouncementDetailSerializer,
    AnnouncementFilterSerializer,
    AnnouncementWriteSerializer,
    BookmarkSerializer,
    CategorySerializer,
    ReportModerationSerializer,
    ReportReceiptSerializer,
    ReportReviewSerializer,
    ReportWriteSerializer,
)
from .throttles import (
    AnnouncementInteractionThrottle,
    AnnouncementReportThrottle,
    AnnouncementSearchThrottle,
    AnnouncementWriteThrottle,
)

UPLOAD_BODY_LIMIT = 6 * 1024 * 1024 + 256 * 1024


def _filters(request, *, allowed=None):
    params = request.query_params
    if allowed is not None:
        params = {k: v for k, v in params.items() if k in allowed}
    serializer = AnnouncementFilterSerializer(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _detail(request, announcement_id, message="", status_code=status.HTTP_200_OK):
    announcement = services.with_relations(Announcement.objects.filter(pk=announcement_id), request.user).get()
    return success_response(
        {"announcement": AnnouncementDetailSerializer(announcement, context={"request": request}).data},
        message, status_code,
    )


class _Authenticated(APIView):
    permission_classes = [IsAuthenticated]


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
class PublicAnnouncementListView(APIView):
    """
    GET /api/announcements/public/  (no login needed)
    Published PUBLIC announcements only. Filters: category, activity_type, when, ordering.
    Text search is reserved for logged-in users (/search/).
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        params = _filters(request, allowed={"category", "activity_type", "when", "ordering", "registration_open"})
        queryset = services.public_announcements()
        hidden = hidden_user_ids(request.user)
        if hidden:
            queryset = queryset.exclude(author_id__in=hidden)
        queryset = services.with_relations(services.apply_filters(queryset, params, allow_search=False), request.user)
        return paginate(request, queryset, AnnouncementCardSerializer)


class AnnouncementListCreateView(APIView):
    """
    GET  /api/announcements/   (login) published announcements the user may see, with filters
    POST /api/announcements/   (login) create; JSON or multipart (cover_image). status=draft|published
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_classes = [AnnouncementWriteThrottle]

    def get(self, request):
        params = _filters(request)
        if params.get("status") and not is_admin(request.user):
            params.pop("status")  # status filtering of other people's content is admin-only
        if is_admin(request.user) and params.get("status"):
            queryset = Announcement.objects.all()
        else:
            queryset = services.visible_announcements(request.user)
        queryset = services.with_relations(services.apply_filters(queryset, params, allow_search=True), request.user)
        return paginate(request, queryset, AnnouncementCardSerializer)

    def post(self, request):
        check_content_length(request, UPLOAD_BODY_LIMIT)
        serializer = AnnouncementWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        cover = data.pop("cover_image", None)
        data.pop("remove_cover_image", None)
        publish = data.pop("status", "draft") == "published"
        announcement = services.create_announcement(request.user, data, cover=cover, publish=publish)
        return _detail(
            request, announcement.pk,
            "Announcement published." if publish else "Announcement saved as draft.", status.HTTP_201_CREATED,
        )


class AnnouncementSearchView(_Authenticated):
    """GET /api/announcements/search/?q=robotics&category=technology&when=upcoming&ordering=start"""

    throttle_classes = [AnnouncementSearchThrottle]

    def get(self, request):
        params = _filters(request)
        params.pop("status", None)  # search only ever covers published announcements
        queryset = services.visible_announcements(request.user)
        queryset = services.with_relations(services.apply_filters(queryset, params, allow_search=True), request.user)
        return paginate(request, queryset, AnnouncementCardSerializer)


class MyAnnouncementsView(_Authenticated):
    """GET /api/announcements/me/[drafts|published|archived]/  -> own announcements, any status"""

    status_filter = None

    def get(self, request):
        params = _filters(request)
        queryset = services.own_announcements(request.user)
        if self.status_filter:
            params["status"] = self.status_filter
        if "ordering" not in params:
            params["ordering"] = "updated"
        queryset = services.with_relations(services.apply_filters(queryset, params, allow_search=True), request.user)
        return paginate(request, queryset, AnnouncementCardSerializer)


# ---------------------------------------------------------------------------
# Single announcement
# ---------------------------------------------------------------------------
class AnnouncementDetailView(APIView):
    """GET (public where visibility allows) / PATCH (owner) / DELETE (owner or moderator)"""

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [ReadAnyWriteAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_classes = [AnnouncementWriteThrottle]

    def get(self, request, announcement_id):
        announcement = services.get_visible_announcement(request.user, announcement_id)
        return success_response(
            {"announcement": AnnouncementDetailSerializer(announcement, context={"request": request}).data}
        )

    def patch(self, request, announcement_id):
        check_content_length(request, UPLOAD_BODY_LIMIT)
        services.get_visible_announcement(request.user, announcement_id, annotated=False)  # 404 before 403
        serializer = AnnouncementWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        cover = data.pop("cover_image", None)
        remove_cover = data.pop("remove_cover_image", False)
        services.update_announcement(request.user, announcement_id, data, cover=cover, remove_cover=remove_cover)
        return _detail(request, announcement_id, "Announcement updated.")

    def delete(self, request, announcement_id):
        services.get_visible_announcement(request.user, announcement_id, annotated=False)
        services.delete_announcement(request.user, announcement_id)
        return success_response(message="Announcement deleted.")


class AnnouncementBySlugView(APIView):
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, slug):
        announcement = services.get_visible_by_slug(request.user, slug)
        return success_response(
            {"announcement": AnnouncementDetailSerializer(announcement, context={"request": request}).data}
        )


class _LifecycleView(_Authenticated):
    throttle_classes = [AnnouncementWriteThrottle]
    action = None
    message = ""

    def post(self, request, announcement_id):
        services.get_visible_announcement(request.user, announcement_id, annotated=False)
        getattr(services, self.action)(request.user, announcement_id)
        return _detail(request, announcement_id, self.message)


class PublishView(_LifecycleView):
    action, message = "publish_announcement", "Announcement published."


class ArchiveView(_LifecycleView):
    action, message = "archive_announcement", "Announcement archived."


class RestoreView(_LifecycleView):
    action, message = "restore_announcement", "Announcement restored as a draft."


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
class BookmarkView(_Authenticated):
    """POST bookmark (201 new / 200 existing), DELETE remove (200, idempotent)."""

    throttle_classes = [AnnouncementInteractionThrottle]

    def post(self, request, announcement_id):
        _bookmark, created = services.bookmark(request.user, announcement_id)
        return success_response(
            {"announcement_id": str(announcement_id), "is_bookmarked": True},
            "Announcement bookmarked." if created else "Already bookmarked.",
            status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, announcement_id):
        services.remove_bookmark(request.user, announcement_id)
        return success_response({"announcement_id": str(announcement_id), "is_bookmarked": False}, "Bookmark removed.")


class BookmarkListView(_Authenticated):
    """GET /api/announcements/bookmarks/  -> only the requesting user's bookmarks"""

    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(services.user_bookmarks(request.user), request, view=None)
        ids = [b.announcement_id for b in page]
        visible = services.with_relations(services.visible_announcements(request.user).filter(pk__in=ids), request.user)
        cards = {a.pk: AnnouncementCardSerializer(a, context={"request": request}).data for a in visible}
        return paginator.get_paginated_response(BookmarkSerializer(page, many=True, context={"cards": cards}).data)


# ---------------------------------------------------------------------------
# Reports and moderation
# ---------------------------------------------------------------------------
class ReportCreateView(_Authenticated):
    throttle_classes = [AnnouncementReportThrottle]

    def post(self, request, announcement_id):
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.report(request.user, announcement_id, **serializer.validated_data)
        return success_response(
            {"report": ReportReceiptSerializer(report).data},
            "Thank you. Your report was submitted and will be reviewed.", status.HTTP_201_CREATED,
        )


class ReportListView(APIView):
    """GET /api/announcements/reports/?status=pending  (moderators only)"""

    permission_classes = [IsAuthenticated, IsModerator]

    def get(self, request):
        queryset = AnnouncementReport.objects.select_related("announcement", "reporter", "reviewed_by")
        status_filter = request.query_params.get("status")
        if status_filter in AnnouncementReport.Status.values:
            queryset = queryset.filter(status=status_filter)
        return paginate(request, queryset, ReportModerationSerializer)


class ReportDetailView(APIView):
    permission_classes = [IsAuthenticated, IsModerator]

    def _get(self, report_id):
        report = AnnouncementReport.objects.select_related("announcement", "reporter", "reviewed_by").filter(pk=report_id).first()
        if report is None:
            from common.exceptions import ResourceNotFound

            raise ResourceNotFound("This report does not exist.", code="report_not_found")
        return report

    def get(self, request, report_id):
        return success_response({"report": ReportModerationSerializer(self._get(report_id)).data})

    def patch(self, request, report_id):
        self._get(report_id)
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.review_report(request.user, report_id, **serializer.validated_data)
        return success_response({"report": ReportModerationSerializer(self._get(report_id)).data}, "Report updated.")


# ---------------------------------------------------------------------------
# Categories (/api/categories/)
# ---------------------------------------------------------------------------
class CategoryListCreateView(APIView):
    """GET active categories (anyone; admins may add ?include_inactive=true). POST: admins only."""

    authentication_classes = [OptionalJWTAuthentication]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated(), IsAdminRole()]

    def get(self, request):
        queryset = Category.objects.all()
        include_inactive = request.query_params.get("include_inactive") in ("1", "true")
        if not (include_inactive and is_admin(request.user)):
            queryset = queryset.filter(is_active=True)
        return success_response({"results": CategorySerializer(queryset, many=True).data})

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response({"category": serializer.data}, "Category created.", status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, category_id):
        category = Category.objects.filter(pk=category_id).first()
        if category is None:
            from common.exceptions import ResourceNotFound

            raise ResourceNotFound("This category does not exist.", code="category_not_found")
        return category

    def patch(self, request, category_id):
        serializer = CategorySerializer(self._get(category_id), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response({"category": serializer.data}, "Category updated.")

    def delete(self, request, category_id):
        outcome = services.delete_or_deactivate_category(self._get(category_id))
        message = "Category deleted." if outcome == "deleted" else "Category is in use and was deactivated instead."
        return success_response({"result": outcome}, message)
