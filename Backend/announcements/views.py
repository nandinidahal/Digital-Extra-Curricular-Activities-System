import mimetypes
import os

from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from . import filters, ranking, selectors
from .models import AnnouncementStatus, Bookmark, Category
from .pagination import StandardPagination
from .permissions import IsAnnouncementOwnerOrReadOnly
from .serializers import (AnnouncementDetailSerializer, AnnouncementPreviewSerializer,
                          AnnouncementWriteSerializer, CategorySerializer)

PARSERS = [MultiPartParser, FormParser, JSONParser]


class AnnouncementFeedView(generics.ListAPIView):
    """Shared list behaviour: validated params -> filters -> search -> sort/rank -> pagination."""

    serializer_class = AnnouncementPreviewSerializer
    pagination_class = StandardPagination
    default_sort = "latest"
    force_sort = False        # ignore ?sort=
    force_ranking = False     # always use the recommendation score
    require_query = False     # ?q= mandatory (search endpoint)

    def base_queryset(self):
        return selectors.public_queryset(self.request.user)

    def scope(self, qs, params):
        return qs

    def list(self, request, *args, **kwargs):
        ser = filters.AnnouncementQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        params = ser.validated_data
        if self.require_query and not filters.search_terms(params.get("q")):
            raise serializers.ValidationError({"q": ["This query parameter is required."]})

        qs = filters.apply_filters(self.scope(self.base_queryset(), params), params)
        qs, searched = filters.apply_search(qs, params.get("q"))
        sort = self.default_sort if self.force_sort else params.get("sort", self.default_sort)

        if self.force_ranking or (sort == "relevant" and not searched):
            items = ranking.rank(qs, request.user)
        else:
            items = filters.apply_sort(qs, sort, searched=searched)
        page = self.paginate_queryset(items)
        data = self.get_serializer(page, many=True).data
        return self.get_paginated_response(data)


class AnnouncementListCreateView(AnnouncementFeedView):
    """GET: all published announcements (filter/search/sort). POST: create (author = request.user)."""

    parser_classes = PARSERS

    def post(self, request, *args, **kwargs):
        ser = AnnouncementWriteSerializer(data=request.data, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj = selectors.visible_queryset(request.user).get(pk=obj.pk)
        return Response(AnnouncementDetailSerializer(obj, context=self.get_serializer_context()).data,
                        status=status.HTTP_201_CREATED)


class LatestAnnouncementsView(AnnouncementFeedView):
    force_sort = True
    default_sort = "latest"


class FeaturedAnnouncementsView(AnnouncementFeedView):
    def scope(self, qs, params):
        return qs.filter(is_featured=True)


class ImportantAnnouncementsView(AnnouncementFeedView):
    def scope(self, qs, params):
        return qs.filter(is_important=True)


class RecommendedAnnouncementsView(AnnouncementFeedView):
    force_ranking = True


class UpcomingEventsView(AnnouncementFeedView):
    default_sort = "event_date"

    def scope(self, qs, params):
        return qs.filter(selectors.upcoming_event_q())


class UpcomingDeadlinesView(AnnouncementFeedView):
    default_sort = "deadline"

    def scope(self, qs, params):
        return qs.filter(selectors.upcoming_deadline_q())


class SearchAnnouncementsView(AnnouncementFeedView):
    require_query = True
    default_sort = "relevant"


class AuthorAnnouncementsView(AnnouncementFeedView):
    """Published announcements of one student (never their drafts, not even for the author)."""

    def scope(self, qs, params):
        return qs.filter(published_by_id=self.kwargs["user_id"])


class MyAnnouncementsView(AnnouncementFeedView):
    """The authenticated student's own announcements in every state (?state=draft|scheduled|...)."""

    default_sort = "updated"

    def base_queryset(self):
        return selectors.owned_queryset(self.request.user)

    def scope(self, qs, params):
        return qs.filter(selectors.state_q(params["state"])) if "state" in params else qs


class MyDraftsView(MyAnnouncementsView):
    def scope(self, qs, params):
        return qs.filter(status=AnnouncementStatus.DRAFT)


class BookmarkedAnnouncementsView(AnnouncementFeedView):
    """Only the requesting student's own bookmarks."""

    default_sort = "bookmarked"
    force_sort = True

    def base_queryset(self):
        return selectors.bookmarked_queryset(self.request.user)


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True)


class AnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET: any student may read a live announcement (owner also drafts/scheduled/expired);
    anything else is a 404. PUT/PATCH/DELETE: author only (403 for everybody else)."""

    permission_classes = [IsAuthenticated, IsAnnouncementOwnerOrReadOnly]
    parser_classes = PARSERS

    def get_queryset(self):
        return selectors.visible_queryset(self.request.user)

    def get_serializer_class(self):
        return AnnouncementDetailSerializer if self.request.method in SAFE_METHODS else AnnouncementWriteSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        ser = AnnouncementWriteSerializer(instance, data=request.data, partial=kwargs.pop("partial", False),
                                          context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        ser.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        return Response(AnnouncementDetailSerializer(fresh, context=self.get_serializer_context()).data)


class SharedAnnouncementView(generics.RetrieveAPIView):
    """Open an announcement through its non-guessable share_id (still requires login)."""

    serializer_class = AnnouncementDetailSerializer
    lookup_field = "share_id"

    def get_queryset(self):
        return selectors.visible_queryset(self.request.user)


class ShareInfoView(APIView):
    def get(self, request, pk):
        obj = get_object_or_404(selectors.visible_queryset(request.user), pk=pk)
        if obj.state != "published":
            return Response({"detail": "Only published announcements can be shared."},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "id": obj.pk,
            "share_id": obj.share_id,
            "detail_url": reverse("announcement-detail", args=[obj.pk], request=request),
            "shared_url": reverse("announcement-shared", args=[obj.share_id], request=request),
        })


class BookmarkView(APIView):
    """GET: am I bookmarking it? POST: bookmark (201, or 200 if it already was). DELETE: remove (204)."""

    def _announcement(self, request, pk):
        return get_object_or_404(selectors.public_queryset(request.user), pk=pk)

    def get(self, request, pk):
        self._announcement(request, pk)
        return Response({"bookmarked": Bookmark.objects.filter(user=request.user, announcement_id=pk).exists()})

    def post(self, request, pk):
        obj = self._announcement(request, pk)
        try:
            with transaction.atomic():
                _, created = Bookmark.objects.get_or_create(user=request.user, announcement=obj)
        except IntegrityError:  # lost a race against a parallel request: the row exists
            created = False
        count = Bookmark.objects.filter(announcement=obj).count()
        return Response({"bookmarked": True, "bookmark_count": count},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, pk):
        deleted, _ = Bookmark.objects.filter(user=request.user, announcement_id=pk).delete()
        if not deleted:
            self._announcement(request, pk)  # 404 for unknown / not-visible ids, 204 otherwise
        return Response(status=status.HTTP_204_NO_CONTENT)


class AttachmentDownloadView(APIView):
    """Private attachments are only served to users who may see the announcement."""

    def get(self, request, pk):
        obj = get_object_or_404(selectors.visible_queryset(request.user), pk=pk)
        if not obj.attachment:
            raise Http404
        try:
            handle = obj.attachment.open("rb")
        except (FileNotFoundError, OSError):
            raise Http404
        name = obj.attachment_name or os.path.basename(obj.attachment.name)
        response = FileResponse(handle, as_attachment=True, filename=name,
                                content_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
        response["X-Content-Type-Options"] = "nosniff"
        return response


class LandingView(APIView):
    """One call for the landing page: previews for every section (real records only)."""

    def get(self, request):
        lim = serializers.IntegerField(min_value=1, max_value=12, required=False, default=6)
        limit = lim.run_validation(request.query_params.get("limit", 6))
        ctx = {"request": request}
        base = selectors.public_queryset(request.user)

        def preview(items):
            return AnnouncementPreviewSerializer(list(items)[:limit], many=True, context=ctx).data

        newest = filters.apply_sort(base, "latest")
        return Response({
            "featured": preview(filters.apply_sort(base.filter(is_featured=True), "latest")[:limit]),
            "latest": preview(newest[:limit]),
            "recommended": preview(ranking.rank(base, request.user)[:limit]),
            "upcoming_events": preview(filters.apply_sort(base.filter(selectors.upcoming_event_q()), "event_date")[:limit]),
            "upcoming_deadlines": preview(filters.apply_sort(base.filter(selectors.upcoming_deadline_q()), "deadline")[:limit]),
            "important": preview(filters.apply_sort(base.filter(is_important=True), "latest")[:limit]),
        })
