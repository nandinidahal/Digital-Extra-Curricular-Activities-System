# DEAS Frontend — API integration reference

Every endpoint below was taken from the backend's `urls.py` / views / serializers and is called
from `src/services/api/*.ts`. Nothing here is invented; the frontend calls no endpoint that is not
in this list. All paths are relative to `${VITE_API_BASE_URL}/api`.

## Conventions used by the backend (and how the client handles them)

| Concern | Backend behaviour | Frontend handling (`src/services/api/client.ts`) |
|---|---|---|
| Success envelope | `{ success: true, message, data }` | `api.get/post/patch/delete` unwrap to `{ data, message, status }` |
| Error envelope | `{ success: false, message, code, errors, ...extra }` | `toApiError()` → `ApiError { status, code, message, fieldErrors }`; field errors are mapped onto form fields by `applyServerErrors()` |
| Page pagination | `data: { results, pagination: { count, page, page_size, total_pages, next, previous } }` | `useInfiniteQuery` + `LoadMore` (IntersectionObserver) |
| Cursor pagination (message history) | `pagination.next` is an absolute URL to *older* messages | followed as-is (`messagingApi.messagesAt(url)`) |
| Auth | SimpleJWT bearer tokens. `POST /auth/login/` → `{ user, tokens: { access, refresh } }` | `Authorization: Bearer <access>` added by an interceptor |
| Token refresh | `POST /auth/token/refresh/` with `{ refresh }`; rotation **and** blacklisting are on | single-flight refresh (concurrent 401s share one refresh call); refresh is also done proactively 30 s before `exp` because "optional auth" endpoints silently treat an expired token as a visitor |
| Session expiry | refresh token invalid / blacklisted → 401 | tokens cleared, `deas:session-expired` event → toast + redirect to `/login?next=…` |
| Logout | `POST /auth/logout/` with `{ refresh }` blacklists it | then local tokens are cleared and the user goes to `/` |
| File uploads | `multipart/form-data` | `toFormData()`; client-side pre-checks mirror backend limits (images ≤ 5 MB JPEG/PNG/WebP/GIF, evidence ≤ 10 MB images or PDF). The backend still validates the real file content (a renamed non-image is rejected — verified in the e2e test) |

Token storage: `sessionStorage` by default, `localStorage` only when "Keep me signed in" is ticked
(key `deas.auth`). No password or secret is ever stored.

## Accounts — `/api/auth/`

| Method | Path | Used by |
|---|---|---|
| POST | `register/` | Register page |
| POST | `verify-email/` `{ email, otp }` | Verify email page (returns tokens → user is signed in) |
| POST | `resend-otp/` `{ email, purpose }` | Verify / forgot-password pages (with cooldown) |
| POST | `login/` | Login page (`email_not_verified` code → sent to verification) |
| POST | `token/refresh/` | API client |
| POST | `logout/` | Account menu, Settings |
| GET / PATCH | `me/` | Session bootstrap, Settings → Account |
| POST | `change-password/` | Settings → Security (backend returns new tokens; client swaps them so the session continues) |
| POST | `forgot-password/` → `verify-reset-otp/` → `reset-password/` | Forgot-password 3-step flow |

## Profiles — `/api/profiles/`

`GET/PATCH me/`, `PATCH me/privacy/`, `POST/DELETE me/picture/`, `POST/DELETE me/cover/`,
`GET <user_id>/` (privacy-filtered by the backend; private profiles come back with
`is_private_view` and only basic fields).

## Social — `/api/social/`

Feed `GET feed/?scope=all|friends`, `GET posts/`, `GET me/posts/`, `GET users/<id>/posts/`,
`POST posts/` (text + up to N images), `GET/PATCH/DELETE posts/<id>/`,
`DELETE posts/<id>/media/<media_id>/`, `POST/DELETE posts/<id>/like/`,
`GET/POST posts/<id>/comments/`, `PATCH/DELETE comments/<id>/`, `POST comments/<id>/reply/`,
`GET comments/<id>/replies/`, `POST/DELETE comments/<id>/like/`, `POST posts/<id>/share/`,
`POST shares/` (share an announcement/achievement), `GET me/shares/`, `DELETE shares/<id>/`,
`POST reports/`, `GET reports/` + `PATCH reports/<id>/` (moderators).

## Friends — `/api/friends/`

`GET /` (my friends; filtered client-side by name on the Friends page), `GET count/`, `GET status/<user_id>/` (drives the friend button),
`GET discover/`, `GET mutual/<user_id>/`, `POST requests/`, `GET requests/received/`,
`GET requests/sent/`, `POST requests/<id>/accept|reject|cancel/`, `DELETE <user_id>/` (unfriend),
`GET/POST blocked/`, `DELETE blocked/<user_id>/`.

## Messaging — `/api/messaging/`

`GET/POST conversations/` (POST `{ user_id }` opens or returns a direct conversation),
`GET conversations/<id>/` (includes `messaging_state`), `GET/POST conversations/<id>/messages/`
(history is cursor-paginated), `GET conversations/<id>/search/?q=`, `POST conversations/<id>/read/`,
`PATCH conversations/<id>/archive/`, `PATCH conversations/<id>/mute/`, `PATCH messages/<id>/` (edit),
`POST messages/<id>/delete-for-me/`, `POST messages/<id>/delete-for-everyone/`,
`POST/DELETE messages/<id>/reactions/`, `GET unread-count/`.

**Four-message rule.** `messaging_state = { can_message, reason, is_friend, messages_used,
messages_allowed, messages_remaining }`. The composer shows "N of 4 messages left" for non-friends,
disables sending at 0 and shows the backend's reason. If the server still answers
`403 message_limit_reached`, the state is refreshed from the response. Sending reuses a
`client_id`, so a retried send is idempotent.

## Announcements — `/api/announcements/` and `/api/categories/`

| Method | Path | Notes |
|---|---|---|
| GET | `public/` | Landing page (anonymous). Cards only |
| GET | `/` | Authenticated list. Filters: `category`, `activity_type`, `location`, `when` (upcoming/ongoing/past), `registration_open`, `start_from`, `start_to`, `ordering` — all combinable, kept in the URL |
| GET | `search/?q=` | Authenticated search (combined with the same filters) |
| GET | `<id>/` | Detail — 401 for visitors, so the UI sends them to `/login?next=/announcements/<id>` |
| POST / PATCH / DELETE | `/`, `<id>/` | Create / edit (only changed fields are sent) / delete — buttons shown only when `permissions.can_edit/can_delete` |
| POST | `<id>/publish/`, `<id>/archive/`, `<id>/restore/` | Status changes |
| GET | `me/`, `me/drafts/`, `me/published/`, `me/archived/` | "Mine" tab |
| GET / POST / DELETE | `bookmarks/`, `<id>/bookmark/` | Bookmarks |
| POST | `<id>/report/` | Report |
| GET / PATCH | `reports/`, `reports/<id>/` | Moderation |
| GET | `/api/categories/` | Category chips / select |

## Achievements — `/api/achievements/` and `/api/achievement-categories/`

`GET /`, `GET me/`, `GET search/`, `GET featured/`, `GET users/<id>/`, `GET stats/`,
`POST /` (multipart, with evidence files), `GET/PATCH/DELETE <id>/`, `POST <id>/evidence/`,
`DELETE evidence/<id>/`, `GET <id>/history/`, `POST <id>/resubmit/`, `POST/DELETE <id>/feature/`,
moderators: `GET pending/`, `POST <id>/verify|reject|request-information/`.
Visibility values come from the backend: `public`, `members_only`, `private`. Private
achievements return 404 to anyone but the owner (verified in e2e).

## Notifications — `/api/notifications/`

`GET /` (`?is_read=`), `GET unread-count/`, `POST <id>/read/`, `POST <id>/unread/`,
`POST read-all/`, `DELETE <id>/`, `DELETE clear/`, `GET/PATCH preferences/`.

## Common

`GET /api/health/`.

## Real-time (Django Channels)

Sockets authenticate with the sub-protocol pair `["deas.jwt", <access token>]` (the token is not
put in the URL). Close code `4401` → refresh the token and reconnect (with backoff).

| Socket | Events consumed |
|---|---|
| `ws/notifications/` | `connection.ready`, `notification.new/updated/read/deleted`, `notification.count_updated` → navbar badge, list refresh, toast |
| `ws/messaging/` | `message.new/updated/deleted`, `message.reaction_updated`, `message.read`, `message.delivered`, `user.typing`, `conversation.permissions` (live 4-message state); client sends `presence.heartbeat` and `message.typing` |

## Missing / limited backend functionality (documented, not faked)

1. **No user search.** There is no endpoint to search all users by name. "Find people" uses
   `GET /friends/discover/` (suggestions, no query). The search box on the Friends page filters
   *your own* loaded friends list.
2. **No other user's friend list.** Only `GET /friends/mutual/<id>/` exists, so another person's
   profile shows *mutual* friends, not their full friend list or count.
3. **Achievement evidence is owner/moderator-only.** Other users see the achievement but not its
   certificate files, so achievement cards on other people's profiles show no certificate image.
4. **Achievement visibility has three levels** (`public`, `members_only`, `private`) instead of the
   two in the brief; the UI exposes all three because that is what the backend enforces.
5. **No global message search** — search is per conversation only.
6. **No endpoint to report a user profile** (posts, comments and announcements can be reported).
7. **No account deletion endpoint** — Settings does not offer it (email change via `PATCH /auth/me/` with `current_password` is supported).
8. **No dark-theme preference stored server-side**; the app ships light theme only.
