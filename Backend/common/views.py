"""Health check: GET /api/health/ (no authentication, no sensitive information)."""
import logging

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("common")


def _database_ok():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception as exc:  # report the TYPE only; never credentials or messages
        logger.error("Health check: database unavailable (%s)", type(exc).__name__)
        return False


def _cache_ok():
    try:
        cache.set("deas:health", "1", 5)
        return cache.get("deas:health") == "1"
    except Exception as exc:
        logger.warning("Health check: cache unavailable (%s)", type(exc).__name__)
        return False


class HealthCheckView(APIView):
    """
    200 {"success": true, "data": {"status": "ok", "checks": {"database": "ok", "cache": "ok"}}}
    503 when the database is unreachable. A cache problem is reported as "degraded" (200).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        database = _database_ok()
        cache_state = _cache_ok()
        overall = "ok" if database and cache_state else ("degraded" if database else "unavailable")
        body = {
            "success": database,
            "message": "" if database else "Service unavailable.",
            "data": {
                "status": overall,
                "checks": {
                    "database": "ok" if database else "unavailable",
                    "cache": "ok" if cache_state else "unavailable",
                },
                "time": timezone.now().isoformat(),
            },
        }
        if not database:
            body["code"] = "service_unavailable"
        return Response(body, status=status.HTTP_200_OK if database else status.HTTP_503_SERVICE_UNAVAILABLE)
