# DEAS — Frontend

React + Vite + TypeScript frontend for the **Digital Extra-Curricular Activities System**
("From Screen Time to Life Time"). It talks only to the Django backend in `../Backend` — there is
no mock data and no second backend.

## Requirements

- Node.js 20.19+ (or 22.12+) and npm
- The DEAS backend running (PostgreSQL + Redis + `daphne`/`runserver` on port 8000). Real-time
  features (live messages, typing, live notification badge) need the ASGI server (Channels).

## Setup

```bash
cd Frontend
cp .env.example .env        # then edit if your backend is not on http://127.0.0.1:8000
npm install
npm run dev                 # http://localhost:5173
```

| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | Backend origin, no trailing slash (e.g. `http://127.0.0.1:8000`). `/api` is appended by the client |
| `VITE_WS_BASE_URL` | Optional WebSocket origin; defaults to the API URL with `http→ws` / `https→wss` |

Everything prefixed `VITE_` ends up in the public JavaScript bundle — never put secrets there.
The backend's default CORS / WebSocket origin lists already allow `http://localhost:5173` and
`http://127.0.0.1:5173`; for any other origin add it to the backend's `CORS_ALLOWED_ORIGINS`
and allowed WebSocket origins in its `.env`.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on port 5173 |
| `npm run build` | Type-check (`tsc -b`) and production build into `dist/` |
| `npm run preview` | Serve the production build |
| `npm run lint` | oxlint |

For production, serve `dist/` as a static site with an SPA fallback (all unknown paths →
`index.html`), and build with `VITE_API_BASE_URL` set to the public backend URL.

## Stack

React 19, React Router 7, TypeScript (strict), Tailwind CSS 4, Axios, TanStack Query (server
state, caching, infinite scrolling), React Hook Form + Zod (forms), Lucide icons, Sonner (toasts).

## Project structure

```
src/
  components/
    common/        Button, Field inputs, Avatar, Modal + confirm dialog, Menu, Tabs, LoadMore,
                   FilePicker, OtpInput, PasswordStrength, skeletons / empty / error states
    layout/        Logo, PublicNavbar + footer, AppNavbar (+ mobile tab bar)
    social/        PostComposer, PostCard (edit / share / report dialogs), CommentSection
    announcements/ AnnouncementCard, status badges
    achievements/  AchievementCard, verification / visibility badges
    friends/       FriendButton (all relationship states)
    messaging/     ConversationView (history, composer, 4-message banner, reactions, typing)
  contexts/        AuthContext (session + tokens), RealtimeContext (WebSockets)
  hooks/           query keys, cache helpers, bookmark, debounce, cooldown
  layouts/         PublicLayout, AuthLayout, AppLayout
  pages/           public, auth, home, announcements, achievements, friends, messaging,
                   notifications, profile, settings, moderation
  routes/          RequireAuth / RequireGuest / RequireModerator guards
  services/
    api/           client.ts (Axios, envelope unwrapping, token refresh), socket.ts,
                   one file per backend module: auth, profiles, social, friends, messaging,
                   announcements, achievements, notifications, common
    auth/          tokenStorage
  types/api.ts     TypeScript types matching the backend serializers
  utils/           formatting, labels, file checks, form helpers
docs/API_INTEGRATION.md   every endpoint used, conventions, and missing backend features
tests/e2e/                end-to-end suite (Playwright, real backend)
```

## Features

- **Visitors:** landing page with public announcement cards from `GET /api/announcements/public/`.
  No search, filters, creation or detail — clicking a card goes to `/login?next=/announcements/<id>`
  and returns there after login (the backend also returns 401 for the detail).
- **Auth:** registration with live validation and password strength, e-mail OTP verification with
  resend cooldown, login (unverified accounts are routed to verification), "keep me signed in",
  forgot password (OTP → new password), change password, logout (refresh token blacklisted),
  automatic access-token refresh, expired-session handling.
- **Home feed:** composer with photos, visibility and category; For you / Friends / My shares tabs;
  like, comment, reply, like comments, edit/delete own posts and comments, share, report;
  infinite scrolling.
- **Announcements:** search, category chips, combinable filters (type, location, when,
  registration open, date range, ordering) kept in the URL; create/edit with drafts, cover image,
  online/in-person details; publish/archive/restore/delete per backend permissions; bookmarks;
  report; my announcements by status.
- **Achievements:** portfolio with stats, add with certificate images/PDF evidence, edit, delete,
  visibility (public / members only / private — as defined by the backend), verification status,
  resubmit, featured achievements, share to feed, history timeline; moderators verify / reject /
  request information.
- **Profiles:** cover + avatar, about, skills, links, posts, achievements, mutual friends;
  privacy (public / members only / private) enforced by the backend; private profiles show a
  private notice to others.
- **Friends:** friends list with search, received / sent requests, discover people,
  send / cancel / accept / reject / unfriend / block / unblock, relationship-aware buttons.
- **Messaging:** conversation list, unread counts, per-conversation search, cursor-paginated
  history, real-time delivery and typing over WebSocket, edit, delete for me / for everyone,
  reactions, archive, mute, and the **four-message limit for non-friends** (remaining count shown,
  composer disabled at 0, server state is authoritative).
- **Notifications:** live unread badge and toasts over WebSocket, list with read/unread filters,
  mark read/unread, mark all read, delete, clear, links to the related item.
- **Settings:** account details, change password, profile and per-achievement privacy,
  notification preferences, blocked users, logout. Only settings the backend supports.
- **Moderation** (admins / coordinators): achievement review queue, announcement reports,
  social reports, platform stats.
- Responsive from 360 px phones (bottom tab bar) through tablets to desktop (three-column feed).

## Testing

What was run on this code, against the real backend (PostgreSQL 16, Redis, Daphne/Channels,
fresh database):

| Check | Result |
|---|---|
| `tsc` (strict) | 0 errors |
| `npm run build` | succeeds |
| `npm run lint` (oxlint) | 0 errors (3 style warnings) |
| End-to-end suite `tests/e2e/e2e_test.py` (Playwright + Chrome) | **28 / 28 steps pass** |

The e2e suite drives the UI the way a user would and covers: visitor restrictions and the
login→detail redirect; protected-route redirects; registration with OTP; validation and server
field errors; login errors; posts with photos, likes, comments, replies, edits; server-side
rejection of a fake image; announcements create/validate/publish, draft privacy, search, category
filter, contact-detail privacy, bookmarks; friend request → accept via notifications; the
4-message non-friend limit; real-time message delivery between two browsers; live notification
badge; achievement with PDF evidence verified by a coordinator; achievement privacy (private →
404 for others); profile privacy; profile editing; notification preferences; change password;
logout; forgot password; and no horizontal overflow at 390 px and 820 px. The only browser console
errors are the expected 4xx responses produced by the negative tests.

Not tested: sending e-mail through a real SMTP server (the suite captures OTP e-mails with
Django's file backend), browsers other than Chrome/Chromium, and production deployment.

### Running the e2e suite

```bash
pip install playwright pillow && python -m playwright install chromium
# backend with the test-only settings overlay (writes e-mails to files):
cd Backend
createdb deas_e2e
PYTHONPATH=../Frontend/tests/e2e DJANGO_SETTINGS_MODULE=e2e_settings DB_NAME=deas_e2e python manage.py migrate
PYTHONPATH=../Frontend/tests/e2e DJANGO_SETTINGS_MODULE=e2e_settings DB_NAME=deas_e2e daphne -b 127.0.0.1 -p 8000 config.asgi:application
# in another terminal
cd Frontend && npm run dev
# in a third terminal (use a fresh database each run)
python Frontend/tests/e2e/e2e_test.py
```

Optional environment variables: `E2E_FRONTEND_URL`, `E2E_API_URL`, `E2E_MAIL_DIR`,
`E2E_BACKEND_DIR`, `E2E_DB_NAME`, `E2E_CHROME`. Screenshots go to `tests/e2e/shots/`.

## Backend gaps

See the end of [`docs/API_INTEGRATION.md`](docs/API_INTEGRATION.md) for features the brief asks
for that the backend does not expose (user search, other users' friend lists, others' certificate
images, two-level achievement privacy, …) and how the UI handles each.
