from rest_framework.routers import SimpleRouter

from .views import AnnouncementViewSet, CategoryViewSet

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = router.urls
