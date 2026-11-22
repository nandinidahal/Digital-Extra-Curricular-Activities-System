"""
Messaging API errors. Rendered by the project's `accounts.exceptions.api_exception_handler`,
so they share its JSON shape: {"success": false, "message": ..., "code": ..., "errors": {}, ...extra}
The WebSocket consumer turns the same exceptions into `error` events with the same code.
"""
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied


class _WithExtra:
    extra = None


class ConversationNotFound(NotFound):
    # Also returned to non-participants, so conversation ids cannot be probed.
    default_detail = "This conversation does not exist."
    default_code = "conversation_not_found"


class MessageNotFound(NotFound):
    default_detail = "This message does not exist."
    default_code = "message_not_found"


class AttachmentNotFound(NotFound):
    default_detail = "This attachment does not exist."
    default_code = "attachment_not_found"


class RecipientNotFound(NotFound):
    default_detail = "This user does not exist or is not available."
    default_code = "user_not_found"


class CannotMessageSelf(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You cannot start a conversation with yourself."
    default_code = "cannot_message_self"


class MessagingNotAllowed(PermissionDenied):
    """Deliberately vague: never reveals WHO blocked WHOM."""

    default_detail = "You cannot message this user."
    default_code = "messaging_not_allowed"


class AccountUnavailable(PermissionDenied):
    default_detail = "Your account cannot use messaging right now."
    default_code = "account_unavailable"


class ConversationInactive(PermissionDenied):
    default_detail = "This conversation is no longer active."
    default_code = "conversation_inactive"


class MessageLimitReached(_WithExtra, PermissionDenied):
    default_code = "message_limit_reached"

    def __init__(self, used, allowed):
        detail = (
            f"You have reached the {allowed}-message limit. Become friends to continue messaging."
            if allowed
            else "You need to be friends to message this user."
        )
        super().__init__(detail)
        self.extra = {"messages_used": used, "messages_allowed": allowed, "can_message": False}


class NotMessageOwner(PermissionDenied):
    default_detail = "You can only change your own messages."
    default_code = "not_message_owner"


class EditWindowExpired(PermissionDenied):
    default_detail = "This message can no longer be edited."
    default_code = "edit_window_expired"


class DeleteWindowExpired(PermissionDenied):
    default_detail = "This message can no longer be deleted for everyone. You can still delete it for yourself."
    default_code = "delete_window_expired"


class MessageNotEditable(PermissionDenied):
    default_detail = "This message cannot be edited."
    default_code = "message_not_editable"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action conflicts with the current state."
    default_code = "conflict"


class MessageDeleted(Conflict):
    default_detail = "This message has been deleted."
    default_code = "message_deleted"


class ClientIdConflict(Conflict):
    default_detail = "This client_id was already used for a different conversation."
    default_code = "client_id_conflict"


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The upload is too large."
    default_code = "payload_too_large"
