from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from announcements.pagination import StandardPagination

from .models import AchievementCategory
from .permissions import CanAccessAchievement
from .selectors import documents_visible_to, owned_by, public_of, visible_to
from .serializers import (
    AchievementCategorySerializer,
    AchievementWriteSerializer,
    OwnerAchievementSerializer,
    PublicAchievementSerializer,
)

PARSERS = [MultiPartParser, FormParser, JSONParser]


class AchievementCategoryListView(generics.ListAPIView):
    """Active categories for the create/edit form dropdown. Not a search endpoint."""

    serializer_class = AchievementCategorySerializer
    pagination_class = None
    queryset = AchievementCategory.objects.filter(is_active=True)


class AchievementCreateView(generics.CreateAPIView):
    """POST /api/achievements/ (there is intentionally no GET list here)."""

    serializer_class = AchievementWriteSerializer
    parser_classes = PARSERS


class MyAchievementListView(generics.ListAPIView):
    serializer_class = OwnerAchievementSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return owned_by(self.request.user)


class MyAchievementDetailView(generics.RetrieveAPIView):
    serializer_class = OwnerAchievementSerializer

    def get_queryset(self):
        return owned_by(self.request.user)


class AchievementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET: owner or PUBLIC only (anything else is a 404). PUT/PATCH/DELETE: owner only."""

    permission_classes = [IsAuthenticated, CanAccessAchievement]
    parser_classes = PARSERS

    def get_queryset(self):
        return visible_to(self.request.user)

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return PublicAchievementSerializer
        return AchievementWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer_class = OwnerAchievementSerializer if obj.user_id == request.user.id else PublicAchievementSerializer
        return Response(serializer_class(obj, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        # Document rows cascade; their files are removed on commit by the post_delete receiver.
        with transaction.atomic():
            instance.delete()


class UserPublicAchievementListView(generics.ListAPIView):
    """Achievements shown on a user's profile: PUBLIC only, even when the owner asks."""

    serializer_class = PublicAchievementSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        User = get_user_model()
        owner = generics.get_object_or_404(User.objects.filter(is_active=True), pk=self.kwargs["user_id"])
        return public_of(owner)


class AchievementDocumentDownloadView(APIView):
    """Streams a document after checking ownership / visibility on every request."""

    def get(self, request, pk, document_id):
        # Documents of other users' PRIVATE achievements are excluded from the queryset,
        # so they answer 404 exactly like a document that does not exist.
        document = generics.get_object_or_404(
            documents_visible_to(request.user), pk=document_id, achievement_id=pk
        )
        try:
            handle = document.file.open("rb")
        except (FileNotFoundError, OSError, ValueError):
            return Response({"detail": "The document file could not be found."}, status=404)

        response = FileResponse(
            handle,
            as_attachment=True,
            filename=document.original_filename or "document",
            content_type=document.content_type or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
