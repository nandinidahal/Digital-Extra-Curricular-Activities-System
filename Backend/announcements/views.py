from django.db.models import ProtectedError, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .filters import AnnouncementFilter
from .models import Announcement, AnnouncementStatus, Category
from .pagination import StandardPagination
from .permissions import IsAdminOrReadOnly, IsCoordinatorOrAdmin, IsOwnerOrAdmin
from .serializers import (
    AnnouncementDetailSerializer,
    AnnouncementListSerializer,
    AnnouncementWriteSerializer,
    CategorySerializer,
)


class AnnouncementViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AnnouncementFilter
    search_fields = [
        "title", "activity_name", "short_description", "full_description",
        "category__name", "country", "province", "city", "venue", "keywords",
    ]
    ordering_fields = ["published_at", "start_date", "end_date", "registration_deadline", "created_at"]
    ordering = None  # default ordering comes from Meta: newest published first

    def get_queryset(self):
        qs = Announcement.objects.select_related("category", "published_by")
        user = self.request.user
        if not user.is_authenticated or not user.is_coordinator:
            return qs.filter(status=AnnouncementStatus.PUBLISHED)
        if user.is_platform_admin:
            return qs
        # coordinator: everything published + all of their own (drafts/archived too)
        return qs.filter(Q(status=AnnouncementStatus.PUBLISHED) | Q(published_by=user))

    def get_serializer_class(self):
        if self.action == "list":
            return AnnouncementListSerializer
        if self.action == "retrieve":
            return AnnouncementDetailSerializer
        return AnnouncementWriteSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated(), IsCoordinatorOrAdmin()]
        return [IsAuthenticated(), IsCoordinatorOrAdmin(), IsOwnerOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(published_by=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None  # short list; the frontend wants it all for dropdowns
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.is_platform_admin:
            return Category.objects.all()
        return Category.objects.filter(is_active=True)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This category is used by announcements. Deactivate it instead of deleting."},
                status=status.HTTP_409_CONFLICT,
            )
