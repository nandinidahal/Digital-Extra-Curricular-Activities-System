"""One response shape for the whole API, so the React app can handle it in one place."""
from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message="", status_code=status.HTTP_200_OK):
    """
    {
        "success": true,
        "message": "Human readable message",
        "data": { ... }
    }
    """
    return Response(
        {"success": True, "message": message, "data": {} if data is None else data},
        status=status_code,
    )
