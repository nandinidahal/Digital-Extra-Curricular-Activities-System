# Announcements module

Student-to-student announcements: every authenticated student can publish; everybody can discover,
search, bookmark and share **live** announcements; only the author can edit or delete. Self-contained
Django app (`announcements/`), **not yet mounted** in `config/urls.py` (see "Integration").

## Visibility rules (single source of truth: `selectors.py`)
| State | Condition | Who can see it |
|---|---|---|
| draft | `status=draft` | author only (everyone else: 404) |
| scheduled | published, `published_at` in the future | author only until the time arrives |
| published | published, `published_at <= now`, not expired | every authenticated student |
| expired | `expires_at <= now` | author only; leaves every public list |

Write access: `PUT/PATCH/DELETE` → author only → **403** for any other student who can see it
(**404** if they cannot see it, e.g. a draft). The author is never read from the payload
(`published_by`, `author`, `user` are ignored); it is `request.user`.
Featured / important flags: only users where the existing `User.is_coordinator` is true (coordinator/admin);
students sending `true` get 400.

## Endpoints (all require `Authorization: Bearer <access token>`; mounted under `/api/`)
| Method & path | Purpose |
|---|---|
| `GET /announcements/` | all live announcements (filters, search, sort, pagination) |
| `POST /announcements/` | create (JSON or multipart) → 201 + detail |
| `GET /announcements/{id}/` | full details (404 if not visible) |
| `PUT/PATCH /announcements/{id}/` | author only → 200 / 403 |
| `DELETE /announcements/{id}/` | author only → 204 / 403 |
| `GET /announcements/landing/?limit=6` | previews for `featured, latest, recommended, upcoming_events, upcoming_deadlines, important` |
| `GET /announcements/latest/` | chronological (newest first) |
| `GET /announcements/featured/` · `/important/` | curated lists |
| `GET /announcements/recommended/` | ranked by the scoring algorithm (adds `score`) |
| `GET /announcements/upcoming/` | events not over yet, soonest first |
| `GET /announcements/deadlines/` | deadlines not passed, nearest first |
| `GET /announcements/search/?q=` | search (`q` required) |
| `GET /announcements/categories/` | active categories (not paginated) |
| `GET /announcements/my-announcements/?state=` | own, any state (`draft/scheduled/published/expired`) |
| `GET /announcements/drafts/` | own drafts |
| `GET /announcements/authors/{user_id}/` | one student's live announcements |
| `GET /announcements/bookmarks/` | own bookmarks only |
| `GET/POST/DELETE /announcements/{id}/bookmark/` | status / add (201, 200 if already) / remove (204) |
| `GET /announcements/{id}/share/` | `id`, `share_id`, `detail_url`, `shared_url` (live announcements only) |
| `GET /announcements/shared/{share_id}/` | open by non-guessable UUID (still needs login) |
| `GET /announcements/{id}/attachment/` | private attachment download (same visibility as the announcement) |

### Query parameters (every list; invalid values → 400)
`q`, `category` (id or slug), `author` (user id), `event=upcoming|past`, `deadline=upcoming`,
`featured=true|false`, `important=true|false`, `activity_type=physical|online|hybrid`,
`published_from/published_to` (YYYY-MM-DD, publication date), `event_from/event_to` (events overlapping the range),
`sort=latest|oldest|relevant|event_date|deadline|bookmarks`, `page`, `page_size` (max 50, default 12).
Responses are `{count, next, previous, results}`.

### Write fields
`title`(≥3) `full_description`(≥5) `category`(id, active) required; optional `short_description`
(derived from the description when empty), `activity_name`, `keywords`, `activity_type`, `country`, `location`,
`start_date`, `end_date`, `deadline`, `image`, `attachment`, `status` (`draft` default | `published`),
`publish_at` (schedule), `expires_at`, `is_featured`/`is_important` (coordinators), `remove_image`, `remove_attachment`.
Dates cannot be set in the past; `end_date` needs `start_date` and cannot precede it. "event date" in the
requirements = `start_date` (`event_date` is returned as an alias). Files: image JPG/PNG/WEBP ≤ 5 MB;
attachment PDF/JPG/PNG/WEBP ≤ 10 MB; extension, size, declared type **and real content** are checked.
Cover images use the default storage (public MEDIA); attachments use private storage and are only served by the
download endpoint.

## Search
`apply_search` splits `q` into ≤ 8 terms; **every** term must appear (case-insensitive substring, so partial
words work) in at least one of: title, activity_name (event name), keywords, category name, location, country,
short/full description. A weighted `search_score` (title 5, event name 3, keywords 3, category 2, others 1)
orders results for `sort=relevant`; ties → newest, then id. Pure ORM → parameterised, injection-safe.
Combines with every filter, sort and pagination.

## Ranking (`ranking.py`)
```
score = 0.30·recency + 0.25·category + 0.20·event + 0.15·deadline + 0.10·engagement  (+0.05 if featured)
```
All components are in [0,1].
* **recency** `0.5^(age_days/7)` – new announcements start near 1, so they are never buried for lack of engagement.
* **category** the viewer's own bookmark history (share of bookmarks per category ÷ their top category). No
  bookmarks → neutral 0.5 for everything. Other students' data is never used.
* **event** 1 while running/today, linear to 0 at 30 days; 0 if past or no event date.
* **deadline** 1 on the day, linear to 0 at 14 days; 0 if passed or none.
* **engagement** `ln(1+bookmarks)/ln(1+max bookmarks in the pool)`; real bookmark rows only.

Ties: newest `published_at`, then highest id. Candidate pool (bounded to 1000): published in the last 90 days,
or featured, or event ≤ 30 days away, or deadline ≤ 14 days away. Weights/horizons are constants at the top of
`ranking.py`; each component is a separate function so it can be replaced.

## Real example (captured from the test run)
`POST /api/announcements/` as alice → `201`
```json
{"id": 2, "title": "Inter-college Football Cup", "short_description": "Teams of 7. Register before the deadline.",
 "activity_name": "College Cup 2026", "category": {"id": 3, "name": "Competitions", "slug": "competitions", "description": ""},
 "author": {"id": 2, "username": "alice", "full_name": "Alice Sharma"}, "image_url": null,
 "published_at": "2026-11-21T03:10:03.456907+05:45", "event_date": "2026-12-03", "start_date": "2026-12-03",
 "end_date": null, "deadline": "2026-11-27", "location": "Dhangadhi Stadium", "is_featured": false,
 "is_important": false, "bookmark_count": 0, "is_bookmarked": false, "state": "published",
 "full_description": "...", "is_owner": true, "can_edit": true, "attachment": null,
 "share_id": "aa93e324-a250-4ce1-a677-48ce6004e538", "share_url": "http://testserver/api/announcements/2/"}
```
`PATCH /api/announcements/2/` as bob → `403 {"detail": "You can only modify your own announcements."}`
`POST /api/announcements/2/bookmark/` as bob → `201 {"bookmarked": true, "bookmark_count": 1}`
`GET /api/announcements/recommended/` → `{"count": 2, ..., "results": [{"id": 2, ..., "score": 0.855714}, ...]}`

## Running
```
python manage.py migrate
python manage.py seed_announcement_categories     # 12 default categories, idempotent
python manage.py test announcements                # PostgreSQL (needs CREATEDB permission)
python manage.py test announcements --settings=announcements.test_settings   # SQLite, no server needed
```
Tests mount the URLs through `announcements/tests/urls.py`, so they run without touching `config/urls.py`.

## Integration (not done, by design)
1. `config/urls.py`: add `path("api/", include("announcements.urls"))`. (`'announcements'` is already in `INSTALLED_APPS`.)
2. `python manage.py migrate` – `social.0001_initial` already depends on `announcements.0001_initial` (provided).
3. Run `seed_announcement_categories` once per database. It is a command rather than a data migration because the
   `friends` tests create `Category(name="Sports")` and would collide with a seeded row.
4. Serve `MEDIA_URL` in development if cover images must load; optionally set `ANNOUNCEMENT_PRIVATE_ROOT` (default
   `<BASE_DIR>/private_media`) or a `STORAGES["announcements"]` alias; optional `ANNOUNCEMENT_MAX_IMAGE_SIZE` /
   `ANNOUNCEMENT_MAX_ATTACHMENT_SIZE`.
5. Other modules already rely on this app: `social` imports `Announcement`/`AnnouncementStatus` and filters
   `status=published`; `friends` creates `Announcement(...)` with `published_by`, `short_description`,
   `full_description`, `activity_name`, `activity_type`, `country`, `start_date`, `end_date`; `achievements`
   imports `announcements.pagination.StandardPagination`. These names are kept. Note `social` only checks
   `status`, so it would accept a scheduled/expired announcement – tighten with `selectors.active_q()` when integrating.
6. Roles: featured/important use `User.is_coordinator`. Interest-based ranking can later also read the social
   profile's `interests` by extending `ranking.category_affinity`.
