# DEAS backend: Digital Extra-Curricular Activities System

*From Screen Time to Life Time: Activity → Attendance → Achievement → Certificate → Skill → Portfolio → Livelihood*

Django 5.2 · Django REST Framework · SimpleJWT · PostgreSQL · Channels (WebSockets) · SMTP e-mail.

| Module | URL prefix | Status | Docs |
|---|---|---|---|
| accounts | `/api/auth/` | existing | `accounts/README.md` |
| profiles | `/api/profiles/` | existing | `profiles/README.md` |
| friends | `/api/friends/` | existing | `friends/README.md` |
| messaging | `/api/messaging/`, `ws/messaging/` | existing | `messaging/README.md` |
| **common** | `/api/health/` | **new** | `common/README.md` |
| **social** | `/api/social/` | existing, **extended** | `social/README.md` §0 |
| **announcements** | `/api/announcements/`, `/api/categories/` | **new** | `announcements/README.md` |
| **achievements** | `/api/achievements/`, `/api/achievement-categories/` | **new** | `achievements/README.md` |
| **notifications** | `/api/notifications/`, `ws/notifications/` | **new** | `notifications/README.md` |

Endpoint-by-endpoint reference for the five modules: **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)**.

---

## 1. What was found in the existing code (and the decisions it led to)

* `accounts.User` (UUID pk, `role` = user/coordinator/admin, `is_email_verified`), SimpleJWT, a global exception
  handler and `success_response` envelope → reused everywhere; no second user/auth system.
* Friends exposes a public service API (`are_friends`, `get_hidden_user_ids`, …) and **after-commit signals**;
  Messaging also publishes after-commit signals; Channels + a JWT WebSocket middleware already exist.
  → Notifications listens to those signals; the notification socket reuses the same middleware.
* A complete **Social** app already existed (posts, comments, likes, shares, reports; 129 tests; applied migration).
  It was **extended, not recreated**: friends-only visibility, blocking, notifications, sharing of announcements and
  achievements, moderation API, privacy-aware author pictures. One additive migration.
* Profiles already had content-based image validation; it was moved to `common.validators` and Profiles/Social delegate to it,
  with identical messages and behaviour.
* UUID primary keys are the house style → every new model uses UUIDs (`common.models.BaseModel`).

## 2. Relationships between new and existing modules

```
accounts.User ─┬─< announcements.Announcement (author, CASCADE) ─┬─< AnnouncementBookmark (UNIQUE user+announcement)
               │        └─> Category (PROTECT)                   └─< AnnouncementReport (one active per reporter)
               ├─< achievements.Achievement (user, CASCADE) ──┬─< AchievementEvidence (private files)
               │        ├─> AchievementCategory (PROTECT)      └─< AchievementReview (history, append-only)
               │        └─> announcements.Announcement (related_announcement, SET_NULL)
               ├─< social.Post ──> Announcement / Achievement (shared_*, SET_NULL, reference only)
               ├─< notifications.Notification (recipient CASCADE, actor SET_NULL; target stored as type+id strings)
               └── notifications.NotificationPreference (1:1)
friends.Friendship / UserBlock  → read through friends.services (via common.relationships) by every new module
```
Dependency direction (no import cycles): `common ← notifications ← {announcements ← achievements} ← social`.
Notifications imports nothing from the business modules; they call `notifications.services.notify()` explicitly.

## 3. Changes made to existing modules (smallest possible, all covered by the existing tests)

| File | Change | Why |
|---|---|---|
| `config/settings.py` | registered `common`, `announcements`, `achievements`, `notifications`; new `*_THROTTLE_RATES`, limits, `STORAGES["private"]`, loggers | app registration and configuration |
| `config/urls.py` | 6 new `include()`s | routing |
| `config/asgi.py` | routes `messaging` **+** `notifications` sockets through the existing JWT middleware/origin check | real-time notifications without touching messaging |
| `accounts/signals.py` (new), `accounts/services.py` | 3 lines: emit `email_verified` / `password_changed` after commit | welcome / security notifications (same signal pattern as Friends/Messaging) |
| `profiles/validators.py` | `validate_image_upload` delegates to `common.validators.validate_image_content` (same messages) | one shared implementation |
| `social/*` | see `social/README.md` §0; migration `0002_friends_visibility_and_resource_shares` (additive) | friends/blocks/notifications/sharing/moderation |
| `social/tests/test_posts.py`, `test_reports.py` | 2 assertions updated: `friends` visibility is now valid; moderators can list reports | the spec deliberately changed these behaviours |
| `templates/emails/notification.{txt,html}` (new) | notification e-mail templates | SMTP notifications |
| `.env.example` | new optional variable names (no secrets) | configuration |

`requirements.txt` needs **no new packages**: everything uses Django, DRF, SimpleJWT, Channels, channels-redis and Pillow,
which were already listed. Celery was deliberately not introduced (see notifications/README.md).

## 4. Setup

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then set DJANGO_SECRET_KEY, DB_*, EMAIL_*, REDIS_URL ...
createdb deas_db                                         # PostgreSQL
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver                               # HTTP + WebSockets (daphne is installed)
```
Production: `daphne -b 0.0.0.0 -p 8000 config.asgi:application`, `DJANGO_DEBUG=False`, `REDIS_URL` set (required for the
channel layer and shared throttling), private object storage via `PRIVATE_STORAGE_BACKEND` / `MESSAGING_PRIVATE_STORAGE_BACKEND`.

### Migrating an existing database
Back up first (`pg_dump`), then `python manage.py migrate`. The new migrations are:
`announcements 0001, 0002 (seed 14 categories)`, `achievements 0001, 0002 (seed 11 categories)`, `notifications 0001`,
`social 0002` (adds columns with defaults and widens one CHECK constraint; **no** data is changed or dropped).
Nothing deletes or rewrites existing rows; seeds only insert categories that do not exist yet.
This was verified by migrating a database containing legacy posts at the old schema: all rows were preserved.

### Scheduled jobs (cron or any scheduler)
```
*/15 * * * *  python manage.py send_announcement_reminders   # reminders to bookmarkers (idempotent)
*/5  * * * *  python manage.py send_notification_emails      # retry failed notification e-mails
15 3 * * *    python manage.py cleanup_notifications         # expired + old read notifications
30 3 * * 0    python manage.py cleanup_orphan_media          # dry run; add --delete to remove
```

### Frontend integration notes (React + Vite)
* Send `Authorization: Bearer <access>`; for visitor pages (public announcements, achievements, posts) you can call the same
  endpoints without a token. On `401` with `code: "authentication_required"` show "log in to see this".
* Uploads: `multipart/form-data` (`cover_image`, evidence `files`). Evidence links come as short-lived `download_url`s; use them directly in `<a>`/`<img>`.
* Notifications: open one `new WebSocket(\`${WS}/ws/notifications/\`, ["deas.jwt", access])` per tab; on reconnect, refetch
  `GET /api/notifications/` and `unread-count/`. Navigate with `notification.action_url`.

## 5. Folder structure (new and changed parts)

```
Backend/
├── API_DOCUMENTATION.md            README.md         .env.example     requirements.txt
├── config/        settings.py* urls.py* asgi.py*
├── accounts/      signals.py (new) services.py*
├── profiles/      validators.py*
├── common/        models.py validators.py files.py signing.py permissions.py relationships.py serializers.py
│                  pagination.py throttles.py exceptions.py views.py urls.py testing.py
│                  management/commands/cleanup_orphan_media.py   tests/
├── social/        models.py* permissions.py* services.py* serializers.py* views.py* urls.py* validators.py* pagination.py*
│                  migrations/0002_friends_visibility_and_resource_shares.py   tests/test_integration_features.py
├── announcements/ models.py services.py serializers.py views.py urls.py category_urls.py throttles.py signals.py admin.py
│                  management/commands/send_announcement_reminders.py   migrations/0001, 0002   tests/
├── achievements/  models.py services.py serializers.py views.py urls.py category_urls.py throttles.py signals.py admin.py
│                  migrations/0001, 0002   tests/
├── notifications/ models.py types.py services.py receivers.py realtime.py consumers.py routing.py emails.py
│                  serializers.py views.py urls.py throttles.py admin.py
│                  management/commands/{send_notification_emails,cleanup_notifications}.py   tests/
└── templates/emails/notification.txt, notification.html (new)
(* = existing file, modified)
```

## 6. Testing report (actually executed)

Environment: Python 3.13, Django 5.2.19, **PostgreSQL 16**, Redis 7 (local), Linux.

| Run | Result |
|---|---|
| Baseline before any change (existing 638 tests) | **638 passed** |
| Full suite after the work: `python manage.py test --parallel 4` | **850 passed, 0 failed** |
| — common / social / announcements / achievements / notifications | 39 / 151 (129 existing + 22 new) / 64 / 40 / 47 |
| WebSocket + integration tests with the **Redis** channel layer (`REDIS_URL` set) | 45 passed (incl. messaging WebSockets) |
| `makemigrations --check` | no changes detected |
| Upgrade path: old schema with legacy posts → `migrate` | all rows preserved, categories seeded |
| Live server (Daphne): health, categories, login, create + publish announcement, public listing, 401 for anonymous writes, notification WebSocket (JWT subprotocol, ping/pong), anonymous and wrong-origin sockets rejected, messaging socket unaffected | all as expected, no server errors |
| `ruff` (E, F, W, B) on all new/changed code | clean |

What the tests cover, per module: file validation (real content, MIME/extension mismatch, executables, SVG, PDF scripts, size,
decompression bombs), safe names/paths; announcement creation/ownership/lifecycle/visibility/search/filters/bookmarks/reports/
moderation/notifications/reminders/cover cleanup; achievement submission/evidence (private storage, signed downloads)/
verification workflow/history/re-verification/featured limit/privacy/statistics; notification rules (self, blocks, preferences,
dedupe, grouping, metadata, after-commit), API ownership, e-mail delivery and failure/retry, WebSocket auth/isolation/expiry;
integration: friend request/accept/reject/cancel/remove, messages (grouped, muted, read), password change, e-mail verification,
post like, announcement publication, achievement verification, private resources across modules, blocks across Social and Messaging.

**Not tested here:** delivery through a real external SMTP server (tests use Django's in-memory backend; failures are simulated),
S3/object storage backends, and load/performance beyond query-count assertions.

## 7. Completion report

| Module | Models | APIs | Permissions | Integration | Tests |
|---|---|---|---|---|---|
| Common | Completed (abstract only) | Completed (health) | Completed | Completed | Completed |
| Social | Completed (extended) | Completed | Completed | Completed | Completed |
| Announcements | Completed | Completed | Completed | Completed | Completed |
| Achievements | Completed | Completed | Completed | Completed | Completed |
| Notifications | Completed | Completed | Completed | Completed | Completed |

## 8. Known limitations / decisions to revisit
* Push notifications (mobile/web push) are not implemented, only designed for (`notifications/README.md`).
* E-mails are sent synchronously right after commit (low volume); if volume grows, move `send_notification_email` to a worker.
* Search uses `ILIKE` on indexed tables (fine for thousands of rows); switch to PostgreSQL full-text search if needed.
* Announcement publication notifies the author's **friends** (configurable: `ANNOUNCEMENT_PUBLISH_AUDIENCE=none`).
  There is no "follow a category" feature, so no wider audience rule was invented.
* Active content inside *compressed* PDF object streams is not decompressed and scanned; evidence PDFs are only served as
  downloads (`attachment`, `nosniff`, private), never rendered inline by the API.
