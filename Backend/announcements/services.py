"""
Business logic of the Announcements module. Views stay thin; other modules import from here.

PUBLIC INTEGRATION API
    visible_announcements(viewer)        published announcements the viewer may see
    public_announcements()               published + public (what visitors see)
    get_visible_announcement(viewer, id) single object, raises 404 / 401
    is_shareable(announcement)           published + public (Social sharing rule)

Access levels
    owner      - the author: everything on their own announcements
    moderator  - admin or coordinator: may read any announcement, archive or delete it, and
                 review reports; moderators do NOT edit someone else's content
    member     - authenticated user: published public + members-only announcements
    visitor    - anonymous: published public announcements only
Blocks (Friends module) hide announcements in both directions for logged-in users.
"""
import logging
import secrets

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, Value
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from common.exceptions import (
    AuthenticationRequired,
    BusinessRuleViolation,
    Conflict,
    NotOwner,
    ResourceNotFound,
)
from common.files import delete_stored_file, reencode_image
from common.permissions import is_authenticated, is_moderator
from common.relationships import hidden_user_ids, is_blocked_between
from notifications.services import notify, notify_many

from .models import Announcement, AnnouncementBookmark, AnnouncementReport, Category

logger = logging.getLogger("announcements")

Status = Announcement.Status
Visibility = Announcement.Visibility
ActivityType = Announcement.ActivityType

# Changes that matter to people who bookmarked an announcement.
MEANINGFUL_FIELDS = {
    "start_datetime": "start time",
    "end_datetime": "end time",
    "registration_deadline": "registration deadline",
    "location": "location",
    "online_link": "online link",
    "activity_type": "activity type",
    "registration_link": "registration link",
}
# Fields the author may set through the API (everything else is server-controlled).
EDITABLE_FIELDS = (
    "title", "short_description", "description", "category", "activity_type", "organizer_name",
    "organizer_email", "organizer_phone", "contact_information", "show_contact_details", "location",
    "online_link", "start_datetime", "end_datetime", "registration_deadline", "registration_link",
    "eligibility_criteria", "requirements", "visibility",
)
ALLOWED_TRANSITIONS = {
    Status.DRAFT: {Status.PUBLISHED, Status.ARCHIVED},
    Status.PUBLISHED: {Status.ARCHIVED},
    Status.ARCHIVED: {Status.DRAFT},
}


class NotFound(ResourceNotFound):
    default_detail = "This announcement does not exist or is not available."
    default_code = "announcement_not_found"


# ---------------------------------------------------------------------------
# Querysets
# ---------------------------------------------------------------------------
def _base():
    return Announcement.objects.filter(author__is_active=True)


def public_announcements():
    return _base().filter(status=Status.PUBLISHED, visibility=Visibility.PUBLIC)


def visible_announcements(viewer):
    """Published announcements the viewer may see in listings and search (no moderator override)."""
    if not is_authenticated(viewer):
        return public_announcements()
    queryset = _base().filter(status=Status.PUBLISHED).filter(
        Q(visibility__in=[Visibility.PUBLIC, Visibility.MEMBERS_ONLY]) | Q(author=viewer)
    )
    hidden = hidden_user_ids(viewer)
    return queryset.exclude(author_id__in=hidden) if hidden else queryset


def own_announcements(user):
    return Announcement.objects.filter(author=user)


def with_relations(queryset, viewer):
    """select_related for cards + is_bookmarked as one EXISTS subquery (no N+1)."""
    if is_authenticated(viewer):
        bookmarked = Exists(AnnouncementBookmark.objects.filter(announcement=OuterRef("pk"), user=viewer))
    else:
        bookmarked = Value(False)
    return queryset.select_related("author", "author__profile", "category").annotate(is_bookmarked=bookmarked)


def access_level(viewer, announcement):
    if not is_authenticated(viewer):
        return "visitor"
    if announcement.author_id == viewer.pk:
        return "owner"
    if is_moderator(viewer):
        return "moderator"
    return "member"


def check_visible(viewer, announcement):
    """Raises 404 (missing / draft / archived / private / blocked) or 401 (members-only visitor)."""
    level = access_level(viewer, announcement)
    if level in ("owner", "moderator"):
        return level
    if announcement.status != Status.PUBLISHED or not announcement.author.is_active:
        raise NotFound()
    if announcement.visibility == Visibility.PRIVATE:
        raise NotFound()
    if announcement.visibility == Visibility.MEMBERS_ONLY and level == "visitor":
        raise AuthenticationRequired("Please log in to view this announcement.")
    if level == "member" and is_blocked_between(viewer, announcement.author_id):
        raise NotFound()
    return level


def get_announcement(announcement_id, *, viewer=None, annotated=False, lock=False):
    queryset = Announcement.objects.filter(pk=announcement_id)
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    queryset = with_relations(queryset, viewer) if annotated else queryset.select_related("author", "category")
    announcement = queryset.first()
    if announcement is None:
        raise NotFound()
    return announcement


def get_visible_announcement(viewer, announcement_id, *, annotated=True):
    announcement = get_announcement(announcement_id, viewer=viewer, annotated=annotated)
    check_visible(viewer, announcement)
    return announcement


def get_visible_by_slug(viewer, slug):
    announcement = with_relations(Announcement.objects.filter(slug=slug), viewer).first()
    if announcement is None:
        raise NotFound()
    check_visible(viewer, announcement)
    return announcement


def is_shareable(announcement):
    return (
        announcement is not None
        and announcement.status == Status.PUBLISHED
        and announcement.visibility == Visibility.PUBLIC
        and announcement.author.is_active
    )


def require_owner(user, announcement):
    if announcement.author_id != user.pk:
        raise NotOwner("You can only change your own announcements.")


def require_owner_or_moderator(user, announcement):
    if announcement.author_id != user.pk and not is_moderator(user):
        raise NotOwner("You can only manage your own announcements.")


# ---------------------------------------------------------------------------
# Filtering / search (query parameters are validated by AnnouncementFilterSerializer)
# ---------------------------------------------------------------------------
ORDERINGS = {
    "newest": ("-published_at", "-created_at"),
    "oldest": ("published_at", "created_at"),
    "start": ("start_datetime", "-published_at"),
    "-start": ("-start_datetime", "-published_at"),
    "deadline": ("registration_deadline", "-published_at"),
    "title": ("title",),
    "updated": ("-updated_at",),
}


def apply_filters(queryset, params, *, allow_search):
    now = timezone.now()
    text = (params.get("q") or "").strip() if allow_search else ""
    if text:
        queryset = queryset.filter(
            Q(title__icontains=text) | Q(short_description__icontains=text) | Q(description__icontains=text)
            | Q(organizer_name__icontains=text) | Q(location__icontains=text) | Q(category__name__icontains=text)
        )
    if params.get("category"):
        value = params["category"]
        queryset = queryset.filter(Q(category__slug=value) | Q(category__id=value) if _is_uuid(value) else Q(category__slug=value))
    if params.get("activity_type"):
        queryset = queryset.filter(activity_type=params["activity_type"])
    if params.get("location"):
        queryset = queryset.filter(location__icontains=params["location"])
    if params.get("organizer"):
        queryset = queryset.filter(organizer_name__icontains=params["organizer"])
    if params.get("start_from"):
        queryset = queryset.filter(start_datetime__gte=params["start_from"])
    if params.get("start_to"):
        queryset = queryset.filter(start_datetime__lte=params["start_to"])
    if params.get("deadline_from"):
        queryset = queryset.filter(registration_deadline__gte=params["deadline_from"])
    if params.get("deadline_to"):
        queryset = queryset.filter(registration_deadline__lte=params["deadline_to"])
    if params.get("published_from"):
        queryset = queryset.filter(published_at__gte=params["published_from"])
    if params.get("published_to"):
        queryset = queryset.filter(published_at__lte=params["published_to"])
    when = params.get("when")
    if when == "upcoming":
        queryset = queryset.filter(start_datetime__gt=now)
    elif when == "past":
        queryset = queryset.filter(Q(end_datetime__lt=now) | Q(end_datetime__isnull=True, start_datetime__lt=now))
    elif when == "ongoing":
        queryset = queryset.filter(start_datetime__lte=now).filter(Q(end_datetime__gte=now) | Q(end_datetime__isnull=True))
    if params.get("registration_open"):
        queryset = queryset.filter(Q(registration_deadline__gte=now) | Q(registration_deadline__isnull=True, start_datetime__gt=now))
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("visibility"):
        queryset = queryset.filter(visibility=params["visibility"])
    return queryset.order_by(*ORDERINGS.get(params.get("ordering") or "newest", ORDERINGS["newest"]), "id")


def _is_uuid(value):
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Validation shared by create / update / publish
# ---------------------------------------------------------------------------
def _value(announcement, data, field):
    return data[field] if field in data else getattr(announcement, field, None)


def validate_consistency(data, announcement=None):
    """Cross-field rules that always apply (draft or published)."""
    errors = {}
    start = _value(announcement, data, "start_datetime")
    end = _value(announcement, data, "end_datetime")
    deadline = _value(announcement, data, "registration_deadline")
    if start and end and end < start:
        errors["end_datetime"] = ["The end date and time cannot be before the start."]
    if start and deadline and deadline > start:
        errors["registration_deadline"] = ["The registration deadline must be on or before the start of the event."]
    if end and not start:
        errors["start_datetime"] = ["Set a start date and time when an end is given."]
    category = data.get("category")
    if category is not None and (announcement is None or category.pk != announcement.category_id):
        if not category.is_active:
            errors["category"] = ["This category is no longer available."]
    if errors:
        raise ValidationError(errors)


def validate_for_publication(announcement, *, allow_inactive_category=False):
    """
    Everything a published announcement must have. Raises one ValidationError listing every gap.
    `allow_inactive_category`: an already-published announcement keeps a category that was
    deactivated later (existing references are retained); new publications need an active one.
    """
    errors = {}
    if not announcement.title.strip():
        errors["title"] = ["A title is required."]
    if not announcement.short_description.strip():
        errors["short_description"] = ["A short description is required to publish."]
    if not announcement.description.strip():
        errors["description"] = ["A full description is required to publish."]
    if announcement.category_id is None:
        errors["category"] = ["Choose a category to publish."]
    elif not announcement.category.is_active and not allow_inactive_category:
        errors["category"] = ["This category is no longer available. Choose another one."]
    if announcement.start_datetime is None:
        errors["start_datetime"] = ["A start date and time is required to publish."]
    else:
        finish = announcement.end_datetime or announcement.start_datetime
        if finish < timezone.now():
            errors["start_datetime"] = ["This event is already over and cannot be published."]
    if announcement.activity_type in (ActivityType.PHYSICAL, ActivityType.HYBRID) and not announcement.location.strip():
        errors["location"] = ["Physical and hybrid activities need a location."]
    if announcement.activity_type in (ActivityType.ONLINE, ActivityType.HYBRID) and not announcement.online_link:
        errors["online_link"] = ["Online and hybrid activities need an online meeting or event link."]
    if errors:
        raise ValidationError(errors)


def _unique_slug(title):
    base = slugify(title)[:200] or "announcement"
    for _ in range(10):
        slug = f"{base}-{secrets.token_hex(3)}"
        if not Announcement.objects.filter(slug=slug).exists():
            return slug
    return f"{base}-{secrets.token_hex(8)}"


# ---------------------------------------------------------------------------
# Create / update / lifecycle
# ---------------------------------------------------------------------------
def create_announcement(author, data, *, cover=None, publish=False):
    """`data` comes from AnnouncementWriteSerializer (already field-validated)."""
    validate_consistency(data)
    stored_name = None
    try:
        with transaction.atomic():
            announcement = Announcement(author=author, slug=_unique_slug(data.get("title", "")))
            for field in EDITABLE_FIELDS:
                if field in data:
                    setattr(announcement, field, data[field])
            if cover is not None:
                upload, detected = cover
                content, _w, _h, extension = reencode_image(upload, detected.format, max_edge=1920)
                announcement.cover_image.save(f"cover.{extension}", content, save=False)
                stored_name = announcement.cover_image.name
            if publish:
                validate_for_publication(announcement)
                announcement.status = Status.PUBLISHED
                announcement.published_at = timezone.now()
            announcement.save()
            if publish:
                _announce_publication(announcement)
            else:
                notify(
                    recipient=author.pk, notification_type="announcement.created",
                    context={"title": announcement.title}, target_type="announcement", target_id=announcement.pk,
                    action_url=f"/announcements/{announcement.pk}", dedupe_key=f"announcement.created:{announcement.pk}",
                )
    except Exception:
        if stored_name:
            delete_stored_file(Announcement._meta.get_field("cover_image").storage, stored_name)
        raise
    return announcement


def update_announcement(user, announcement_id, data, *, cover=None, remove_cover=False):
    stored_name = None
    try:
        with transaction.atomic():
            announcement = get_announcement(announcement_id, lock=True)
            require_owner(user, announcement)
            if announcement.status == Status.ARCHIVED:
                raise BusinessRuleViolation("Restore the announcement before editing it.", code="announcement_archived")
            validate_consistency(data, announcement)

            changed = [f for f in EDITABLE_FIELDS if f in data and getattr(announcement, f) != data[f]]
            if "category" in data:
                changed = [f for f in changed if f != "category"] + (
                    ["category"] if (data["category"].pk if data["category"] else None) != announcement.category_id else []
                )
            for field in EDITABLE_FIELDS:
                if field in data:
                    setattr(announcement, field, data[field])
            old_cover = announcement.cover_image.name if announcement.cover_image else None
            if cover is not None:
                upload, detected = cover
                content, _w, _h, extension = reencode_image(upload, detected.format, max_edge=1920)
                announcement.cover_image.save(f"cover.{extension}", content, save=False)
                stored_name = announcement.cover_image.name
                changed.append("cover_image")
            elif remove_cover and old_cover:
                announcement.cover_image = ""
                changed.append("cover_image")
            if announcement.status == Status.PUBLISHED:
                # a published announcement must stay complete
                validate_for_publication(announcement, allow_inactive_category="category" not in changed)
                if changed:
                    announcement.is_edited = True
            if "title" in data and announcement.status == Status.DRAFT:
                announcement.slug = _unique_slug(announcement.title)
            announcement.save()
            if old_cover and "cover_image" in changed:
                storage = Announcement._meta.get_field("cover_image").storage
                transaction.on_commit(lambda: delete_stored_file(storage, old_cover))

            meaningful = [label for field, label in MEANINGFUL_FIELDS.items() if field in changed]
            if announcement.status == Status.PUBLISHED and meaningful:
                _notify_bookmarkers(
                    announcement, "announcement.updated", actor=user,
                    context={"title": announcement.title, "changes": ", ".join(meaningful)},
                    metadata={"changed": meaningful}, group_key=f"announcement.updated:{announcement.pk}",
                )
    except Exception:
        if stored_name:
            delete_stored_file(Announcement._meta.get_field("cover_image").storage, stored_name)
        raise
    return announcement


def _transition(announcement, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(announcement.status, set()):
        raise BusinessRuleViolation(
            f"A {announcement.status} announcement cannot be changed to {new_status}.", code="invalid_status_transition"
        )


@transaction.atomic
def publish_announcement(user, announcement_id):
    announcement = get_announcement(announcement_id, lock=True)
    require_owner(user, announcement)
    if announcement.status == Status.PUBLISHED:
        return announcement  # idempotent
    _transition(announcement, Status.PUBLISHED)
    validate_for_publication(announcement)
    announcement.status = Status.PUBLISHED
    announcement.published_at = timezone.now()
    announcement.archived_at = None
    announcement.archived_by = None
    announcement.save()
    _announce_publication(announcement)
    return announcement


@transaction.atomic
def archive_announcement(user, announcement_id):
    announcement = get_announcement(announcement_id, lock=True)
    require_owner_or_moderator(user, announcement)
    if announcement.status == Status.ARCHIVED:
        return announcement
    _transition(announcement, Status.ARCHIVED)
    was_published = announcement.status == Status.PUBLISHED
    announcement.status = Status.ARCHIVED
    announcement.archived_at = timezone.now()
    announcement.archived_by = user
    announcement.save()
    if was_published:
        _notify_bookmarkers(
            announcement, "announcement.archived", actor=user, context={"title": announcement.title},
            dedupe_key=f"announcement.archived:{announcement.pk}:{announcement.archived_at.isoformat()}",
        )
    if announcement.author_id != user.pk:  # moderation: tell the author
        notify(
            recipient=announcement.author_id, actor=user.pk, notification_type="announcement.archived",
            context={"title": announcement.title}, target_type="announcement", target_id=announcement.pk,
            metadata={"by_moderator": True}, action_url=f"/announcements/{announcement.pk}",
        )
    return announcement


@transaction.atomic
def restore_announcement(user, announcement_id):
    """Archived -> draft (the author can then edit and publish again)."""
    announcement = get_announcement(announcement_id, lock=True)
    require_owner(user, announcement)
    _transition(announcement, Status.DRAFT)
    announcement.status = Status.DRAFT
    announcement.archived_at = None
    announcement.archived_by = None
    announcement.save()
    return announcement


@transaction.atomic
def delete_announcement(user, announcement_id):
    announcement = get_announcement(announcement_id, lock=True)
    require_owner_or_moderator(user, announcement)
    announcement.delete()  # the post_delete signal removes the cover file after commit


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def _announce_publication(announcement):
    """Audience rule (ANNOUNCEMENT_PUBLISH_AUDIENCE): the author's friends; never for private."""
    from django.conf import settings

    if announcement.visibility == Visibility.PRIVATE:
        return
    if getattr(settings, "ANNOUNCEMENT_PUBLISH_AUDIENCE", "friends") != "friends":
        return
    from friends.services import get_friend_ids

    friend_ids = get_friend_ids(announcement.author_id)
    notify_many(
        recipients=friend_ids, notification_type="announcement.published", actor=announcement.author_id,
        context={"title": announcement.title}, target_type="announcement", target_id=announcement.pk,
        metadata={"announcement_id": announcement.pk}, action_url=f"/announcements/{announcement.pk}",
        dedupe_key=f"announcement.published:{announcement.pk}",
    )


def _bookmarker_ids(announcement):
    return list(
        AnnouncementBookmark.objects.filter(announcement=announcement, user__is_active=True)
        .exclude(user_id=announcement.author_id)
        .values_list("user_id", flat=True)
    )


def _notify_bookmarkers(announcement, notification_type, *, actor, context, metadata=None, dedupe_key=None, group_key=None):
    """Only people who may still SEE the announcement are told about it."""
    for user_id in _bookmarker_ids(announcement):
        if announcement.visibility == Visibility.PRIVATE:
            continue
        notify(
            recipient=user_id, actor=getattr(actor, "pk", actor), notification_type=notification_type,
            context=context, target_type="announcement", target_id=announcement.pk,
            metadata={"announcement_id": announcement.pk, **(metadata or {})},
            action_url=f"/announcements/{announcement.pk}", dedupe_key=dedupe_key, group_key=group_key,
        )


def send_due_reminders(now=None, hours=None):
    """
    Notify bookmarkers of published announcements that start within the next `hours`.
    Idempotent: the dedupe key contains the start time, so each user gets one reminder per
    start time (a re-scheduled event is reminded again). Returns the number scheduled.
    """
    from django.conf import settings

    now = now or timezone.now()
    hours = hours or getattr(settings, "ANNOUNCEMENT_REMINDER_HOURS", 24)
    window_end = now + timezone.timedelta(hours=hours)
    due = (
        _base().filter(status=Status.PUBLISHED, start_datetime__gt=now, start_datetime__lte=window_end)
        .exclude(visibility=Visibility.PRIVATE)
    )
    scheduled = 0
    for announcement in due.select_related("author"):
        when = announcement.start_datetime.strftime("%d %b %Y at %H:%M UTC")
        for user_id in _bookmarker_ids(announcement):
            notify(
                recipient=user_id, notification_type="announcement.reminder",
                context={"title": announcement.title, "when": f"on {when}"},
                target_type="announcement", target_id=announcement.pk,
                metadata={"announcement_id": announcement.pk, "start_datetime": announcement.start_datetime.isoformat()},
                action_url=f"/announcements/{announcement.pk}",
                dedupe_key=f"announcement.reminder:{announcement.pk}:{announcement.start_datetime.isoformat()}",
                expires_at=announcement.end_datetime or announcement.start_datetime,
            )
            scheduled += 1
    return scheduled


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
def bookmark(user, announcement_id):
    """Idempotent. Returns (bookmark, created)."""
    announcement = get_visible_announcement(user, announcement_id, annotated=False)
    if announcement.status != Status.PUBLISHED:
        raise BusinessRuleViolation("Only published announcements can be bookmarked.", code="not_bookmarkable")
    try:
        with transaction.atomic():
            return AnnouncementBookmark.objects.get_or_create(user=user, announcement=announcement)
    except IntegrityError:  # concurrent duplicate: the unique constraint won
        return AnnouncementBookmark.objects.get(user=user, announcement=announcement), False


def remove_bookmark(user, announcement_id):
    deleted, _ = AnnouncementBookmark.objects.filter(user=user, announcement_id=announcement_id).delete()
    return bool(deleted)


def user_bookmarks(user):
    return AnnouncementBookmark.objects.filter(user=user).select_related("announcement")


# ---------------------------------------------------------------------------
# Reports and moderation
# ---------------------------------------------------------------------------
def report(user, announcement_id, *, reason, description=""):
    announcement = get_visible_announcement(user, announcement_id, annotated=False)
    if announcement.author_id == user.pk:
        raise BusinessRuleViolation("You cannot report your own announcement.", code="cannot_report_own_content")
    try:
        with transaction.atomic():
            return AnnouncementReport.objects.create(
                reporter=user, announcement=announcement, reason=reason, description=description
            )
    except IntegrityError:
        raise Conflict("You have already reported this announcement and it is still being reviewed.", code="already_reported")


REPORT_TRANSITIONS = {
    AnnouncementReport.Status.PENDING: {"reviewed", "resolved", "rejected"},
    AnnouncementReport.Status.REVIEWED: {"resolved", "rejected"},
    AnnouncementReport.Status.RESOLVED: set(),
    AnnouncementReport.Status.REJECTED: set(),
}


@transaction.atomic
def review_report(moderator, report_id, *, status, review_comments="", action="none"):
    report_obj = AnnouncementReport.objects.select_for_update().filter(pk=report_id).first()
    if report_obj is None:
        raise ResourceNotFound("This report does not exist.", code="report_not_found")
    if status != report_obj.status and status not in REPORT_TRANSITIONS[report_obj.status]:
        raise BusinessRuleViolation(
            f"A {report_obj.status} report cannot be changed to {status}.", code="invalid_status_transition"
        )
    if action == AnnouncementReport.Action.ARCHIVED:
        if status != AnnouncementReport.Status.RESOLVED:
            raise ValidationError({"action": ["Archiving is only possible when resolving a report."]})
        archive_announcement(moderator, report_obj.announcement_id)
        report_obj.action_taken = AnnouncementReport.Action.ARCHIVED
    report_obj.status = status
    if review_comments:
        report_obj.review_comments = review_comments
    report_obj.reviewed_by = moderator
    report_obj.reviewed_at = timezone.now()
    report_obj.save()
    return report_obj


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
def active_categories():
    return Category.objects.filter(is_active=True)


@transaction.atomic
def delete_or_deactivate_category(category):
    """A category in use is deactivated (existing announcements keep it); unused ones are deleted."""
    if category.announcements.exists():
        category.is_active = False
        category.save(update_fields=["is_active", "updated_at"])
        return "deactivated"
    category.delete()
    return "deleted"
