# Profiles module

Personal profiles for the Digital Extra-Curricular Activities System (DEAS):
about-me information, profile picture, cover photo, privacy settings and a
dynamically calculated completion percentage.

Base URL: `/api/profiles/` · Auth: JWT (`Authorization: Bearer <access token>`) from the Accounts module.

---------------------------------------------------------------------------

## 1. Relationship with Accounts

| Accounts (`accounts.User`) owns | Profiles (`profiles.Profile`) owns |
|---|---|
| username, email, full_name, password, role, phone, country, date of birth, verification state | picture, cover, headline, bio, institution, education, interests, skills, location, links, privacy |

* `Profile.user` is a `OneToOneField(settings.AUTH_USER_MODEL, related_name="profile")`. No second user model; nothing from Accounts is copied.
* Username and full name in profile responses are read from the account at request time.
* **Never exposed** by this module: password hash, tokens, OTPs, e-mail, phone, date of birth, role, staff flags. Output serializers list their fields explicitly, so a new model field is never leaked by accident.
* The profile APIs reject attempts to send account fields (`role`, `email`, `password`, ...) with a 400.
* Reuses from Accounts: `success_response`, the global exception handler (same error JSON), `User.Role`.

## 2. Setup

```bash
pip install -r requirements.txt        # adds Pillow (needed by ImageField)
python manage.py makemigrations accounts   # ONLY if accounts/migrations has no 0001 yet (see Limitations)
python manage.py migrate               # creates profiles table AND back-fills profiles for existing users
python manage.py test profiles         # run the module tests
```

`.env` (all optional, defaults in brackets; see `.env.example`):

```
MEDIA_ROOT=media                 # [media/ next to manage.py]
MEDIA_URL=media/                 # [media/]
MEDIA_STORAGE_BACKEND=           # e.g. storages.backends.s3.S3Storage (production)
PROFILE_PICTURE_MAX_BYTES=2097152   # [2 MB]
PROFILE_COVER_MAX_BYTES=5242880     # [5 MB]
PROFILE_UPLOAD_RATE=30/hour         # upload/removal throttle per user
```

## 3. Database model (`profiles_profile`)

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | consistent with `accounts.User` |
| user | OneToOne → User | unique, CASCADE |
| profile_picture, cover_photo | ImageField | path only in DB; file in media storage; blank allowed |
| headline | varchar(120) | single line |
| bio | varchar(500) | newlines allowed |
| institution, field_of_study | varchar(150) | |
| education_level | varchar(20) | `high_school, diploma, undergraduate, postgraduate, doctorate, other` or empty (DB CHECK) |
| interests | JSON list | max 20 items × 40 chars |
| skills | JSON list | max 30 items × 40 chars |
| location | varchar(100) | "general location" only |
| website, portfolio_url | URL(200) | http/https only |
| linkedin_url, github_url | URL(200) | must be on linkedin.com / github.com |
| profile_visibility | varchar(20) | `public` (default), `members_only`, `private` (DB CHECK) |
| show_institution, show_education, show_interests, show_skills, show_location, show_social_links | bool, default true | |
| date_created, updated_at | datetime | |

Indexes: `profile_visibility`, `institution`, `field_of_study` (for the future discovery feature). The `user` one-to-one is already unique-indexed.

**Why JSON lists for interests and skills?** A JSON list works on PostgreSQL *and* on the SQLite option in your settings (Postgres `ArrayField` would break that), is validated in serializer + model, and on PostgreSQL supports containment filtering (`interests__contains=["Robotics"]`) and a GIN index. When a discovery/search feature is built, add a `GinIndex` in a new migration; a normalised `Tag` table is the next step if tag popularity/autocomplete is needed. Values are trimmed and de-duplicated case-insensitively.

## 4. Automatic profile creation

* `signals.py`: `post_save` on the user model creates the profile (`get_or_create`, so never a duplicate). It runs **inside the same transaction** as the user insert; `accounts.services.register_user` is atomic, so a profile failure rolls the whole registration back (no account without profile).
* Self-healing: `GET/PATCH /api/profiles/me/` creates a missing profile on first access.
* Existing users: migration `0002_create_missing_profiles` back-fills them on `migrate`; later at any time run
  `python manage.py create_missing_profiles [--dry-run]` (idempotent).

## 5. Privacy rules

| Viewer | public | members_only | private |
|---|---|---|---|
| Owner | full profile | full | full |
| Admin role (Accounts) | all content fields | all | all |
| Logged-in user | field-level filtered | field-level filtered | **403** `profile_private` |
| Visitor | field-level filtered | **401** `authentication_required` | **403** `profile_private` |

* Unknown user, user without profile, inactive or e-mail-unverified account → **404** `profile_not_found` (for non-owners/non-admins).
* Field-level flags remove keys **from the JSON on the server** (the key is absent, not `null`):
  `show_institution`→`institution` · `show_education`→`education_level`,`field_of_study` · `show_interests`→`interests` · `show_skills`→`skills` · `show_location`→`location` · `show_social_links`→`website`,`linkedin_url`,`github_url`,`portfolio_url`.
* Always visible when the profile itself is visible: username, full name, pictures, headline, bio, creation date.
* Coordinators get **no** special access. No friendship rules yet (see §11).
* `GET /api/profiles/<id>/` accepts an invalid/expired token as "visitor", so a stale token in the browser can't break a public page.

## 6. Profile completion

Computed on every request, never stored. Nine fields, each worth 1/9, rounded:
`profile_picture, bio, headline, institution, education_level, field_of_study, interests, skills, location`.
Cover photo and social links do **not** count. Returned only to the owner as
`profile_completion: {percentage, completed_fields[], missing_fields[]}`.

## 7. Images

* Endpoints take `multipart/form-data` with one file field named **`image`**.
* Allowed: JPEG, PNG, WebP — decided by the **real file content** (Pillow), not the extension or `Content-Type`. SVG, GIF, HTML, executables, truncated or corrupt files → 400.
* Limits: 2 MB (picture) / 5 MB (cover) by default, 25 megapixels, and an early `Content-Length` check (413) before the body is read.
* Every accepted image is **re-encoded**: EXIF/GPS/metadata stripped, rotation applied, downscaled (picture ≤ 1024 px, cover ≤ 2400×1200).
* Stored as `profiles/<user-uuid>/pictures|covers/<random-uuid>.<ext>`; the client file name is never used.
* Replace/remove deletes the old file **after the DB commit**; deleting a profile/user deletes its files.
* Responses contain absolute URLs (built from the request host, or the storage's own URL for S3/CDN).

### Local media
`MEDIA_ROOT` (default `Backend/media/`, git-ignored) is served by Django only when `DEBUG=True` (`config/urls.py`).

### Production media
* Don't serve media through Django: let nginx/Apache serve `MEDIA_ROOT`, or use object storage (`MEDIA_STORAGE_BACKEND=storages.backends.s3.S3Storage` + `pip install django-storages boto3` + that backend's own settings). No code change needed.
* Set a request-body limit at the proxy (e.g. nginx `client_max_body_size 6m;`).
* **Privacy caveat:** image URLs are unguessable (random UUID) but are *not* access-controlled once known. If a private profile's picture must stay secret even to someone holding the URL, use private storage with short-lived signed URLs.
* Use `NUM_PROXIES` / shared cache (Redis) as already documented for Accounts so throttling works across processes.

## 8. API

All success responses: `{"success": true, "message": "...", "data": {...}}`.
All errors: `{"success": false, "message": "...", "code": "...", "errors": {field: [msgs]}}`.

| Method | URL | Auth | Body | Success |
|---|---|---|---|---|
| GET | `/api/profiles/me/` | required | – | 200 `data.profile` (full) |
| PATCH | `/api/profiles/me/` | required | JSON, any of: `headline bio institution education_level field_of_study interests skills location website linkedin_url github_url portfolio_url` | 200 updated profile |
| PATCH | `/api/profiles/me/privacy/` | required | JSON, any of: `profile_visibility show_institution show_education show_interests show_skills show_location show_social_links` | 200 updated profile |
| POST | `/api/profiles/me/picture/` | required | multipart `image` | 200 updated profile |
| DELETE | `/api/profiles/me/picture/` | required | – | 200 updated profile (idempotent) |
| POST | `/api/profiles/me/cover/` | required | multipart `image` | 200 updated profile |
| DELETE | `/api/profiles/me/cover/` | required | – | 200 updated profile (idempotent) |
| GET | `/api/profiles/<user_id>/` | depends on visibility | – | 200 permitted profile |

Unknown or protected keys in a PATCH body → 400 (nothing is saved). Clear a text/link field by sending `""`, a list by sending `[]`.

### Example: `GET /api/profiles/me/`
```json
{
  "success": true, "message": "",
  "data": { "profile": {
    "id": "6f1c…", "user_id": "a3b9…", "username": "student1", "full_name": "Test Student",
    "profile_picture": "http://localhost:8000/media/profiles/a3b9…/pictures/9c1e….jpg",
    "cover_photo": null,
    "headline": "CS student", "bio": "I love robotics.",
    "institution": "DEAS University", "education_level": "undergraduate", "field_of_study": "Computer Science",
    "interests": ["Robotics"], "skills": ["Python"], "location": "Kathmandu",
    "website": "", "linkedin_url": "", "github_url": "https://github.com/someone", "portfolio_url": "",
    "privacy": {"profile_visibility": "public", "show_institution": true, "show_education": true,
                "show_interests": true, "show_skills": true, "show_location": true, "show_social_links": true},
    "profile_completion": {"percentage": 89, "completed_fields": ["…"], "missing_fields": ["profile_picture"]},
    "is_owner": true, "date_created": "2026-11-22T10:00:00Z", "updated_at": "2026-11-22T10:05:00Z"
  } }
}
```

### Example: `GET /api/profiles/<other user id>/` (skills hidden by the owner)
```json
{ "success": true, "message": "", "data": { "profile": {
    "user_id": "…", "username": "owner1", "full_name": "…",
    "profile_picture": null, "cover_photo": null, "headline": "…", "bio": "…",
    "institution": "…", "education_level": "undergraduate", "field_of_study": "…",
    "interests": ["…"], "location": "…", "website": "…", "linkedin_url": "…", "github_url": "…", "portfolio_url": "…",
    "is_owner": false, "date_created": "…" } } }
```
(`skills` is absent because `show_skills` is false. Owner-only `id`, `privacy`, `profile_completion`, `updated_at` are never sent to others.)

### Example: PATCH validation error (400)
```json
{ "success": false, "message": "Please correct the highlighted errors.", "code": "validation_error",
  "errors": { "github_url": ["Enter a valid GitHub URL (it must be on github.com)."],
              "role": ["This field cannot be set or changed here."] } }
```

### Example: React (axios) upload
```ts
const form = new FormData();
form.append("image", file);                                  // field name is "image"
const { data } = await api.post("/profiles/me/picture/", form);   // do NOT set Content-Type manually
```

### Error codes
| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | bad field / bad image (see `errors`) |
| 401 | `not_authenticated` / `authentication_required` | missing token / members-only profile as visitor |
| 403 | `profile_private` | private profile |
| 404 | `profile_not_found` / `not_found` | no such (visible) profile / malformed id |
| 405 | `method_not_allowed` | e.g. PUT, or writing to `/<user_id>/` |
| 413 | `file_too_large` | body far above the limit |
| 415 | `unsupported_media_type` | JSON sent to an upload endpoint |
| 429 | `throttled` | too many uploads |

CORS: no change needed — the existing `django-cors-headers` setup already allows `Authorization`, `Content-Type`, `PATCH` and `DELETE` for the origins in `CORS_ALLOWED_ORIGINS`.

## 9. Files

```
profiles/
  models.py  validators.py  services.py  serializers.py  views.py  urls.py
  permissions.py  authentication.py  throttles.py  exceptions.py  signals.py  admin.py  apps.py
  migrations/0001_initial.py  0002_create_missing_profiles.py
  management/commands/create_missing_profiles.py
  tests/  base.py  test_profile_creation.py  test_profile_retrieval.py  test_profile_update.py
          test_profile_images.py  test_profile_privacy.py  test_profile_permissions.py  test_profile_completion.py
```

## 10. Testing

```bash
export DJANGO_SECRET_KEY=test-key-not-for-production DB_ENGINE=sqlite   # quick run; use PostgreSQL for the real check
python manage.py test profiles          # this module
python manage.py test                   # everything, incl. accounts (profile signal now runs on user creation)
python manage.py makemigrations --check --dry-run   # confirms the hand-written migration matches the models
```
Tests write uploads to a temporary directory, never to your `MEDIA_ROOT`.

## 11. Integration with future modules

* **Friends:** add a `friend` level in `permissions.get_viewer_access`, then let `members_only`/`private` (or a new `friends_only`) consult it. Serializers need no change.
* **Discovery/search:** build it as its own endpoint reusing `ProfileViewSerializer` and a queryset filtered to `profile_visibility="public"` (or members-only for authenticated users) plus `is_active`/`is_email_verified`; add a GIN index for interests/skills then. Never search on fields whose `show_*` flag is off.
* **Social/messaging/achievements:** import `profiles.services.get_or_create_profile` or follow `user.profile`; show names via the profile serializer so privacy stays consistent.
