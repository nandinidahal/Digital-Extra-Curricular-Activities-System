"""
Business logic of the Achievements module.

PUBLIC INTEGRATION API
    visible_achievements(viewer)          verified achievements the viewer may see
    get_visible_achievement(viewer, id)   raises 404 / 401
    is_shareable(achievement)             verified + public (Social sharing rule)

Workflow
    create  -> PENDING (submitted) -> reviewer: VERIFIED | REJECTED | MORE_INFORMATION_REQUIRED
    REJECTED / MORE_INFORMATION_REQUIRED -> owner edits / adds evidence -> resubmit -> PENDING
    VERIFIED + material change (claim fields or evidence) -> PENDING again ("reverification")
Rules
    * reviewers are moderators (admin or coordinator) and can never review their own achievement
    * every status change writes an AchievementReview row (complete history)
    * only VERIFIED achievements can be featured; at most ACHIEVEMENT_MAX_FEATURED per user
    * evidence lives in private storage and is only downloadable by the owner and reviewers
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, TextField
from django.db.models.functions import Cast
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.exceptions import AuthenticationRequired, BusinessRuleViolation, NotOwner, ResourceNotFound
from common.files import delete_stored_file, reencode_image, safe_display_name
from common.permissions import MODERATOR_ROLES, is_admin, is_authenticated, is_moderator
from common.relationships import hidden_user_ids, is_blocked_between
from notifications.services import notify, notify_many

from .models import Achievement, AchievementEvidence, AchievementReview

logger = logging.getLogger("achievements")

Status = Achievement.VerificationStatus
Visibility = Achievement.Visibility
Decision = AchievementReview.Decision
Role = AchievementReview.ActorRole

EDITABLE_FIELDS = (
    "title", "description", "category", "achievement_type", "organization", "event_name",
    "related_announcement", "achievement_date", "location", "level", "position", "skills", "visibility",
)
# Changing any of these on a VERIFIED achievement sends it back for verification.
MATERIAL_FIELDS = {
    "title", "description", "category", "achievement_type", "organization", "event_name",
    "related_announcement", "achievement_date", "location", "level", "position",
}
REVIEWABLE_STATUSES = (Status.PENDING, Status.MORE_INFORMATION_REQUIRED)


class AchievementNotFound(ResourceNotFound):
    default_detail = "This achievement does not exist or is not available."
    default_code = "achievement_not_found"


class EvidenceNotFound(ResourceNotFound):
    default_detail = "This evidence file does not exist."
    default_code = "evidence_not_found"


# ---------------------------------------------------------------------------
# Querysets and access
# ---------------------------------------------------------------------------
def _base():
    return Achievement.objects.filter(user__is_active=True)


def visible_achievements(viewer):
    """Verified achievements visible to the viewer (owners also see their own private ones)."""
    queryset = _base().filter(verification_status=Status.VERIFIED)
    if not is_authenticated(viewer):
        return queryset.filter(visibility=Visibility.PUBLIC)
    queryset = queryset.filter(Q(visibility__in=[Visibility.PUBLIC, Visibility.MEMBERS_ONLY]) | Q(user=viewer))
    hidden = hidden_user_ids(viewer)
    return queryset.exclude(user_id__in=hidden) if hidden else queryset


def with_relations(queryset):
    return queryset.select_related("user", "user__profile", "category", "related_announcement", "verified_by")


def access_level(viewer, achievement):
    if not is_authenticated(viewer):
        return "visitor"
    if achievement.user_id == viewer.pk:
        return "owner"
    if is_moderator(viewer):
        return "reviewer"
    return "member"


def check_visible(viewer, achievement):
    level = access_level(viewer, achievement)
    if level in ("owner", "reviewer"):
        return level
    if not achievement.user.is_active or achievement.verification_status != Status.VERIFIED:
        raise AchievementNotFound()
    if achievement.visibility == Visibility.PRIVATE:
        raise AchievementNotFound()
    if achievement.visibility == Visibility.MEMBERS_ONLY and level == "visitor":
        raise AuthenticationRequired("Please log in to view this achievement.")
    if level == "member" and is_blocked_between(viewer, achievement.user_id):
        raise AchievementNotFound()
    return level


def get_achievement(achievement_id, *, lock=False, related=True):
    queryset = Achievement.objects.filter(pk=achievement_id)
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    if related:
        queryset = with_relations(queryset)
    achievement = queryset.first()
    if achievement is None:
        raise AchievementNotFound()
    return achievement


def get_visible_achievement(viewer, achievement_id):
    achievement = get_achievement(achievement_id)
    check_visible(viewer, achievement)
    return achievement


def is_shareable(achievement):
    return (
        achievement is not None
        and achievement.verification_status == Status.VERIFIED
        and achievement.visibility == Visibility.PUBLIC
        and achievement.user.is_active
    )


def _require_owner(user, achievement):
    if achievement.user_id != user.pk:
        raise NotOwner("You can only change your own achievements.")


def _require_reviewer(user, achievement):
    if not is_moderator(user):
        raise PermissionDenied("Only authorized reviewers can review achievements.")
    if achievement.user_id == user.pk:
        raise PermissionDenied("You cannot review your own achievement.", code="cannot_review_own")


def reviewer_ids(exclude=None):
    queryset = get_user_model().objects.filter(role__in=MODERATOR_ROLES, is_active=True)
    if exclude is not None:
        queryset = queryset.exclude(pk=exclude)
    return list(queryset.values_list("pk", flat=True))


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
ORDERINGS = {
    "newest": ("-achievement_date", "-created_at"),
    "oldest": ("achievement_date", "created_at"),
    "submitted": ("submitted_at",),
    "-submitted": ("-submitted_at",),
    "title": ("title",),
}


def apply_filters(queryset, params):
    text = (params.get("q") or "").strip()
    if text or params.get("skill"):
        queryset = queryset.annotate(skills_text=Cast("skills", TextField()))
    if text:
        queryset = queryset.filter(
            Q(title__icontains=text) | Q(description__icontains=text) | Q(organization__icontains=text)
            | Q(event_name__icontains=text) | Q(skills_text__icontains=text) | Q(category__name__icontains=text)
        )
    if params.get("category"):
        value = str(params["category"])
        queryset = queryset.filter(Q(category__slug=value) | (Q(category__id=value) if _is_uuid(value) else Q(pk__in=[])))
    for field in ("achievement_type", "level", "visibility"):
        if params.get(field):
            queryset = queryset.filter(**{field: params[field]})
    if params.get("status"):
        queryset = queryset.filter(verification_status=params["status"])
    if params.get("featured") is not None:
        queryset = queryset.filter(is_featured=params["featured"])
    if params.get("date_from"):
        queryset = queryset.filter(achievement_date__gte=params["date_from"])
    if params.get("date_to"):
        queryset = queryset.filter(achievement_date__lte=params["date_to"])
    if params.get("skill"):
        queryset = queryset.filter(skills_text__icontains=params["skill"])
    return queryset.order_by(*ORDERINGS.get(params.get("ordering") or "newest", ORDERINGS["newest"]), "id")


def _is_uuid(value):
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def validate_references(user, data, achievement=None):
    errors = {}
    category = data.get("category")
    if category is not None and (achievement is None or category.pk != achievement.category_id) and not category.is_active:
        errors["category"] = ["This category is no longer available."]
    announcement = data.get("related_announcement")
    if announcement is not None and (achievement is None or announcement.pk != achievement.related_announcement_id):
        from announcements.services import NotFound as AnnouncementNotFound
        from announcements.services import check_visible as announcement_visible

        try:
            announcement_visible(user, announcement)
        except (AnnouncementNotFound, AuthenticationRequired):
            errors["related_announcement"] = ["This announcement does not exist or is not available."]
    if errors:
        raise ValidationError(errors)


def _history(achievement, *, actor, role, previous, decision, comments=""):
    AchievementReview.objects.create(
        achievement=achievement, reviewer=actor, actor_role=role, previous_status=previous,
        new_status=achievement.verification_status, decision=decision, comments=comments,
    )


def _notify_reviewers(achievement, actor):
    notify_many(
        recipients=reviewer_ids(exclude=achievement.user_id), notification_type="achievement.submitted",
        actor=actor.pk, context={"title": achievement.title}, target_type="achievement", target_id=achievement.pk,
        metadata={"achievement_id": achievement.pk}, action_url=f"/achievements/review/{achievement.pk}",
        dedupe_key=f"achievement.submitted:{achievement.pk}:{achievement.submitted_at.isoformat()}",
    )


def _send_back_for_verification(achievement, actor, comments):
    """A verified achievement changed materially: it needs a new review and loses featured status."""
    previous = achievement.verification_status
    achievement.verification_status = Status.PENDING
    achievement.submitted_at = timezone.now()
    achievement.verified_at = None
    achievement.verified_by = None
    achievement.is_featured = False
    achievement.featured_at = None
    _history(achievement, actor=None, role=Role.SYSTEM, previous=previous, decision=Decision.REVERIFICATION_REQUIRED, comments=comments)
    _notify_reviewers(achievement, actor)


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------
@transaction.atomic
def create_achievement(user, data):
    validate_references(user, data)
    achievement = Achievement(user=user, submitted_at=timezone.now(), verification_status=Status.PENDING)
    for field in EDITABLE_FIELDS:
        if field in data:
            setattr(achievement, field, data[field])
    achievement.save()
    _history(achievement, actor=user, role=Role.OWNER, previous="", decision=Decision.SUBMITTED)
    _notify_reviewers(achievement, user)
    return achievement


@transaction.atomic
def update_achievement(user, achievement_id, data):
    achievement = get_achievement(achievement_id, lock=True)
    _require_owner(user, achievement)
    validate_references(user, data, achievement)
    changed = set()
    for field in EDITABLE_FIELDS:
        if field not in data:
            continue
        new = data[field]
        old = getattr(achievement, field)
        if field in ("category", "related_announcement"):
            if (new.pk if new else None) != (old.pk if old else None):
                changed.add(field)
        elif new != old:
            changed.add(field)
        setattr(achievement, field, new)
    if achievement.verification_status == Status.VERIFIED and changed & MATERIAL_FIELDS:
        _send_back_for_verification(achievement, user, "Changed: " + ", ".join(sorted(changed & MATERIAL_FIELDS)))
    achievement.save()
    return achievement


@transaction.atomic
def delete_achievement(user, achievement_id):
    achievement = get_achievement(achievement_id, lock=True, related=False)
    if achievement.user_id != user.pk and not is_admin(user):
        raise NotOwner("You can only delete your own achievements.")
    achievement.delete()  # evidence rows cascade; files are removed after commit (signals.py)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def max_evidence_files():
    return getattr(settings, "ACHIEVEMENT_MAX_EVIDENCE_FILES", 10)


def add_evidence(user, achievement_id, uploads):
    """`uploads` = [(UploadedFile, DetectedFile)] already validated by the serializer."""
    stored = []
    storage = AchievementEvidence._meta.get_field("file").storage
    try:
        with transaction.atomic():
            achievement = get_achievement(achievement_id, lock=True)
            _require_owner(user, achievement)
            existing = achievement.evidence.count()
            if existing + len(uploads) > max_evidence_files():
                raise ValidationError({"files": [f"An achievement can have at most {max_evidence_files()} evidence files."]})
            created = []
            for upload, detected in uploads:
                evidence = AchievementEvidence(
                    achievement=achievement, kind=detected.kind, content_type=detected.mime,
                    size=detected.size, original_name=safe_display_name(upload.name), uploaded_by=user,
                )
                if detected.kind == "image":
                    content, _w, _h, extension = reencode_image(upload, detected.format)  # strips EXIF/GPS
                    evidence.size = content.size
                    evidence.file.save(f"evidence.{extension}", content, save=False)
                else:
                    upload.seek(0)
                    evidence.file.save("evidence.pdf", upload, save=False)
                stored.append(evidence.file.name)
                evidence.save()
                created.append(evidence)
            if achievement.verification_status == Status.VERIFIED:
                _send_back_for_verification(achievement, user, "New evidence was added.")
                achievement.save()
    except Exception:
        for name in stored:
            delete_stored_file(storage, name)
        raise
    return achievement, created


@transaction.atomic
def delete_evidence(user, evidence_id):
    evidence = AchievementEvidence.objects.select_related("achievement").filter(pk=evidence_id).first()
    if evidence is None:
        raise EvidenceNotFound()
    achievement = get_achievement(evidence.achievement_id, lock=True)
    if achievement.user_id != user.pk:
        if is_moderator(user):
            raise NotOwner("Only the owner can remove evidence.")
        raise EvidenceNotFound()
    evidence.delete()  # file removed after commit by signals.py
    if achievement.verification_status == Status.VERIFIED:
        _send_back_for_verification(achievement, user, "Evidence was removed.")
        achievement.save()
    return achievement


def get_evidence_for_download(user, evidence_id):
    evidence = AchievementEvidence.objects.select_related("achievement").filter(pk=evidence_id).first()
    if evidence is None:
        raise EvidenceNotFound()
    if not (evidence.achievement.user_id == user.pk or is_moderator(user)):
        raise EvidenceNotFound()  # private evidence: existence is not revealed
    return evidence


def can_view_evidence(user, achievement):
    return is_authenticated(user) and (achievement.user_id == user.pk or is_moderator(user))


# ---------------------------------------------------------------------------
# Verification workflow
# ---------------------------------------------------------------------------
@transaction.atomic
def resubmit(user, achievement_id, note=""):
    achievement = get_achievement(achievement_id, lock=True)
    _require_owner(user, achievement)
    if achievement.verification_status not in (Status.REJECTED, Status.MORE_INFORMATION_REQUIRED):
        raise BusinessRuleViolation(
            "Only rejected achievements or those needing more information can be resubmitted.",
            code="invalid_status_transition",
        )
    previous = achievement.verification_status
    achievement.verification_status = Status.PENDING
    achievement.submitted_at = timezone.now()
    achievement.save()
    _history(achievement, actor=user, role=Role.OWNER, previous=previous, decision=Decision.RESUBMITTED, comments=note)
    _notify_reviewers(achievement, user)
    return achievement


DECISIONS = {
    "verify": (Status.VERIFIED, Decision.VERIFIED, "achievement.verified"),
    "reject": (Status.REJECTED, Decision.REJECTED, "achievement.rejected"),
    "request_information": (
        Status.MORE_INFORMATION_REQUIRED, Decision.MORE_INFORMATION_REQUIRED, "achievement.more_information_required"
    ),
}


@transaction.atomic
def review(reviewer, achievement_id, decision, comments=""):
    achievement = get_achievement(achievement_id, lock=True)
    _require_reviewer(reviewer, achievement)
    if achievement.verification_status not in REVIEWABLE_STATUSES:
        raise BusinessRuleViolation(
            f"A {achievement.verification_status} achievement cannot be reviewed now.", code="not_reviewable"
        )
    new_status, history_decision, notification_type = DECISIONS[decision]
    if decision in ("reject", "request_information") and not comments.strip():
        raise ValidationError({"comments": ["Please explain the decision to the user."]})
    previous = achievement.verification_status
    achievement.verification_status = new_status
    if new_status == Status.VERIFIED:
        achievement.verified_at = timezone.now()
        achievement.verified_by = reviewer
        achievement.rejection_reason = ""
    else:
        achievement.verified_at = None
        achievement.verified_by = None
        if new_status == Status.REJECTED:
            achievement.rejection_reason = comments
    achievement.save()
    _history(achievement, actor=reviewer, role=Role.REVIEWER, previous=previous, decision=history_decision, comments=comments)
    notify(
        recipient=achievement.user_id, actor=reviewer.pk, notification_type=notification_type,
        context={"title": achievement.title, "comments": comments[:300]},
        message='{actor} reviewed "{title}": {comments}' if comments else None,
        target_type="achievement", target_id=achievement.pk, metadata={"achievement_id": achievement.pk},
        action_url=f"/achievements/{achievement.pk}",
    )
    # The reviewers' "awaiting review" notifications for this submission are done.
    from notifications.models import Notification

    transaction.on_commit(
        lambda: Notification.objects.filter(
            notification_type="achievement.submitted", target_id=str(achievement.pk), is_read=False
        ).update(is_read=True, read_at=timezone.now())
    )
    return achievement


def review_queue():
    return with_relations(
        _base().filter(verification_status__in=REVIEWABLE_STATUSES)
    ).order_by("submitted_at", "id")


# ---------------------------------------------------------------------------
# Featured
# ---------------------------------------------------------------------------
def max_featured():
    return getattr(settings, "ACHIEVEMENT_MAX_FEATURED", 5)


@transaction.atomic
def set_featured(user, achievement_id, featured):
    achievement = get_achievement(achievement_id, lock=True)
    if achievement.user_id != user.pk and not is_admin(user):
        raise NotOwner("You can only feature your own achievements.")
    if featured == achievement.is_featured:
        return achievement
    if featured:
        if achievement.verification_status != Status.VERIFIED:
            raise BusinessRuleViolation("Only verified achievements can be featured.", code="not_verified")
        # Serialise concurrent "feature" requests of the same owner on the user row.
        get_user_model().objects.select_for_update().filter(pk=achievement.user_id).first()
        count = Achievement.objects.filter(user_id=achievement.user_id, is_featured=True).count()
        if count >= max_featured():
            raise BusinessRuleViolation(
                f"You can feature at most {max_featured()} achievements. Remove one first.", code="featured_limit_reached"
            )
        achievement.is_featured = True
        achievement.featured_at = timezone.now()
    else:
        achievement.is_featured = False
        achievement.featured_at = None
    achievement.save(update_fields=["is_featured", "featured_at", "updated_at"])
    if featured and achievement.user_id != user.pk:
        notify(
            recipient=achievement.user_id, actor=user.pk, notification_type="achievement.featured",
            context={"title": achievement.title}, target_type="achievement", target_id=achievement.pk,
            action_url=f"/achievements/{achievement.pk}", dedupe_key=f"achievement.featured:{achievement.pk}:{achievement.featured_at.isoformat()}",
        )
    return achievement


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def statistics(queryset):
    totals = queryset.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(verification_status=Status.PENDING)),
        verified=Count("pk", filter=Q(verification_status=Status.VERIFIED)),
        rejected=Count("pk", filter=Q(verification_status=Status.REJECTED)),
        more_information_required=Count("pk", filter=Q(verification_status=Status.MORE_INFORMATION_REQUIRED)),
        featured=Count("pk", filter=Q(is_featured=True)),
    )
    by_category = [
        {"category": row["category__name"] or "Uncategorised", "slug": row["category__slug"], "count": row["count"]}
        for row in queryset.order_by().values("category__name", "category__slug").annotate(count=Count("pk")).order_by("-count", "category__name")
    ]
    by_level = {row["level"]: row["count"] for row in queryset.order_by().values("level").annotate(count=Count("pk"))}
    by_type = {row["achievement_type"]: row["count"] for row in queryset.order_by().values("achievement_type").annotate(count=Count("pk"))}
    return {**totals, "by_category": by_category, "by_level": by_level, "by_type": by_type}
