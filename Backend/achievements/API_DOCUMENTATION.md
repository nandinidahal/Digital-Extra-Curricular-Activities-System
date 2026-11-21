# Achievement Management API

Base URL: `/api/` &nbsp;|&nbsp; Auth: `Authorization: Bearer <access token>` on **every** endpoint (401 otherwise).

There is no achievement search and no global achievement list. Other people's achievements are
found only through their profile (`/api/users/{user_id}/achievements/`).

## Visibility rules (enforced in the backend)

| Viewer | PUBLIC achievement | PRIVATE achievement |
|---|---|---|
| Owner | view, edit, delete, download | view, edit, delete, download |
| Other authenticated user | view, download | **404** (same as "does not exist") |

Modifying or deleting someone else's PUBLIC achievement returns **403**; their PRIVATE one returns **404**.
New achievements default to `private`.

## Endpoints

| Method | URL | Purpose |
|---|---|---|
| GET | `/api/achievements/categories/` | Active categories (for the form dropdown) |
| POST | `/api/achievements/` | Create (multipart) |
| GET | `/api/achievements/my/` | Own achievements, paginated |
| GET | `/api/achievements/my/{id}/` | Own achievement detail |
| GET | `/api/achievements/{id}/` | Detail: owner, or anyone if PUBLIC |
| PUT / PATCH | `/api/achievements/{id}/` | Update (owner only) |
| DELETE | `/api/achievements/{id}/` | Delete (owner only) |
| GET | `/api/users/{user_id}/achievements/` | A user's PUBLIC achievements (profile view), paginated |
| GET | `/api/achievements/{id}/documents/{document_id}/download/` | Secure document download |

Pagination (list endpoints): `?page=2&page_size=5` (default 12, max 50). Response:
`{"count": 15, "next": "...", "previous": null, "results": [...]}`.

## Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string ≤200 | yes | |
| `category` | integer (category id) | yes | active categories only |
| `description` | string | no | |
| `issuing_organization` | string ≤200 | yes | |
| `achievement_date` | `YYYY-MM-DD` | yes | not in the future, not before 1900 |
| `certificate_number` | string ≤100 | no | owner-only in responses |
| `location` | string ≤200 | no | |
| `visibility` | `public` \| `private` | no | default `private` |
| `certificate` | file | see below | one file; on update it **replaces** the current certificate |
| `supporting_documents` | file (repeat the key for several) | no | always **appended** |
| `remove_document_ids` | integer (repeat the key / JSON list) | no | update only; ids of documents to delete |

`user`/`owner` in a request body is ignored; the owner is always the authenticated user.

At create time at least one document (`certificate` or `supporting_documents`) is required
(`ACHIEVEMENT_REQUIRE_DOCUMENT=false` removes this). An update never leaves an achievement without
documents if it touches them, and never touches documents it does not mention.

### File rules

* Types: PDF, JPG, JPEG, PNG, WEBP. Extension, declared content type **and actual file contents** are checked
  (a renamed `.exe`/`.html` is rejected).
* Max size per file: `ACHIEVEMENT_MAX_UPLOAD_SIZE` bytes (default 5 MB). Max documents per achievement:
  `ACHIEVEMENT_MAX_DOCUMENTS` (default 6). At most one certificate per achievement.
* Files are stored under a random name in private storage (`ACHIEVEMENT_PRIVATE_ROOT`, outside `MEDIA_ROOT`,
  or the `STORAGES["achievements"]` backend if you define one). The API never returns a file path or storage URL.

## Uploading files (multipart/form-data)

```bash
curl -X POST http://localhost:8000/api/achievements/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=National Science Olympiad" \
  -F "category=1" \
  -F "description=Gold medal in the national round" \
  -F "issuing_organization=Ministry of Education" \
  -F "achievement_date=2026-03-14" \
  -F "certificate_number=NSO-2026-001" \
  -F "location=Kathmandu" \
  -F "visibility=public" \
  -F "certificate=@cert.pdf" \
  -F "supporting_documents=@photo1.jpg" \
  -F "supporting_documents=@photo2.png"
```

Browser: `const fd = new FormData(); fd.append("title", ...); files.forEach(f => fd.append("supporting_documents", f));`
Do not set the `Content-Type` header yourself; let the browser add the multipart boundary.

## Response objects

Owner view (`/my/`, `/my/{id}/`, create/update responses, and `/{id}/` when you own it):

```json
{
  "id": 7,
  "title": "National Science Olympiad",
  "category": {"id": 1, "name": "Academic Achievement", "slug": "academic-achievement", "description": "..."},
  "description": "Gold medal in the national round",
  "issuing_organization": "Ministry of Education",
  "achievement_date": "2026-03-14",
  "certificate_number": "NSO-2026-001",
  "location": "Kathmandu",
  "visibility": "public",
  "documents": [
    {
      "id": 12, "document_type": "certificate", "document_name": "cert",
      "original_filename": "cert.pdf", "content_type": "application/pdf", "size": 48211,
      "uploaded_at": "2026-11-21T10:15:00+05:45",
      "download_url": "http://localhost:8000/api/achievements/7/documents/12/download/"
    }
  ],
  "owner": {"id": 3, "full_name": "Alice", "username": "alice"},
  "created_at": "2026-11-21T10:15:00+05:45",
  "updated_at": "2026-11-21T10:15:00+05:45"
}
```

Public view (other users, profile list) is the same without `visibility`, `certificate_number` and `updated_at`.

## Examples

Update only some fields (JSON is fine when no files are sent):

```bash
curl -X PATCH http://localhost:8000/api/achievements/7/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"visibility": "private", "location": "Pokhara"}'
```

Replace the certificate, add one more document, remove document 13:

```bash
curl -X PATCH http://localhost:8000/api/achievements/7/ -H "Authorization: Bearer $TOKEN" \
  -F "certificate=@renewed.pdf" -F "supporting_documents=@extra.png" -F "remove_document_ids=13"
```

Download (saves as the original file name):

```bash
curl -L -OJ -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/achievements/7/documents/12/download/
```

Download headers: `Content-Disposition: attachment; filename="cert.pdf"`, `Content-Type: application/pdf`,
`X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`.

## Errors

| Status | When | Body |
|---|---|---|
| 400 | validation failure | `{"title": ["This field is required."], "certificate": ["File is too large (6.2 MB). The maximum allowed size is 5 MB."]}` |
| 401 | missing/invalid/expired token | `{"detail": "Authentication credentials were not provided."}` |
| 403 | modifying/deleting another user's PUBLIC achievement | `{"detail": "You can only modify your own achievements."}` |
| 404 | not found, **or** another user's PRIVATE achievement/document, or inactive user profile | `{"detail": "Not found."}` |
| 404 | file missing from storage | `{"detail": "The document file could not be found."}` |
| 405 | e.g. `GET /api/achievements/` (no global list) | |

Example validation errors: `{"certificate": ["Unsupported file type. Allowed types: PDF, JPG, JPEG, PNG and WEBP."]}`,
`{"certificate": ["The file is not a valid PDF document."]}`,
`{"achievement_date": ["Achievement date cannot be in the future."]}`,
`{"remove_document_ids": ["Document(s) not found on this achievement: [99]."]}`,
`{"supporting_documents": ["An achievement can have at most 6 documents."]}`,
`{"certificate": ["Upload a certificate or at least one supporting document."]}`.
