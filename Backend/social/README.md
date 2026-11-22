# Social module (`/api/social/`)

Lets students and other registered users share extra-curricular experiences and interact:
posts (with images), feeds, likes, comments and replies, comment likes, shares, visibility
control and content reporting. It adds **only** the Social app; Accounts and Profiles are
reused, not changed.

> **Status of verification.** The app is now installed (`INSTALLED_APPS`, `/api/social/`) and
> its 129 tests have been executed against PostgreSQL 16: all pass. (A test-isolation bug in
> `tests/base.py` - all tests shared one media folder - was fixed; each test now gets its own.)

## 0. Integration update (Friends, Notifications, Announcements, Achievements)

Added on top of the original module, with one **additive** migration (`0002_friends_visibility_and_resource_shares`:
new nullable/defaulted columns and a wider CHECK constraint; no data is changed or removed):

* **`friends` visibility**: friends of the author only (visitor 401, other members 404).
* **Blocking** (Friends module, either direction): the other person's posts, comments, replies and post list are invisible
  (404) and cannot be liked, commented, shared or reported. Admin moderation reads are not affected.
* **Feed** `GET /feed/` is now its own view: own + friends' + public/members-only posts + shared announcements/achievements;
  `?scope=friends` limits it to own + friends. `GET /posts/` keeps its old meaning.
* **Sharing announcements / achievements**: `POST /shares/` creates a post that *references* a published public announcement
  or a verified public achievement (`shared_type`, `shared_announcement`, `shared_achievement`, all `SET_NULL`). The
  original's visibility is re-checked on every read (`shared_resource.available`). Private and friends-only posts cannot be re-shared.
* **Notifications**: `post.liked`, `post.commented`, `comment.replied`, `post.shared` via `notifications.services.notify` (after commit).
* **Reports**: generic `POST /reports/`; moderators (admin/coordinator) list/review reports via `GET /reports/` and
  `PATCH /reports/<id>/` (`review_comments`, `action: content_removed`).
* **Author picture privacy**: a private profile's picture is no longer shown on posts (except to the author and admins).
* Shared code now comes from `common` (text validator, image content validation, pagination, user card).

See `../API_DOCUMENTATION.md` §2 for the request/response details. The sections below describe the original module;
where they say "not implemented" for the points above, this section supersedes them.

## 1. Dependencies on other modules

| Needs | From | How it is used |
|---|---|---|
| `AUTH_USER_MODEL` (`accounts.User`) | Accounts | `ForeignKey(settings.AUTH_USER_MODEL)` everywhere; `username`, `full_name`, `role`, `is_active` |
| JWT auth + `accounts.responses.success_response` + `accounts.exceptions.api_exception_handler` | Accounts | same success/error JSON envelope as the rest of the API |
| `Profile.profile_picture` (reverse `user.profile`) | Profiles | author card in every post/comment (`select_related("author__profile")`, no extra queries) |
| `profiles.authentication.OptionalJWTAuthentication` | Profiles | visitors and stale tokens are "visitor" on read endpoints |
| `profiles.validators.validate_image_upload` | Profiles | real-content image validation (Pillow), not duplicated |

**Prerequisite (resolved):** `accounts/migrations/0001_initial.py` was missing from the project;
it has now been generated, so `python manage.py migrate` works on an empty database.

## 2. Files changed outside `social/`

* `config/settings.py` – `"social"` in `INSTALLED_APPS`; `SOCIAL_*` settings; `social` logger.
* `config/urls.py` – `path("api/social/", include("social.urls"))`.
* `.env.example` – new optional `SOCIAL_*` variables.

`REST_FRAMEWORK` defaults are untouched: parsers/auth are set per view (JSON + multipart for posts).

## 3. Models (`social/models.py`)

| Model | Purpose / key constraints |
|---|---|
| `Post` | UUID pk, `author`, `content` (≤ 5000), `post_type`, `visibility`, `is_edited`, soft delete (`is_deleted`, `deleted_at`). Indexes: `(is_deleted, visibility, -created_at)` for the feed, `(author, is_deleted, -created_at)` for profile pages. CHECK constraints on the two choice fields. |
| `PostMedia` | One image per row; only the storage path is in PostgreSQL (never base64). `position` keeps order. |
| `PostLike` | **UNIQUE(post, user)**. |
| `Comment` | `parent_comment` (self FK), stored `depth`, soft delete. CHECK: top-level ⇔ depth 0. |
| `CommentLike` | **UNIQUE(comment, user)**. |
| `PostShare` | References `original_post`; `share_caption` ≤ 500. **UNIQUE(original_post, user)**. |
| `ContentReport` | `content_type` post/comment, `post` or `comment` FK, `reason`, `description`, `status`, `reviewed_by/at`. CHECK: exactly one target matching `content_type`. Partial UNIQUE (reporter, target) **while status is pending/reviewing**. |

Design decisions
* **UUID keys** like Accounts/Profiles (no enumeration, safe to expose).
* **Soft delete for posts and comments**: keeps report evidence, thread structure and counters
  consistent. Likes, shares and attachments are hard-deleted. Deleting a post also removes its image
  rows/files immediately (orphan cleanup); the text stays in the database for moderation but is never
  returned by the API.
* **Counts are never stored**: likes/comments/shares and `is_liked` are correlated subqueries, so they
  cannot drift and there is no write contention on a counter row. Subqueries (not JOINs) avoid row
  multiplication when three counts are computed together.
* **Concurrency**: duplicates are stopped by database constraints, not by "check then insert".
  Likes use `get_or_create` (idempotent), shares/reports catch `IntegrityError`. Multi-step writes
  (post + images) run in `transaction.atomic()`.
* No Redis/Celery/Elasticsearch is introduced. Throttle counters use Django's cache (same as Accounts;
  set `REDIS_URL` in production so counters are shared between processes).

## 4. Post types
`general`, `activity`, `achievement`, `experience`. An `achievement` post is **only a post**; no
official achievement record is created (that belongs to the Achievements module).

## 5. Visibility rules (enforced in `social/permissions.py` and `services.py`)

| Post visibility | Visitor | Other member | Author | Admin role |
|---|---|---|---|---|
| `public` | read | read + interact | all | all |
| `members_only` | **401** `authentication_required` | read + interact | all | all |
| `private` | **404** | **404** | all | **read** (detail, comments, author's posts) |

* Applied identically to detail, comments, replies, likes, shares, reports, feeds and user-post lists.
* Inaccessible content answers **404** (private existence is not revealed). A visitor asking for a
  members-only post gets **401** so the frontend can show "log in".
* The general feed excludes other people's private posts **even for admins**; admins only read them
  via detail/comments/user-posts. Admins have **no write override** (they moderate in Django admin).
* Soft-deleted posts and posts of deactivated accounts are invisible everywhere.
* `friends` visibility and blocking: see §0.

## 6. Text and media rules
* Text is **plain text**. Control characters, HTML tags (`<b>`, `<script>` …) and `javascript:` /
  `data:text/…` links are rejected with a 400, so stored text equals displayed text. The frontend must
  render it as text (React default; never `dangerouslySetInnerHTML`). Newlines are kept.
* Post ≤ 5000 chars, comment ≤ 2000, share caption ≤ 500, report description ≤ 1000.
* Images: JPEG/PNG/WebP, validated by content (Pillow), ≤ `SOCIAL_IMAGE_MAX_BYTES` (5 MB) each,
  ≤ `SOCIAL_MAX_IMAGES_PER_POST` (6) per post, ≤ 25 MP. Oversized multipart bodies are refused with 413
  from the `Content-Length` header before parsing. Images are **re-encoded** (EXIF/GPS removed,
  rotation applied, longest side ≤ 2048 px). Stored as `social/posts/<post_uuid>/<random>.<ext>`; the
  client file name is never used. Storage is Django's default storage: local `MEDIA_ROOT` in
  development, or set `MEDIA_STORAGE_BACKEND` (S3/GCS) in production, exactly as for Profiles.
* Media URLs in responses are absolute.
* Video is not supported.

## 7. Likes
`POST` is idempotent: `201` the first time, `200` if already liked (no duplicate). `DELETE` always
`200`. Both return `{"like_count": n, "is_liked": bool}`. Same for comments.

## 8. Comments
* Top-level comments are listed with `GET /posts/<id>/comments/` (oldest first, paginated, default 10).
* Replies are fetched per comment with `GET /comments/<id>/replies/` (paginated) so a response never
  contains unlimited nesting. Each comment carries `reply_count`.
* **Depth limit = 2** (`MAX_COMMENT_DEPTH` in `models.py`): comment (0) → reply (1) → reply to reply (2).
  Replying to depth 2 returns 400 `max_depth_reached`; the frontend should reply to the thread instead.
* Deleting a comment is a soft delete. If it still has live replies it is returned as a placeholder
  (`is_deleted: true`, empty `content`, `author: null`) so the thread keeps its shape; otherwise it
  disappears. Only the author can edit/delete (`403 not_owner` otherwise).

## 9. Sharing
A share is a row pointing at the original post (no copied content, so attribution is always the
original author and a share can never be shared again). One share per user per post (`409
already_shared`). Private posts cannot be shared (`400 post_not_shareable`). Counts appear as
`share_count`.

**How shares appear:** in this version a share is **not** injected into the global feed as its own
item. It appears in the sharer's `GET /me/shares/` (with the original post nested, or
`original_post: null, original_post_available: false` if the original was deleted/made private), and
raises the original post's `share_count`. Showing "X shared …" cards in the feed needs a product
decision about ordering/duplication and is listed under future work.

## 10. Reporting
`POST /posts/<id>/report/` and `/comments/<id>/report/` with `reason` ∈ `spam, harassment,
inappropriate, false_information, bullying, other` and optional `description`.
* Only content the reporter can see can be reported (else 404). Own content → 400.
* One active (pending/reviewing) report per user per item (`409 already_reported`); allowed again
  after the earlier report is resolved/dismissed.
* The response is a receipt without reporter/reviewer data; reports are not exposed in any API.
* Moderation: Django admin → *Content reports* (actions: under review / resolved / dismissed, which
  also stamp `reviewed_by` and `reviewed_at`; posts/comments have a "soft delete" action).

## 11. Authentication, permissions, throttling
* Reads: no token needed where visibility allows. A bad/expired token on a read = visitor.
* Every write needs `Authorization: Bearer <access token>`; otherwise `401`.
* The author is always `request.user`. Unknown/protected keys (`author`, `author_id`, `user`,
  `like_count`, `is_deleted`, …) are rejected with 400 instead of silently ignored.
* Per-user write limits (`SOCIAL_THROTTLE_RATES`): posts 30/h, comments 90/h, likes+shares 600/h,
  reports 20/h → `429` with `retry_after`. Reads and DELETEs are not throttled.

## 12. API

Base: `/api/social/`. UUIDs in paths. Success: `{"success": true, "message": "", "data": {...}}`.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `posts/` (alias `feed/`) | optional | General feed. Query: `page`, `page_size` (≤ 50), `post_type` |
| POST | `posts/` | yes | Create post (JSON or multipart; images in `images`) → 201 |
| GET | `posts/<id>/` | optional | Post detail |
| PATCH | `posts/<id>/` | owner | Edit `content`/`post_type`/`visibility`; may add `images` (multipart) |
| DELETE | `posts/<id>/` | owner | Soft delete (images removed) |
| DELETE | `posts/<id>/media/<media_id>/` | owner | **Added:** remove one attachment |
| GET | `users/<user_id>/posts/` | optional | A user's posts the viewer may see |
| GET | `me/posts/` | yes | Own posts, all visibilities |
| POST / DELETE | `posts/<id>/like/` | yes | Like / unlike |
| GET / POST | `posts/<id>/comments/` | optional / yes | List top-level comments / create |
| PATCH / DELETE | `comments/<id>/` | author | Edit / delete |
| POST | `comments/<id>/reply/` | yes | Reply |
| GET | `comments/<id>/replies/` | optional | **Added:** paginated replies of a comment |
| POST / DELETE | `comments/<id>/like/` | yes | Like / unlike comment |
| POST | `posts/<id>/share/` | yes | Share (`{"caption": "…"}` optional) → 201 |
| DELETE | `shares/<id>/` | sharer | Remove own share |
| GET | `me/shares/` | yes | Own shares |
| POST | `posts/<id>/report/`, `comments/<id>/report/` | yes | Report → 201 |

Changes from the brief: `feed/`, `posts/<id>/media/<media_id>/` and `comments/<id>/replies/` were
added (needed for the media-removal and bounded-nesting requirements); the response uses the
project's existing envelope instead of a bare object.

### Example: create a post with images
```
POST /api/social/posts/            (multipart/form-data)
Authorization: Bearer <access>
content=Participated in a college event today!
post_type=activity
visibility=public
images=@a.jpg   images=@b.webp
```
```json
{
  "success": true,
  "message": "Post created.",
  "data": {
    "post": {
      "id": "6f1c…",
      "author": {"id": "…", "username": "student123", "full_name": "Example Student",
                 "profile_picture": "https://host/media/profiles/…/pictures/….jpg"},
      "content": "Participated in a college event today!",
      "post_type": "activity",
      "visibility": "public",
      "media": [{"id": "…", "url": "https://host/media/social/posts/…/….jpg",
                 "width": 1024, "height": 768, "position": 0}],
      "like_count": 0, "comment_count": 0, "share_count": 0,
      "is_liked": false, "is_owner": true, "is_edited": false,
      "created_at": "2026-11-22T10:00:00Z", "updated_at": "2026-11-22T10:00:00Z"
    }
  }
}
```

### Example: paginated list
```json
{"success": true, "message": "",
 "data": {"results": [ {…post…} ],
          "pagination": {"count": 42, "page": 1, "page_size": 10, "total_pages": 5,
                         "next": "https://host/api/social/posts/?page=2", "previous": null}}}
```

### Example: comment (and a deleted placeholder)
```json
{"id": "…", "post_id": "…", "parent_comment_id": null, "depth": 0,
 "author": {"id": "…", "username": "bob", "full_name": "Bob", "profile_picture": null},
 "content": "Great job!", "like_count": 3, "reply_count": 2, "is_liked": false,
 "is_owner": false, "is_edited": false, "is_deleted": false,
 "created_at": "…", "updated_at": "…"}
```

### Errors
`{"success": false, "message": "…", "code": "…", "errors": {"field": ["…"]}}`

| Status | `code` | When |
|---|---|---|
| 400 | `validation_error` | bad/empty text, HTML, bad image, unknown field, too many images |
| 400 | `max_depth_reached` / `post_not_shareable` / `cannot_report_own_content` | rule violations |
| 401 | `authentication_required` / `not_authenticated` | members-only as visitor / missing token |
| 403 | `not_owner` | editing/deleting someone else's content |
| 404 | `post_not_found` / `comment_not_found` / `share_not_found` / `media_not_found` / `user_not_found` | missing, deleted or not visible |
| 409 | `already_shared` / `already_reported` | duplicates |
| 413 | `file_too_large` | request body larger than the image limits |
| 429 | `throttled` | rate limit (`retry_after` seconds) |

## 13. Testing
```bash
cd Backend
# PostgreSQL (project default), needs a user allowed to create test databases:
python manage.py makemigrations --check --dry-run      # must report "No changes detected"
python manage.py migrate
python manage.py test social -v 2
# quick local run without PostgreSQL:
DB_ENGINE=sqlite python manage.py test social
# whole project (make sure Accounts/Profiles still pass):
python manage.py test
```
The migration `social/migrations/0001_initial.py` was written by hand; `makemigrations --check` is
the quickest way to confirm it matches the models (if it prints changes, run
`python manage.py makemigrations social` and keep the generated file instead).

Tests (in `social/tests/`): posts & media, feed/ordering/pagination/N+1 query-count, post likes,
comments & depth, comment likes, shares, visibility matrix, reports & privacy, authentication,
impersonation, ownership and throttling. Uploaded files go to a temporary directory.

## 14. Future integration points
* **Friends:** add a `friends_only` visibility value and a "friend" viewer level in
  `permissions.visibility_filter` / `check_post_visible` (single place); add a migration for the CHECK
  constraint and `Post.Visibility`.
* **Notifications:** emit events from `services.like_post`, `create_comment`, `share_post` (all writes
  go through `services.py`).
* **Achievements:** `post_type="achievement"` is only a label; an Achievements module can link a
  record to a `Post.id` later.
* **Messaging/Announcements:** none required.
* **Admin module:** reuse `ContentReport` and the status workflow; `services.delete_post/delete_comment`
  are the moderation actions.
* **Profile privacy:** an author's profile picture is shown on their public posts even if their profile
  is private; add a check in `serializers.author_payload` if that should change.
* **Feed shares:** render shares as feed items (see §9).

## 15. Known limitations
* Test suite not yet executed in the authoring environment (see top).
* Content moderation is manual (admin); no automatic text/image scanning.
* Rate limits use the Django cache; configure a shared cache (e.g. Redis) for multi-process production.
* Feed is chronological only (no ranking, search or hashtags).
