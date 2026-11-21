# User Profile & Settings API

Base URL: `/api/profile/`. Every endpoint needs `Authorization: Bearer <access token>` (the existing
JWT from `POST /api/auth/login/`) except `POST /api/profile/reactivate/`. Errors use DRF's standard
shapes: `{"detail": "..."}` or `{"field": ["message"]}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/profile/me/` | Own complete profile + own achievements (public and private) |
| PUT / PATCH | `/api/profile/me/update/` | Update name, username, DOB, bio, phone, country |
| POST | `/api/profile/me/upload-picture/` | Upload or replace the profile picture |
| DELETE | `/api/profile/me/remove-picture/` | Remove the profile picture |
| GET / PATCH | `/api/profile/me/settings/` | Privacy settings |
| GET | `/api/profile/me/account/` | Account information and status |
| POST | `/api/profile/me/email/change/` | Start a verified e-mail change |
| POST | `/api/profile/me/email/confirm/` | Finish it with the 6-digit code |
| POST | `/api/profile/me/deactivate/` | Deactivate own account (reversible) |
| POST | `/api/profile/reactivate/` | Reactivate a self-deactivated account (no token) |
| GET | `/api/profile/me/dashboard/` | Dashboard: profile, privacy, achievement counts |
| GET | `/api/profile/<user_id>/` | Another user's profile (owner: full profile) |
| GET | `/api/profile/<user_id>/achievements/` | Paginated achievements visible to the caller |
| POST | `/api/auth/change-password/` | Change password (accounts module, see note) |

There is no endpoint that takes a user id for writing: every write acts on the authenticated user.

## Privacy model
* `profile_visibility`: `public` / `private` (default **private**). Private: everyone except the owner gets **403**.
* `email_visibility`, `date_of_birth_visibility`: default **private**. `bio_visibility`: default **public**.
* Achievement visibility is a separate, per-achievement setting that stays in the achievements module
  (`PATCH /api/achievements/<id>/`). A public profile never shows private achievements; a private
  profile shows nothing at all.
* Others never see phone number, country, role, verification status, or an achievement's certificate number.

## GET /api/profile/me/
```json
{
  "id": 1, "username": "alice", "full_name": "Alice", "email": "alice@example.com",
  "phone_number": "+9779800000000", "country": "Nepal", "date_of_birth": "2000-05-17",
  "bio": "I love robotics", "profile_picture_url": "http://host/media/profiles/1/ab12....png",
  "role": "user", "is_email_verified": true, "account_status": "active",
  "account_created_at": "2026-11-21T03:26:57+05:45",
  "privacy": {"profile_visibility": "private", "email_visibility": "private",
              "date_of_birth_visibility": "private", "bio_visibility": "public"},
  "achievement_counts": {"total": 3, "public": 2, "private": 1},
  "achievements": [ /* latest 10, same shape as GET /api/achievements/my/ (includes "visibility") */ ]
}
```

## PUT / PATCH /api/profile/me/update/
JSON or multipart. PUT requires `full_name` and `username`; PATCH takes any subset.
```json
{"full_name": "Alice Smith", "username": "alice_s", "date_of_birth": "1999-01-02",
 "bio": "I love robotics", "phone_number": "+9779812345678", "country": "Nepal"}
```
Returns **200** with the same body as `GET /me/` (without achievements). Errors **400**:
```json
{"username": ["This username is already taken."]}
{"email": ["Email cannot be changed here. Use POST /api/profile/me/email/change/ so the new address can be verified."]}
{"date_of_birth": ["You must be at least 13 years old to register."]}
```
Rules: username is unique case-insensitively and may contain letters, digits and `@ . + - _`; bio is at most
500 characters; DOB must be in the past and the user at least 13. Fields such as `role`, `is_active` or
`password` are ignored. Bio is stored as plain text: the frontend must escape it when rendering.

## POST /api/profile/me/upload-picture/  (multipart/form-data)
Field `profile_picture`. **Image upload instructions**
```
curl -X POST http://host/api/profile/me/upload-picture/ \
     -H "Authorization: Bearer $TOKEN" -F "profile_picture=@avatar.png"
```
* Allowed: JPEG (`.jpg/.jpeg`), PNG, WebP. Max **2 MB** and **4096 x 4096 px** (settings
  `PROFILE_PICTURE_MAX_SIZE`, `PROFILE_PICTURE_MAX_DIMENSION`).
* Content is checked with Pillow (not just the name/type), must match the extension, and is **re-encoded**,
  which strips EXIF metadata such as GPS. Animated images keep only their first frame.
* Stored under a random name (`profiles/<user_id>/<uuid>.<ext>`); a replaced picture's file is deleted.
* **201** first upload / **200** replacement: `{"message": "Profile picture uploaded.", "profile_picture_url": "..."}`
* **400** `{"profile_picture": ["Image is too large (3.1 MB). The maximum allowed size is 2 MB."]}`,
  `["Unsupported file type. Allowed types: JPEG, PNG and WebP."]`, `["The file is not a valid image."]`

The URL is only returned to people allowed to see the profile. Files are served from `MEDIA_URL`; in development
`config/urls.py` serves them when `DEBUG=True`; in production configure your web server (or define a `"profiles"`
entry in `settings.STORAGES` for S3 and similar).

## DELETE /api/profile/me/remove-picture/
**200** `{"message": "Profile picture removed.", "profile_picture_url": null}`; **404** if there is none.

## GET / PATCH /api/profile/me/settings/
```json
PATCH {"profile_visibility": "public", "date_of_birth_visibility": "public"}
200   {"profile_visibility": "public", "email_visibility": "private",
       "date_of_birth_visibility": "public", "bio_visibility": "public"}
```
GET also returns `achievements: {total, public, private, note}`. **400** for invalid values, unknown keys or an empty body.

## GET /api/profile/me/account/
```json
{"username": "alice", "email": "alice@example.com", "is_email_verified": true, "role": "user",
 "account_status": "active", "account_created_at": "...", "last_login": "...", "pending_email": null}
```

## E-mail change (verified)
1. `POST /api/profile/me/email/change/` `{"new_email": "new@example.com", "current_password": "..."}`
   -> **200**, and a 6-digit code is mailed to the **new** address. The account email does not change yet.
   Errors: wrong password, address already used, same address (400); resend inside the cooldown (429).
2. `POST /api/profile/me/email/confirm/` `{"otp": "123456"}`
   -> **200** `{"message": "Email address updated.", "email": "new@example.com"}`.
   Codes expire (`OTP_EXPIRY_SECONDS`), allow `OTP_MAX_ATTEMPTS` tries, are stored hashed, and the old address is notified.

## POST /api/profile/me/deactivate/
`{"current_password": "...", "confirm": true}` -> **200**. Sets `is_active=false`, ends every session, keeps all data
(nothing is deleted). The profile disappears for other users (404). There is deliberately no account-deletion endpoint.

## POST /api/profile/reactivate/  (no token)
`{"identifier": "alice@example.com", "password": "..."}`
-> **200** `{"message": "Your account has been reactivated. You can now log in."}`.
**401** wrong credentials, **400** already active, **403** if an administrator disabled the account or its e-mail
was never verified.

## GET /api/profile/me/dashboard/
Same fields as `GET /me/` (no achievement list) plus `achievement_counts`, computed from the existing Achievement model.

## GET /api/profile/<user_id>/
* Own id: the complete profile (as `/me/`).
* Another user, public profile, **200**:
```json
{"id": 1, "username": "alice", "full_name": "Alice", "profile_picture_url": "http://host/media/....png",
 "member_since": "2026-11-21T03:26:57+05:45",
 "bio": "About Alice",                 // only if bio_visibility = public
 "email": "alice@example.com",         // only if email_visibility = public
 "date_of_birth": "2000-05-17",        // only if date_of_birth_visibility = public
 "public_achievements_count": 2,
 "achievements": [ /* latest 10 PUBLIC achievements */ ]}
```
* Private profile **403** `{"detail": "This profile is private."}`; unknown or deactivated user **404**.

## GET /api/profile/<user_id>/achievements/?page=1&page_size=12
Same access rules as above. Visitors get PUBLIC achievements only; the owner gets all of theirs.

## Change password
`POST /api/auth/change-password/` `{"current_password", "new_password", "confirm_password"}` -> **200**
`{"message": "Password changed successfully.", "access": "...", "refresh": "..."}`. All other sessions are revoked and
the returned tokens keep the current device logged in. **400** for a wrong current password, mismatch, weak or
unchanged password.
