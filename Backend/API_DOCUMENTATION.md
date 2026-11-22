# DEAS API documentation: Common, Social, Announcements, Achievements, Notifications

Accounts, Profiles, Friends and Messaging are documented in their own `README.md` files.
This document covers the five modules built or extended in this round.

## Conventions (all modules)

* **Auth:** `Authorization: Bearer <access token>` (SimpleJWT from `/api/auth/login/`).
  "Optional" means visitors are allowed; a missing/expired token on those endpoints is treated as a visitor.
* **IDs:** UUIDs everywhere.
* **Success envelope:** `{"success": true, "message": "...", "data": {...}}`
* **Error envelope:** `{"success": false, "message": "...", "code": "machine_code", "errors": {"field": ["..."]}}`
  (`429` also has `retry_after` in seconds).
* **Pagination** (`?page=&page_size=`, max 100; Social max 50):
  `data = {"results": [...], "pagination": {"count", "page", "page_size", "total_pages", "next", "previous"}}`
* **Input is strict:** unknown or protected keys (`author`, `user`, `status` on PATCH, `verification_status`,
  `is_featured`, `published_at`, …) are rejected with `400` instead of being silently ignored.
* **Text** is plain text: HTML tags, control characters and `javascript:`/`data:` links → `400`. Render as text in React.
* **Roles:** `admin` and `coordinator` are **moderators** (review achievements, handle reports).
  Only `admin` manages announcement categories.

| Status | Meaning in this API |
|---|---|
| 200 | read / update / idempotent repeat (e.g. liking again) |
| 201 | created |
| 400 | validation error or business rule (`code` says which) |
| 401 | `not_authenticated` (no/invalid token) or `authentication_required` (members-only content for a visitor) |
| 403 | `not_owner`, `permission_denied`, `cannot_review_own` |
| 404 | missing **or not visible to you** (private content never reveals that it exists) |
| 409 | duplicates: `already_reported`, `already_shared` |
| 413 | `file_too_large` (body larger than the upload limit) |
| 429 | `throttled` |
| 503 | `/api/health/` when the database is unreachable |

Delete endpoints answer `200` with a message (project convention, so the frontend can always parse JSON).

---

## 1. Common

### `GET /api/health/`  (no auth)
`200 {"data": {"status": "ok"|"degraded", "checks": {"database": "ok", "cache": "ok"}, "time": "..."}}`
`503` with `code: "service_unavailable"` when the database is down. Never returns credentials, versions or env values.

---

## 2. Social (`/api/social/`)

Unchanged endpoints (posts, media, comments, likes, post shares, `me/*`) keep the contract in `social/README.md`.
**What changed / was added:**

### Visibility values
`public` · `members_only` (visitors → 401) · **`friends`** (new: author's friends only; visitors → 401, others → 404) · `private` (404 for others).
Blocks (either direction) hide the other person's posts, comments and profile post list (404) and block likes/comments/shares/reports.

### `GET /api/social/feed/`  (optional auth)
Query: `scope=all|friends` (friends = own + friends' posts, needs login), `post_type`, `shared_type=announcement|achievement`, `page`, `page_size`.
Own posts + friends' posts + public/members-only posts + shared announcements/achievements, newest first. Constant number of queries per page.

### Post representation (new fields)
```json
{"id": "…", "author": {"id","username","full_name","profile_picture"}, "content": "Join us!",
 "visibility": "public", "shared_type": "announcement",
 "shared_resource": {"type": "announcement", "id": "…", "available": true,
                     "data": {"id","title","short_description","category","activity_type","location",
                              "start_datetime","end_datetime","registration_deadline","cover_image"}},
 "like_count": 0, "comment_count": 0, "share_count": 0, "is_liked": false, "is_owner": false, ...}
```
`shared_resource` is `null` for normal posts. If the original is deleted, unpublished, unverified, made private, or its
owner blocks you: `{"type": "...", "id": null, "available": false, "data": null}`.
`author.profile_picture` is `null` when the author's profile is **private** (except for the author and admins).

### `POST /api/social/shares/`  (auth)
```json
{"resource_type": "post" | "announcement" | "achievement", "resource_id": "<uuid>",
 "caption": "optional ≤500", "visibility": "public|members_only|friends"}
```
* `post` → creates a `PostShare` (same as `POST posts/<id>/share/`) → `201 {"share": {...}}`. Private and friends-only posts → `400 post_not_shareable`.
* `announcement` → only **published public** announcements; `achievement` → only **verified public** achievements.
  Creates a post that **references** the original → `201 {"post": {...}}`.
* Errors: `404` not visible, `400 post_not_shareable`, `409 already_shared`, `400` `visibility: private`.
  Share-posts cannot get images; their caption can be edited/emptied with `PATCH posts/<id>/`.

### `POST /api/social/reports/`  (auth)
`{"content_type": "post"|"comment", "object_id": "<uuid>", "reason": "spam|harassment|inappropriate|false_information|bullying|other", "description": "optional"}`
→ `201 {"report": {"id","content_type","reason","status","created_at"}}`. Errors: `404`, `400 cannot_report_own_content`, `409 already_reported`.
(`POST posts/<id>/report/` and `comments/<id>/report/` still work.)

### `GET /api/social/reports/?status=pending`  (moderators) · `GET|PATCH /api/social/reports/<id>/`  (moderators)
PATCH body: `{"status": "reviewing|resolved|dismissed", "review_comments": "…", "action": "none"|"content_removed"}`.
`content_removed` (only with `resolved`) soft-deletes the post/comment. Transitions: pending → reviewing/resolved/dismissed; reviewing → resolved/dismissed; final states are final (`400 invalid_status_transition`).
Members → `403`.

### Notifications emitted
`post.liked` (once per user/post, even after unlike+like), `post.commented` (grouped per post while unread),
`comment.replied` (grouped per parent comment), `post.shared` (posts, announcements, achievements). Never for your own actions or across blocks.

---

## 3. Announcements

### Who can do what

| Action | Visitor | Member | Author | Moderator (admin/coordinator) |
|---|---|---|---|---|
| List/read published **public** | ✔ | ✔ | ✔ | ✔ |
| Read published **members-only** | 401 | ✔ | ✔ | ✔ |
| Read **private** / **draft** / **archived** | 404 | 404 | ✔ | ✔ |
| Create, search, bookmark, report | 401 | ✔ | ✔ | ✔ |
| Edit (PATCH), publish, restore | 401 | 403/404 | ✔ | 403 |
| Archive, delete | 401 | 403/404 | ✔ | ✔ (author is notified) |
| Moderate reports | 401 | 403 | 403 | ✔ |
| Manage categories | 401 | 403 | 403 | admin only |

Lifecycle: `draft → published → archived → (restore) draft`. Drafts may be incomplete; **publishing validates everything**.

### Announcement object

Card (lists): `id, title, slug, short_description, category{id,name,slug}, activity_type, organizer_name, location,
start_datetime, end_datetime, registration_deadline, cover_image, status, visibility, author{id,username,full_name,profile_picture},
is_bookmarked, is_owner, is_edited, published_at, created_at, updated_at`

Detail adds: `description, registration_link, eligibility_criteria, requirements, organizer_email, organizer_phone,
contact_information, contact_details_hidden, online_link, requires_login_for_online_link` (+ `show_contact_details`, `archived_at` for author/moderators).

Privacy of organizer data: `organizer_email`, `organizer_phone`, `contact_information` are `null` for visitors, `null` for members
unless the author enabled `show_contact_details`, always present for the author/moderators. `online_link` is `null` for visitors
(`requires_login_for_online_link: true`).

### Writable fields (POST / PATCH; JSON or multipart)
`title` (required, ≤200, single line) · `short_description` (≤300) · `description` (≤10000) · `category` (UUID, must be active when chosen) ·
`activity_type` `physical|online|hybrid` · `organizer_name` · `organizer_email` (email) · `organizer_phone` (digits/+/-/spaces) ·
`contact_information` · `show_contact_details` (bool) · `location` · `online_link` (http/https) · `start_datetime` ·
`end_datetime` · `registration_deadline` · `registration_link` (http/https) · `eligibility_criteria` · `requirements` ·
`visibility` `public|members_only|private` · `cover_image` (file: JPEG/PNG/WebP ≤5 MB, re-encoded) · `remove_cover_image` (bool, PATCH) ·
`status` (**POST only**: `draft` default | `published`).

Always validated: end ≥ start; registration deadline ≤ start; end requires start.
Validated on publish: title, short + full description, active category, start time, event not already over,
physical/hybrid → `location`, online/hybrid → `online_link`. All missing items are returned together in `errors`.

### Endpoints

| Method & URL | Auth | Body / query | Success | Errors |
|---|---|---|---|---|
| `GET /api/announcements/public/` | none | `category` (slug or id), `activity_type`, `when=upcoming\|past\|ongoing`, `registration_open`, `ordering` | 200 page of cards (published + public only) | 400 bad filter |
| `GET /api/announcements/` | yes | all filters below | 200 page of cards visible to you | 401 |
| `POST /api/announcements/` | yes | fields above | 201 `{"announcement": detail}` | 400, 401, 413 |
| `GET /api/announcements/search/` | yes | `q` + filters | 200 page | 401, 400, 429 |
| `GET /api/announcements/me/` `me/drafts/` `me/published/` `me/archived/` | yes | filters | 200 own announcements | 401 |
| `GET /api/announcements/<id>/` | optional | — | 200 `{"announcement": detail}` | 401 members-only, 404 |
| `GET /api/announcements/slug/<slug>/` | optional | — | same | same |
| `PATCH /api/announcements/<id>/` | author | any writable field except `status` | 200 detail (`is_edited` true after publication) | 400 (`announcement_archived`), 403 `not_owner`, 404 |
| `DELETE /api/announcements/<id>/` | author / moderator | — | 200 | 403, 404 |
| `POST /api/announcements/<id>/publish/` | author | — | 200 detail (idempotent) | 400 validation / `invalid_status_transition`, 403, 404 |
| `POST /api/announcements/<id>/archive/` | author / moderator | — | 200 detail | 400, 403, 404 |
| `POST /api/announcements/<id>/restore/` | author | — | 200 detail (archived → draft) | 400, 403, 404 |
| `POST /api/announcements/<id>/bookmark/` | yes | — | 201 new / 200 existing `{"is_bookmarked": true}` | 400 not published, 404 |
| `DELETE /api/announcements/<id>/bookmark/` | yes | — | 200 `{"is_bookmarked": false}` (idempotent) | 401 |
| `GET /api/announcements/bookmarks/` | yes | — | 200 page of `{"id","announcement_id","created_at","available","announcement": card\|null}` | 401 |
| `POST /api/announcements/<id>/report/` | yes | `{"reason": "spam\|misleading\|inappropriate\|fraudulent\|harassment\|incorrect\|other", "description"}` | 201 receipt | 400 own, 404, 409 `already_reported`, 429 |
| `GET /api/announcements/reports/?status=` | moderator | — | 200 page of reports | 401, 403 |
| `GET /api/announcements/reports/<id>/` | moderator | — | 200 | 403, 404 |
| `PATCH /api/announcements/reports/<id>/` | moderator | `{"status": "reviewed\|resolved\|rejected", "review_comments", "action": "none\|archived"}` | 200 | 400 transition, 403, 404 |
| `GET /api/categories/` | none | `include_inactive=true` (admins) | 200 `{"results": [{"id","name","slug","description","is_active"}]}` | — |
| `POST /api/categories/` | admin | `{"name", "slug"?, "description"?, "is_active"?}` | 201 | 400 duplicate, 403 |
| `PATCH /api/categories/<id>/` | admin | same, partial | 200 | 400, 403, 404 |
| `DELETE /api/categories/<id>/` | admin | — | 200 `{"result": "deleted"\|"deactivated"}` (in use → deactivated) | 403, 404 |

Filters (`GET /`, `search/`, `me/*`): `q`, `category`, `activity_type`, `location`, `organizer`, `start_from`, `start_to`,
`deadline_from`, `deadline_to`, `published_from`, `published_to` (ISO datetimes), `when`, `registration_open=true`,
`status` (own lists; admins on `GET /`), `visibility`, `ordering=newest|oldest|start|-start|deadline|title|updated`.

Notifications: `announcement.created` (author, draft saved), `announcement.published` (author's friends, once per announcement,
never for private), `announcement.updated` (bookmarkers, only for date/time/location/link/type changes, grouped),
`announcement.archived` (bookmarkers; author when a moderator archives), `announcement.reminder` (bookmarkers, by cron).

---

## 4. Achievements

### Workflow
`create → pending → (reviewer) verified | rejected | more_information_required`;
`rejected / more_information_required → (owner) resubmit → pending`;
`verified` + a **material** change (title, description, category, type, organization, event, related announcement,
date, location, level, position, or evidence added/removed) → back to `pending`, featured flag removed.
Visibility and skills edits are not material. Uploading evidence never verifies anything.
Reviewers = admin/coordinator; nobody can review their own achievement. Every change is written to the history.

### Visibility

| Viewer | sees |
|---|---|
| visitor | verified + public |
| member | verified + public/members-only (not blocked users) |
| owner | everything of their own (`/me/`) |
| reviewer | everything (needed for review) |
Evidence, history, rejection reason and `verified_by` are shown only to the owner and reviewers.

### Achievement object
`id, user{id,username,full_name,profile_picture}, title, description, category{id,name,slug,...}, achievement_type, organization,
event_name, related_announcement{id,title,available}|null, achievement_date, location, level, position, skills[], visibility,
verification_status, is_featured, featured_at, verified_at, is_owner, created_at, updated_at`
+ for owner/reviewers: `submitted_at, rejection_reason, verified_by, evidence[{id,kind,original_name,content_type,size,download_url,created_at}]` (detail only).

### Writable fields (JSON)
`title` (required) · `description` · `category` (UUID, active) · `achievement_type` `award|certificate|competition|participation|project|publication|scholarship|volunteering|leadership|other` ·
`organization` · `event_name` · `related_announcement` (UUID of an announcement you can see) · `achievement_date` (required, not in the future) ·
`location` · `level` `institutional|local|national|international|other` · `position` · `skills` (≤20 unique strings ≤40 chars) ·
`visibility` `public|members_only|private`.

### Endpoints

| Method & URL | Auth | Body / query | Success | Errors |
|---|---|---|---|---|
| `GET /api/achievements/` | optional | `category, achievement_type, level, visibility, featured, date_from, date_to, skill, ordering` | 200 page (verified & visible) | 400 |
| `POST /api/achievements/` | yes | fields above | 201 `{"achievement": ...}` (pending) | 400, 401 |
| `GET /api/achievements/me/` | yes | filters + `status` | 200 own, any status | 401 |
| `GET /api/achievements/users/<user_id>/` | optional | filters | 200 that user's verified & visible | 404 unknown/blocked |
| `GET /api/achievements/featured/` | optional | `user_id` | 200 featured & visible | 400 bad uuid |
| `GET /api/achievements/search/` | yes | `q` + filters | 200 | 401 |
| `GET /api/achievements/stats/` | yes | `scope=platform` (reviewers) | 200 `{"scope", "statistics": {"total","pending","verified","rejected","more_information_required","featured","by_category":[...],"by_level":{},"by_type":{}}}` | 403 platform for members |
| `GET /api/achievements/<id>/` | optional | — | 200 | 401 members-only, 404 |
| `PATCH /api/achievements/<id>/` | owner | fields, partial | 200 (message says if re-verification started) | 400, 403, 404 |
| `DELETE /api/achievements/<id>/` | owner / admin | — | 200 (evidence files removed) | 403, 404 |
| `POST /api/achievements/<id>/evidence/` | owner | multipart `files` (repeat) or `file`; JPEG/PNG/WebP ≤5 MB, PDF ≤10 MB, ≤10 per achievement | 201 `{"evidence": [...]}` | 400 type/size/count, 403, 404, 413 |
| `DELETE /api/achievements/evidence/<evidence_id>/` | owner | — | 200 | 403 (reviewer), 404 |
| `GET /api/achievements/evidence/<evidence_id>/download/` | owner/reviewer JWT **or** `?token=` from `download_url` (10 min) | — | 200 file, `attachment`, `no-store` | 401, 404 |
| `POST /api/achievements/<id>/resubmit/` | owner | `{"note"?}` | 200 (pending) | 400 `invalid_status_transition` |
| `GET /api/achievements/pending/` | reviewer | `status=pending\|more_information_required` | 200 queue, oldest first, own excluded | 403 |
| `POST /api/achievements/<id>/verify/` | reviewer | `{"comments"?}` | 200 | 400 `not_reviewable`, 403 (`cannot_review_own`) |
| `POST /api/achievements/<id>/reject/` | reviewer | `{"comments"}` **required** | 200 | 400, 403 |
| `POST /api/achievements/<id>/request-information/` | reviewer | `{"comments"}` **required** | 200 | 400, 403 |
| `GET /api/achievements/<id>/history/` | owner / reviewer | — | 200 `{"history": [{"decision","previous_status","new_status","comments","actor_role","reviewer","created_at"}]}` | 404 |
| `POST /api/achievements/<id>/feature/` | owner / admin | — | 200 | 400 `not_verified` / `featured_limit_reached` (default 5), 403 |
| `DELETE /api/achievements/<id>/feature/` | owner / admin | — | 200 | 403 |
| `GET /api/achievement-categories/` | none | — | 200 `{"results": [...]}` | — |

Notifications: `achievement.submitted` (all reviewers except the owner), `achievement.verified` / `.rejected` /
`.more_information_required` (owner, with the reviewer's comment, also e-mailed), `achievement.featured` (owner, when an admin features it).

---

## 5. Notifications

### Notification object
```json
{"id": "…", "type": "post.liked", "category": "social", "title": "New like", "message": "Bob liked your post.",
 "actor": {"id","username","full_name","profile_picture"} | null, "metadata": {"post_id": "…", "count": 1},
 "target_type": "post", "target_id": "…", "action_url": "/social/posts/…",
 "is_read": false, "read_at": null, "created_at": "…", "updated_at": "…", "expires_at": null}
```
`action_url` is always an internal frontend path. `metadata.count` > 1 means a grouped notification (e.g. 3 new messages).

Types: `account.welcome, account.email_verified, account.password_changed*, account.security_alert*,
friend_request.received, friend_request.accepted, friend_request.rejected, friend.removed, message.received,
post.liked, post.commented, post.shared, comment.replied, announcement.created, announcement.published,
announcement.updated, announcement.archived, announcement.reminder, achievement.submitted, achievement.verified,
achievement.rejected, achievement.more_information_required, achievement.featured, system.announcement, system.maintenance`
(* = essential, cannot be disabled). Categories: `account, friends, messages, social, announcements, achievements, system`.

### Endpoints (all need auth; only your own notifications are ever visible: others' ids → 404)

| Method & URL | Body / query | Success |
|---|---|---|
| `GET /api/notifications/` | `is_read=true\|false`, `category`, `type`, `page`, `page_size` | 200 page, newest first (expired hidden) |
| `GET /api/notifications/unread-count/` | — | 200 `{"unread_count": n}` |
| `GET /api/notifications/<id>/` | — | 200 `{"notification": ...}` |
| `POST /api/notifications/<id>/read/` | — | 200 `{"notification", "unread_count"}` |
| `POST /api/notifications/<id>/unread/` | — | 200 `{"notification", "unread_count"}` |
| `POST /api/notifications/read-all/` | — | 200 `{"updated": n, "unread_count": 0}` |
| `DELETE /api/notifications/<id>/` | — | 200 `{"unread_count"}` |
| `DELETE /api/notifications/clear/` | `read_only=true` keeps unread | 200 `{"deleted": n, "unread_count"}` |
| `GET /api/notifications/preferences/` | — | 200 `{"preferences": {"friend_requests","social_interactions","messages","announcements","achievements","system_notifications","email_notifications","realtime_notifications","updated_at","always_on":[...]}}` |
| `PATCH /api/notifications/preferences/` | any of the 8 booleans | 200; unknown key or non-boolean → 400 |

### WebSocket `ws://<host>/ws/notifications/`
Authenticate exactly like Messaging: `new WebSocket(url, ["deas.jwt", accessToken])` (preferred), or a one-time ticket from
`POST /api/messaging/ws-ticket/` → `?ticket=`. Origin must be an allowed frontend origin.
Server events: `connection.ready {user_id, unread_count}`, `notification.new {notification, unread_count}`,
`notification.updated {notification, unread_count}` (grouped item bumped), `notification.read {notification_ids|all, unread_count}`,
`notification.deleted {notification_ids|all, unread_count}`, `notification.count_updated {unread_count}`, `pong`, `auth.expired`.
Client → server: `{"type": "ping"}`, `{"type": "count"}`. Close codes: `4401` not authenticated / token expired, `4403` inactive.
Each socket joins only `notifications.user.<its own JWT user id>`; client input can never choose a group.

### E-mail
Sent over the project SMTP settings, only for: `account.password_changed`, `account.security_alert`, `achievement.verified`,
`achievement.rejected`, `achievement.more_information_required`, `announcement.reminder`, `system.*`; only to verified addresses;
only if the user's `email_notifications` is on (security notices ignore it); only when `NOTIFICATIONS_EMAIL_ENABLED`.
`email_status` is `sent` only after the SMTP backend accepted the message; failures are `failed` and retried by
`python manage.py send_notification_emails` (max 3 attempts, never twice). Push notifications are **not** implemented.
