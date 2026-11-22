# Announcements module (`/api/announcements/`, `/api/categories/`)

User-based: **any authenticated user** can create, publish and manage their own announcements; visitors browse
published public ones without logging in; moderators (admin/coordinator) can archive/delete and handle reports.
Full endpoint reference: `../API_DOCUMENTATION.md` §3.

## Models
| Model | Notes |
|---|---|
| `Category` | UUID, name (case-insensitive unique), slug, description, `is_active`. 14 defaults seeded by migration `0002`. `PROTECT` from announcements: a used category is deactivated, never deleted. |
| `Announcement` | all requested fields + `requirements`, `contact_information`, `show_contact_details`, `archived_at/by`, `is_edited`. DB CHECKs: status/visibility/activity type values, end ≥ start, deadline ≤ start, published ⇒ `published_at`. Indexes for listing, author pages, category, dates. |
| `AnnouncementBookmark` | UNIQUE(user, announcement). |
| `AnnouncementReport` | reasons/status as specified, `action_taken`, `reviewed_by/at`, `review_comments`; one **active** (pending/reviewed) report per reporter+announcement (partial unique). |

## Rules worth knowing
* The author is always `request.user`; `author`, `status` (on PATCH), `slug`, `published_at`, `is_edited` … are rejected.
* Drafts may be incomplete. Publishing (create with `status=published` or `POST /publish/`) validates everything and returns all gaps at once.
* Event-date policy: registration deadline must be on or before the start; an event that already ended cannot be published.
* Status changes only through `publish` / `archive` / `restore` (archived → draft). Archived announcements cannot be edited until restored.
* Visitors never see organizer e-mail/phone/contact text or the online meeting link; members see contact details only when the author enabled `show_contact_details`.
* Blocks hide announcements both ways for logged-in users. Private items answer 404 to everyone else, including through search, bookmarks and UUID guessing.
* Text search (`q`) is login-only (`/search/`, `GET /`); the public list only offers category/type/date filters.
* Covers: JPEG/PNG/WebP via `common.validators`, re-encoded (EXIF stripped), stored as `announcements/covers/<id>/<random>.<ext>`; old covers removed after commit.

## Notifications (through `notifications.services`, after commit)
`announcement.created` → author (draft saved) · `announcement.published` → author's friends, once per announcement (not for private; `ANNOUNCEMENT_PUBLISH_AUDIENCE=none` disables) ·
`announcement.updated` → bookmarkers, only for start/end/deadline/location/link/type/registration-link changes, grouped while unread ·
`announcement.archived` → bookmarkers, and the author when a moderator archived it · `announcement.reminder` → bookmarkers, from cron:

```
*/15 * * * *  python manage.py send_announcement_reminders     # idempotent
```

## Integration
Achievements may reference an announcement (`SET_NULL`); Social can share published public announcements (`SET_NULL`).
Other modules use `services.visible_announcements`, `check_visible`, `get_visible_announcement`, `is_shareable`.
