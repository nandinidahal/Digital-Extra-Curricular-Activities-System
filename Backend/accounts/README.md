# Accounts Module (DEAS)

Authentication foundation for the **Digital Extra-Curricular Activities System**.
It gives every future module (profiles, friendships, posts, messaging, announcements, achievements...) one shared user model and one login system.

**What it does:** registration, email OTP verification, login (JWT), token refresh, logout, forgot/reset password, change password, current-user endpoint, and basic account updates.

**What it deliberately does not do:** profiles, friends, posts, messaging or any other module.

---

## 1. Requirements

- Python 3.10+
- PostgreSQL 14+
- An SMTP account (Gmail app password, SendGrid, Mailgun, your university mail server...)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Environment configuration

```bash
cp .env.example .env            # Windows: copy .env.example .env
```

Edit `.env`. Never commit it (it is in `.gitignore`).

| Variable | Meaning |
|---|---|
| `DJANGO_SECRET_KEY` | **Required.** Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DJANGO_DEBUG` | `True` locally, `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection (`DB_ENGINE=sqlite` only for quick experiments) |
| `CORS_ALLOWED_ORIGINS` | Your React origins, e.g. `http://localhost:5173` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP settings |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS` | Token lifetimes (defaults 15 min / 7 days) |
| `OTP_VALID_MINUTES` / `OTP_MAX_ATTEMPTS` | OTP lifetime (5) and wrong-guess limit (5) |
| `NUM_PROXIES` | Reverse proxies in front of Django (needed for correct IP throttling) |

## 3. Database setup

```sql
CREATE DATABASE deas_db;
```

Put the same name, user and password in `.env`.

## 4. Migrations (important order)

`AUTH_USER_MODEL = "accounts.User"` is already set in `config/settings.py`. It **must** be set before the first migration, so do not run `migrate` on a database that was migrated with Django's default user.

```bash
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
```

> The migration file is not shipped pre-written: `makemigrations` generates it correctly for your exact Django version. Commit the generated `accounts/migrations/0001_initial.py`.

## 5. SMTP configuration

Gmail example (use an **App Password**, not your normal password; requires 2-step verification):

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=youraddress@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=DEAS <youraddress@gmail.com>
```

Quick delivery test:

```bash
python manage.py shell -c "from django.core.mail import send_mail; send_mail('Test', 'Hello', None, ['you@example.com'])"
```

Emails are real SMTP emails (HTML + plain text, templates in `templates/emails/`). If an email cannot be sent, registration is rolled back (no half-created accounts) and the API returns `503 email_delivery_failed`.

## 6. JWT configuration

Uses `djangorestframework-simplejwt`. In `config/settings.py`:

- Access token: 15 minutes. Refresh token: 7 days.
- `ROTATE_REFRESH_TOKENS = True`, `BLACKLIST_AFTER_ROTATION = True` (every refresh returns a **new** refresh token and the old one stops working).
- `rest_framework_simplejwt.token_blacklist` is installed, so logout, password change and password reset can revoke refresh tokens.

Send the access token on protected requests: `Authorization: Bearer <access>`.

---

## 7. Response format (same for every endpoint)

**Success**

```json
{ "success": true, "message": "Login successful.", "data": { } }
```

**Error**

```json
{
  "success": false,
  "message": "Please correct the highlighted errors.",
  "code": "validation_error",
  "errors": { "email": ["A user with that email already exists."] }
}
```

Some errors add extra keys: `retry_after` (seconds, on 429) and `attempts_remaining` (wrong OTP).

### Error codes

| HTTP | `code` | Meaning / what the frontend should do |
|---|---|---|
| 400 | `validation_error` | Show `errors[field]` next to each form field (`non_field_errors` = general errors) |
| 400 | `otp_invalid` | Wrong code (`attempts_remaining` may be present) |
| 400 | `otp_expired` | Code expired: offer "Resend code" |
| 400 | `otp_max_attempts` | Too many wrong guesses: offer "Resend code" |
| 400 | `reset_token_invalid` | Reset token bad/expired/used: restart "Forgot password" |
| 400 | `token_invalid` | Logout refresh token invalid: clear local tokens anyway |
| 401 | `invalid_credentials` | Wrong email or password |
| 401 | `not_authenticated` | No access token sent |
| 401 | `token_not_valid` | Access/refresh token invalid or expired: try refresh, else go to login |
| 403 | `email_not_verified` | Correct password but unverified: send user to the "Enter OTP" screen |
| 403 | `permission_denied` | Not allowed |
| 429 | `throttled` / `otp_rate_limited` | Too many requests: show countdown from `retry_after` |
| 503 | `email_delivery_failed` | SMTP problem: "try again later" |

---

## 8. API endpoints

Base URL (local): `http://localhost:8000/api/auth/`. All requests/responses are JSON (`Content-Type: application/json`).

| Method | Endpoint | Auth |
|---|---|---|
| POST | `/api/auth/register/` | Public |
| POST | `/api/auth/verify-email/` | Public |
| POST | `/api/auth/resend-otp/` | Public |
| POST | `/api/auth/login/` | Public |
| POST | `/api/auth/token/refresh/` | Refresh token in body |
| POST | `/api/auth/logout/` | Access token |
| POST | `/api/auth/forgot-password/` | Public |
| POST | `/api/auth/verify-reset-otp/` | Public |
| POST | `/api/auth/reset-password/` | Reset token in body |
| POST | `/api/auth/change-password/` | Access token |
| GET | `/api/auth/me/` | Access token |
| PATCH | `/api/auth/me/` | Access token |

### 8.1 Register: `POST /api/auth/register/`

Request

```json
{
  "full_name": "Asha Sharma",
  "username": "asha_s",
  "email": "asha@example.com",
  "password": "Str0ng!Passw0rd#2026",
  "confirm_password": "Str0ng!Passw0rd#2026",
  "date_of_birth": "2006-03-14",
  "phone_number": "+977 9812345678",
  "country": "Nepal"
}
```

Response `201`

```json
{
  "success": true,
  "message": "Account created. We sent a 6-digit verification code to your email.",
  "data": {
    "user": {
      "id": "6f1c7a9e-6c3e-4d3e-9a4c-0c9a2b1f7d11",
      "username": "asha_s",
      "full_name": "Asha Sharma",
      "email": "asha@example.com",
      "phone_number": "+9779812345678",
      "country": "Nepal",
      "date_of_birth": "2006-03-14",
      "role": "user",
      "is_email_verified": false,
      "created_at": "2026-11-22T08:30:00Z"
    },
    "email_verification_required": true,
    "otp_expires_in_minutes": 5
  }
}
```

No tokens are returned. Sending `role`, `is_staff`, `is_email_verified`... returns `400`.

Rules: username 3-30 letters/digits/`_`/`.` (unique, case-insensitive); email unique (case-insensitive); phone in international format; date of birth not in the future and the user must be at least 13 (`MINIMUM_USER_AGE`); password passes Django's validators (min 8, not common, not all numeric, not similar to username/email).

Validation error `400`

```json
{
  "success": false,
  "message": "Please correct the highlighted errors.",
  "code": "validation_error",
  "errors": {
    "email": ["A user with that email already exists."],
    "confirm_password": ["Passwords do not match."]
  }
}
```

### 8.2 Verify email: `POST /api/auth/verify-email/`

```json
{ "email": "asha@example.com", "otp": "483920" }
```

Response `200`

```json
{ "success": true, "message": "Email verified successfully. You can now log in.", "data": { "email_verified": true } }
```

Wrong code `400`

```json
{ "success": false, "message": "The code is incorrect or no longer valid.", "code": "otp_invalid", "errors": {}, "attempts_remaining": 4 }
```

The code lasts 5 minutes, allows 5 wrong attempts, and works once.

### 8.3 Resend verification code: `POST /api/auth/resend-otp/`

```json
{ "email": "asha@example.com" }
```

Response `200` (identical whether or not the account exists)

```json
{
  "success": true,
  "message": "If an account exists for this email, a verification code has been sent.",
  "data": { "otp_expires_in_minutes": 5 }
}
```

The previous code stops working. Limits: 1 request/minute per email (`429 throttled` with `retry_after`), 5 per hour.

### 8.4 Login: `POST /api/auth/login/`

```json
{ "email": "asha@example.com", "password": "Str0ng!Passw0rd#2026" }
```

Response `200`

```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "user": { "id": "6f1c7a9e-6c3e-4d3e-9a4c-0c9a2b1f7d11", "username": "asha_s", "full_name": "Asha Sharma", "email": "asha@example.com", "phone_number": "+9779812345678", "country": "Nepal", "date_of_birth": "2006-03-14", "role": "user", "is_email_verified": true, "created_at": "2026-11-22T08:30:00Z" },
    "tokens": { "access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..." }
  }
}
```

Wrong email or password `401`: `{"success": false, "message": "Invalid email or password.", "code": "invalid_credentials", "errors": {}}`
(the same answer for an unknown email, so accounts cannot be discovered).

Correct password but email not verified `403`: `code: "email_not_verified"`. Redirect the user to the OTP screen and call `resend-otp` if needed.

### 8.5 Refresh: `POST /api/auth/token/refresh/`

```json
{ "refresh": "eyJhbGciOi...(current refresh token)" }
```

Response `200`

```json
{ "success": true, "message": "Token refreshed.", "data": { "tokens": { "access": "eyJhbGciOi...", "refresh": "eyJhbGciOi...(NEW)" } } }
```

**You must replace the stored refresh token with the new one**: the old one is blacklisted. Invalid/expired/used token: `401`, `code: "token_not_valid"`.

### 8.6 Logout: `POST /api/auth/logout/`

Header: `Authorization: Bearer <access>`

```json
{ "refresh": "eyJhbGciOi..." }
```

Response `200`: `{ "success": true, "message": "Logged out successfully.", "data": {} }`.
The refresh token is blacklisted. (The short-lived access token simply expires; discard it on the client.)

### 8.7 Forgot password (3 steps)

**Step 1: `POST /api/auth/forgot-password/`**

```json
{ "email": "asha@example.com" }
```

`200` (always the same, even for unknown emails):

```json
{ "success": true, "message": "If an account exists for this email, a password reset code has been sent.", "data": { "otp_expires_in_minutes": 5 } }
```

**Step 2: `POST /api/auth/verify-reset-otp/`**

```json
{ "email": "asha@example.com", "otp": "120987" }
```

`200`:

```json
{
  "success": true,
  "message": "Code verified. You can now set a new password.",
  "data": { "reset_token": "q3Zk...long-random-string", "expires_in_minutes": 10 }
}
```

Keep `reset_token` **in memory only** (React state), not in storage or the URL.

**Step 3: `POST /api/auth/reset-password/`**

```json
{ "token": "q3Zk...long-random-string", "new_password": "An0ther$Str0ng#Pass77", "confirm_password": "An0ther$Str0ng#Pass77" }
```

`200`: `{ "success": true, "message": "Password reset successfully. You can now log in.", "data": {} }`

The token is single-use, the password is hashed, remaining reset codes are cancelled, and **every refresh token of that user is revoked** (all devices signed out).

### 8.8 Change password: `POST /api/auth/change-password/`

Header: `Authorization: Bearer <access>`

```json
{ "current_password": "Str0ng!Passw0rd#2026", "new_password": "An0ther$Str0ng#Pass77", "confirm_password": "An0ther$Str0ng#Pass77" }
```

`200`

```json
{
  "success": true,
  "message": "Password changed successfully. Other devices have been signed out.",
  "data": { "tokens": { "access": "eyJ...", "refresh": "eyJ..." } }
}
```

All old refresh tokens are revoked and a **fresh pair is returned for the current device**: store it so the user stays signed in here. (Access tokens already issued stay valid until they expire, at most 15 minutes.)

### 8.9 Current user: `GET /api/auth/me/`

Header: `Authorization: Bearer <access>`

```json
{
  "success": true,
  "message": "",
  "data": {
    "user": { "id": "6f1c7a9e-6c3e-4d3e-9a4c-0c9a2b1f7d11", "username": "asha_s", "full_name": "Asha Sharma", "email": "asha@example.com", "phone_number": "+9779812345678", "country": "Nepal", "date_of_birth": "2006-03-14", "role": "user", "is_email_verified": true, "created_at": "2026-11-22T08:30:00Z" }
  }
}
```

### 8.10 Update account: `PATCH /api/auth/me/`

Send only the fields to change. Editable: `full_name`, `username`, `email`, `phone_number`, `country`, `date_of_birth`.

```json
{ "full_name": "Asha K. Sharma", "country": "India" }
```

`200`

```json
{
  "success": true,
  "message": "Account updated successfully.",
  "data": { "user": { "...": "updated user" }, "email_verification_required": false }
}
```

**Changing email** also needs `current_password` (protects against a stolen session redirecting your account):

```json
{ "email": "asha.new@example.com", "current_password": "Str0ng!Passw0rd#2026" }
```

The email is changed, `is_email_verified` becomes `false`, and an OTP is sent to the **new** address (`email_verification_required: true`). Show the OTP screen and call `verify-email` with the new address. Until then the user stays signed in but cannot log in again.

`role`, `is_staff`, `is_active`, `is_email_verified`, `id`, `password`... in the body return `400`.

---

## 9. Frontend integration guide

### Token storage strategy

| Token | Where to keep it | Why |
|---|---|---|
| Access token | JavaScript memory (React state / module variable) | Short-lived, never touches storage |
| Refresh token | `localStorage` (simple) | Needed to survive a page reload |
| Reset token | Component state only | Single-use, 10 minutes |

`localStorage` is readable by any script running on your page, so avoid XSS (no `dangerouslySetInnerHTML` with user content; keep dependencies updated). A stricter option for later is an HttpOnly cookie for the refresh token, which needs a small backend change; ask before building it.

### Recommended Axios setup (put in the future frontend, not here)

```ts
import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL }); // e.g. http://localhost:8000/api
let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => (accessToken = t);

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const code = error.response?.data?.code;
    if (error.response?.status === 401 && code === "token_not_valid" && !original._retry) {
      original._retry = true;
      refreshing ??= axios
        .post(`${import.meta.env.VITE_API_URL}/auth/token/refresh/`, {
          refresh: localStorage.getItem("refresh"),
        })
        .then((res) => {
          const { access, refresh } = res.data.data.tokens;
          localStorage.setItem("refresh", refresh); // rotation: ALWAYS store the new one
          setAccessToken(access);
          return access;
        })
        .finally(() => (refreshing = null));
      try {
        const access = await refreshing;
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        localStorage.removeItem("refresh");
        setAccessToken(null);
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
```

Share one in-flight refresh (as above): with rotation, two parallel refreshes would use the same refresh token and the second would fail.

### Typical flows

- **Sign up:** `register` -> OTP screen -> `verify-email` -> login screen. After `register`, disable "Resend" for 60 seconds.
- **Login:** `login` -> store `tokens.refresh` in localStorage and `tokens.access` in memory. On `email_not_verified`, go to the OTP screen.
- **App start:** if a refresh token exists, call `token/refresh/` then `GET /me/`.
- **Logout:** `POST /logout/` with the current refresh token, then clear everything (also clear on any error).
- **Forgot password:** `forgot-password` -> `verify-reset-otp` (keep `reset_token` in state) -> `reset-password` -> login.

Public endpoints ignore any `Authorization` header, so a stale token never breaks login/register.

### CORS

Set `CORS_ALLOWED_ORIGINS` to your Vite origin. Credentials/cookies are not used.

---

## 10. Security summary

- Passwords hashed with Django's hashers; strength validated.
- OTPs: 6 digits from `secrets`, stored only as keyed HMAC, 5-minute life, 5 attempts, single use, bound to user + purpose + email address, previous codes cancelled on resend, never returned in responses or logged.
- Reset token: random 256-bit value, stored only as SHA-256, 10-minute life, single use.
- Rate limits: per IP and per email on login, registration, OTP and reset endpoints; plus database cooldown (60 s) and 5 codes/hour per user.
- Generic answers for forgot-password / resend / unknown-email login (no user enumeration).
- Mass-assignment protection: protected fields in a request return `400`.
- Refresh rotation + blacklist; logout, password change and reset revoke tokens.
- Database: case-insensitive unique constraints on email and username; role check constraint.

## 11. Testing

```bash
python manage.py test accounts -v 2
```

Tests use Django's in-memory email backend (no real emails) and your configured database (PostgreSQL needs permission to create a `test_<DB_NAME>` database). They cover registration, OTP verification, login, JWT, password reset and change, and account management (see `accounts/tests/`).

## 12. Using accounts in future modules

```python
# models.py of any other app
from django.conf import settings
from django.db import models

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
```

```python
# views.py of any other app
from accounts.permissions import IsEmailVerified, IsCoordinatorOrAdmin, IsOwnerOrAdmin
```

- Always use `settings.AUTH_USER_MODEL` in models and `get_user_model()` in code; never import `User` into a ForeignKey.
- The default DRF permission is `IsAuthenticated`, so a new view is private unless you opt out with `AllowAny`.
- Use `IsEmailVerified` for features that need a verified email; `IsCoordinatorOrAdmin` / `IsAdminRole` for role checks; `IsOwnerOrAdmin` for "only the author may edit".
- Profile data (bio, avatar, ...) belongs in a future `profiles` app with a `OneToOneField(settings.AUTH_USER_MODEL)`.
- Return the same response shape: `from accounts.responses import success_response`. Errors are formatted automatically by the global exception handler.
- Add each new app's URLs in `config/urls.py`.
- `role` is application-level (`user`, `coordinator`, `admin`). Access to Django's admin site uses `is_staff`/`is_superuser`; `createsuperuser` sets both.

## 13. Known limitations / production checklist

- Access tokens already issued stay valid until they expire (15 min) after logout or password change; only refresh tokens can be revoked.
- Throttle counters use Django's cache. Use a shared cache (`REDIS_URL`) when running several server processes.
- Set `DJANGO_DEBUG=False`, real `DJANGO_ALLOWED_HOSTS`, HTTPS, `NUM_PROXIES`, and `DJANGO_BEHIND_PROXY=True` if a proxy terminates TLS.
- Run `python manage.py check --deploy` before deploying.
- Periodically delete old rows: `OneTimePassword`, `PasswordResetToken`, and `python manage.py flushexpiredtokens` (Simple JWT).
- Registration reveals whether a username/email is already taken (needed for a usable sign-up form); it is protected by rate limiting.
