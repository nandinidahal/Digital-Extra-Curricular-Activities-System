# Messaging module (`/api/messaging/`, `ws/messaging/`)

Private one-to-one messaging for DEAS: conversations, text and attachments, replies, forwarding,
reactions, edit/delete, delivery and read receipts, unread counts, mute/archive, in-conversation
search, real-time delivery over WebSockets, typing indicators and privacy-aware presence, plus
the platform rule **"non-friends may exchange at most four messages in total"**.

Only the Messaging app was added. Accounts, Profiles, Friends and Social are reused, never
duplicated: there is no second user, profile, friendship or block table.

> **Verification.** 148 Messaging tests run against PostgreSQL 16, both with the in-memory
> channel layer and with Redis (`REDIS_URL` set). The whole project suite (638 tests) passes.
> A live check with two separate Daphne processes sharing Redis confirmed cross-process
> delivery (REST send on server A -> WebSocket event on server B).

---

## 1. Dependencies on other modules

| Needs | From | Used for |
|---|---|---|
| `AUTH_USER_MODEL` (`accounts.User`, UUID pk) | Accounts | every FK; `is_active`, `is_email_verified` |
| JWT (SimpleJWT), `success_response`, `api_exception_handler` | Accounts | same auth and JSON envelope as the rest of the API |
| `build_user_card` (privacy-aware person card) | Friends -> Profiles | sender / participant cards (private profiles hide the picture) |
| `profiles.validators.validate_image_upload` | Profiles | real-content image validation |
| `OptionalJWTAuthentication` | Profiles | attachment download (JWT *or* signed link) |
| `are_friends`, `is_blocked_between`, `get_friend_ids`, `get_hidden_user_ids` | **Friends** (authoritative) | the four-message rule, blocking, presence privacy |
| `friends.signals.*` | Friends | push new messaging permissions when friendship/blocks change |

"Available" account = active **and** e-mail verified (same rule as Friends). Unavailable users
cannot use messaging and cannot be messaged.

## 2. Data model

| Model | Purpose | Key constraints / indexes |
|---|---|---|
| `Conversation` | `direct` (implemented) or `group` (reserved). `direct_key = "<low uuid>:<high uuid>"`. `last_message_at` = activity | **UNIQUE(direct_key)**; CHECK direct ⇔ key present; index `-last_message_at` |
| `ConversationParticipant` | membership + the user's **own** `is_muted`, `is_archived`, `last_read_at`, `is_active` | UNIQUE(conversation, user); index (user, is_active, is_archived) |
| `Message` | `sender` (SET_NULL), `message_type` text/image/file/system, `content`, `reply_to`, `is_forwarded`, `client_id`, `counts_toward_limit`, edit/delete stamps | UNIQUE(sender, client_id) when set; index (conversation, -created_at, -id); **partial index** on conversation WHERE counts_toward_limit |
| `MessageAttachment` | private file + detected type, size, dimensions, safe display name | storage = `STORAGES["messaging_private"]` |
| `MessageReaction` | like / love / laugh / sad / surprised | UNIQUE(message, user) |
| `MessageReceipt` | per **recipient**: `delivered_at`, `read_at` (`conversation` denormalised) | UNIQUE(message, user); CHECK read ⇒ delivered; partial index (user, conversation) WHERE read_at IS NULL |
| `MessageVisibility` | "delete for me" | UNIQUE(message, user) |
| `UserPresence` | `last_seen_at` only (live state is in Redis) | one row per user |

Design decisions
* **UUID keys** everywhere (no enumeration), like the other modules.
* **Group-ready**: participants are rows, not two columns, so groups need no rewrite.
* **Nothing is counted in a column that can drift**: unread counts come from receipts, the
  pre-friendship count from stamped messages, reactions are aggregated on read.
* **Per-user state is per-user rows** (mute, archive, hide, receipts), so one participant's
  actions never change the other's view.

## 3. Conversation lifecycle

1. `POST /conversations/ {"user_id"}` → checks: actor available, not self, target available,
   no block in either direction → returns the existing direct conversation (200) or creates it
   (201). Concurrent starts are safe: the UNIQUE `direct_key` makes the loser reuse the winner's row.
2. Starting sends nothing and does not use the allowance. An empty conversation appears only in
   its creator's list until the first message.
3. Every message updates `last_message_at` (list ordering).
4. Blocking never deletes a conversation or its history.

## 4. Message lifecycle

`send` → validated (text and/or attachments) → **conversation row locked** → membership, block,
friendship and limit checked → message + attachments + receipts written → conversation activity
updated → after commit: real-time `message.new` + `message_sent` signal.

| Action | Who | Rule |
|---|---|---|
| Edit | sender only | within `MESSAGING_EDIT_WINDOW_MINUTES` (15); not deleted / forwarded / system; refused while a block exists; sets `is_edited`, `edited_at` |
| Delete for me | any participant | always allowed; hides the message for that user only; clears it from their unread count |
| Delete for everyone | sender only | within `MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES` (60); **tombstone**: content wiped in the DB, attachments (rows + files) and reactions removed, row kept |
| `DELETE /messages/<id>/?scope=` | — | `me` (default, always safe) or `everyone` |
| Reply | participant | target must be in the same conversation, visible to the replier, not deleted |
| Forward | participant of both | copies text + attachment files; marked `is_forwarded`; no link back to the source (nothing leaks); full send rules apply to the target, including the limit |

Text is **plain text**: trimmed, control characters refused, max 5000 chars, *not* HTML-escaped
on input (so `<3` and code survive). The frontend must render it as text (React's default; never
`dangerouslySetInnerHTML`).

## 5. The four-message rule (pre-friendship limit)

* Non-friends may exchange **`MESSAGING_NON_FRIEND_MESSAGE_LIMIT` (default 4) messages in total**
  in their conversation - both senders draw from the same allowance (A,B,A,B → 5th blocked).
* Each message is stamped `counts_toward_limit=True` if the users were **not** friends when it was
  sent; the limit counts stamped rows.
* **Deleted messages still count** (both delete kinds) - deleting cannot recover allowance.
* **Failed sends never count** (validation, block, file errors roll back everything).
* **Friends:** unlimited; messages sent while friends are not stamped.
* **Friendship removed (documented policy):** the limit applies again and the allowance used
  *before* the friendship still counts. If 4 were already used, they cannot message until friends again.
* **Blocking overrides friendship** and stops all new messages, edits, reactions and typing.
* **Concurrency:** the conversation row is locked with `SELECT … FOR UPDATE` before counting, so
  parallel requests are serialised. Tested with 12 parallel threads on PostgreSQL: exactly the
  remaining slots succeed.
* Same rule for REST and WebSocket (both call `services.send_message`).
* `0` = only friends can message.
* The UI gets the state from `GET /conversations/<id>/` and every send response:
  ```json
  "messaging": {"can_message": true, "reason": null, "is_friend": false,
                "messages_used": 1, "messages_allowed": 4, "messages_remaining": 3}
  ```
  `reason`: `null | "blocked" | "user_unavailable" | "message_limit_reached" | "conversation_inactive"`
  (`"blocked"` never says *who* blocked). A `conversation.permissions` WebSocket event pushes the
  new state when friendship or blocks change.

## 6. Blocking rules

Friends is the single source of truth (`friends.services.is_blocked_between`, either direction).
While a block exists: no new conversation, no message, no edit, no reaction, no typing, no
presence, no real-time events about the other user (except "deleted for everyone", which removes
content). History stays readable. Unblocking sends nothing and restores nothing (Friends
deletes the friendship when blocking, so the limit applies again afterwards).

## 7. REST API

All endpoints need `Authorization: Bearer <access>` and an available account, except the signed
attachment link. Success: `{"success": true, "message": "...", "data": {...}}`.

### Conversations
| Method | Endpoint | Body / query | Result |
|---|---|---|---|
| POST | `/api/messaging/conversations/` | `{"user_id"}` | 201 new / 200 existing; conversation + `messaging` |
| GET | `/api/messaging/conversations/` | `?archived=false&page=&page_size=` | paginated list |
| GET | `/api/messaging/conversations/<id>/` | | conversation + `messaging` |
| PATCH | `/api/messaging/conversations/<id>/mute/` | `{"is_muted": bool}` | conversation |
| PATCH | `/api/messaging/conversations/<id>/archive/` | `{"is_archived": bool}` | conversation |

### Messages
| Method | Endpoint | Body | Result |
|---|---|---|---|
| GET | `/conversations/<id>/messages/` | `?cursor=&page_size=30` (max 100), newest first | cursor page; marks the page delivered for the recipient |
| POST | `/conversations/<id>/messages/` | JSON `{"content","reply_to_id"?,"client_id"?}` or multipart (+ repeated `attachments`) | 201 `{message, messaging}`; 200 for a repeated `client_id` |
| PATCH | `/messages/<id>/` | `{"content"}` | edited message |
| DELETE | `/messages/<id>/?scope=me\|everyone` | | default `me` |
| POST | `/messages/<id>/delete-for-me/` | | |
| POST | `/messages/<id>/delete-for-everyone/` | | tombstone |
| POST | `/messages/<id>/reply/` | same as send | 201 |
| POST | `/messages/<id>/forward/` | `{"conversation_id"}` **or** `{"user_id"}`, `client_id`? | 201 |
| POST | `/messages/<id>/reactions/` | `{"reaction_type"}` | message with `reactions`, `my_reaction` |
| DELETE | `/messages/<id>/reactions/` | | idempotent |

### Receipts, search, misc
| Method | Endpoint | Notes |
|---|---|---|
| POST | `/conversations/<id>/read/` | `{"up_to_message_id"?}` → `{marked_read, message_ids, read_at, unread_count}` |
| POST | `/conversations/<id>/delivered/` | `{"message_ids": [...]}` (clients without a socket) |
| GET | `/conversations/<id>/unread-count/` | |
| GET | `/api/messaging/unread-count/` | navigation badge, muted conversations excluded |
| GET | `/conversations/<id>/search/?q=` | 2–100 chars, case-insensitive, paginated, only that conversation |
| GET | `/attachments/<id>/download/?sig=` | signed link (or JWT header) |
| POST | `/api/messaging/ws-ticket/` | one-time WebSocket ticket |

There is **no global message search** endpoint by design.

### Example payloads
Conversation:
```json
{
  "id": "6c1…", "conversation_type": "direct",
  "participant": {"id": "a2f…", "username": "student123", "full_name": "Example Student",
                  "profile_picture": "http://…/media/profiles/…jpg", "is_online": false,
                  "last_seen_at": "2026-11-22T09:58:00Z"},
  "last_message": {"id": "9b0…", "content": "Hello!", "message_type": "text", "sender_id": "a2f…",
                   "is_own": false, "is_deleted": false, "created_at": "2026-11-22T10:00:00Z"},
  "unread_count": 2, "is_muted": false, "is_archived": false,
  "last_read_at": null, "created_at": "…", "updated_at": "…",
  "messaging": {"can_message": true, "reason": null, "is_friend": false,
                "messages_used": 2, "messages_allowed": 4, "messages_remaining": 2}
}
```
`is_online` / `last_seen_at` are `null` when presence is hidden from the viewer.

Message:
```json
{
  "id": "9b0…", "conversation_id": "6c1…",
  "sender": {"id": "a2f…", "username": "student123", "full_name": "Example Student", "profile_picture": null},
  "is_own": false, "message_type": "image", "content": "Our robot!",
  "attachments": [{"id": "…", "kind": "image", "name": "robot.jpg", "content_type": "image/jpeg",
                   "size": 48211, "width": 1280, "height": 960,
                   "url": "http://…/api/messaging/attachments/…/download/?sig=…"}],
  "reply_to": {"id": "…", "sender_id": "…", "sender_username": "bob", "message_type": "text",
               "content_preview": "Show me?", "is_deleted": false, "is_available": true},
  "is_forwarded": false, "status": "read", "delivered_at": "…", "read_at": "…",
  "reactions": {"love": 1}, "my_reaction": "love",
  "is_edited": false, "edited_at": null, "is_deleted": false, "deleted_at": null,
  "client_id": null, "created_at": "2026-11-22T10:00:00Z", "updated_at": "…"
}
```
Deleted for everyone: `content: null`, `attachments: []`, `reactions: {}`, `is_deleted: true`.

## 8. Error responses

Shape: `{"success": false, "message": "...", "code": "...", "errors": {}, ...extra}`

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | bad/unknown fields (`sender_id`, `status`, … are rejected), empty message, bad file |
| 400 | `cannot_message_self` | |
| 401 | `not_authenticated` / `token_not_valid` | |
| 403 | `account_unavailable` | caller inactive or e-mail not verified |
| 403 | `messaging_not_allowed` | block (either direction) or unavailable recipient |
| 403 | `message_limit_reached` | + `messages_used`, `messages_allowed`, `can_message: false` |
| 403 | `not_message_owner`, `edit_window_expired`, `delete_window_expired`, `message_not_editable` | |
| 404 | `conversation_not_found`, `message_not_found`, `attachment_not_found`, `user_not_found` | also for things that exist but are not yours |
| 409 | `message_deleted`, `client_id_conflict` | |
| 413 | `payload_too_large` | multipart body over the attachment limits |
| 429 | `throttled` | + `retry_after` |

Note: the project uses lower-case codes everywhere, so the limit error is `message_limit_reached`
(the brief's example showed `MESSAGE_LIMIT_REACHED`).

## 9. Attachments

* Allowed: **JPEG, PNG, WebP** images (≤ 5 MB) and **PDF** (≤ 10 MB); ≤ 5 per message. All configurable.
* Type is detected from the **content**, never from the name or `Content-Type`.
* Images are fully decoded and **re-encoded** (removes EXIF/GPS and anything appended), long edge ≤ 2560 px.
* PDFs must start with `%PDF-`, end with `%%EOF`, and are refused if they contain
  `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/RichMedia` or `/XFA`. (Objects inside
  compressed object streams cannot be inspected this way; treat PDFs as untrusted on the client too.)
* Everything else is rejected: executables, HTML, SVG, archives, Office files, GIF, polyglots.
* Stored with a random name in **private storage** (`PRIVATE_MEDIA_ROOT`, default `private_media/`,
  outside `MEDIA_ROOT`, so DEBUG media serving can never expose it). Never base64 in PostgreSQL.
* Access: each serialized attachment has a **signed link** bound to (attachment, viewer), valid
  `MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS` (600 s) — usable in `<img src>`. On every download the
  server re-checks that the user is still an active participant, the account is active, and the
  message is not deleted or hidden for them. Responses: `nosniff`, `CSP: default-src 'none'; sandbox`,
  PDFs as `Content-Disposition: attachment`.
* Cleanup: files are removed when a send fails, on delete-for-everyone, and when attachment rows
  are deleted. `python manage.py messaging_cleanup_orphans [--delete]` removes any leftovers.
* Production: point `MESSAGING_PRIVATE_STORAGE_BACKEND` at a **private** bucket (e.g.
  `storages.backends.s3.S3Storage`, needs `django-storages`).

## 10. Delivery and read receipts

| Status | Set when | By |
|---|---|---|
| `sent` | message committed | server |
| `delivered` | the recipient's client **acknowledged** it: WebSocket `message.delivered`, `POST …/delivered/`, or the recipient loading the message list | recipient only |
| `read` | the recipient marks the conversation read (`POST …/read/` or WS `message.read`) | recipient only |

The server never claims delivery just because it pushed an event (a channel-layer send has no
acknowledgement). Receipts are per user, not per device; the first device to acknowledge wins.
Only the caller's own receipts can change, so a sender cannot mark their messages read for the
recipient. Unread counts exclude deleted and hidden messages.

## 11. WebSockets

### Routes
* `ws/messaging/` — **inbox socket** (recommended: one per browser tab). Receives events for all
  the user's conversations; client events must include `conversation_id` where relevant.
* `ws/messaging/conversations/<conversation_id>/` — **conversation socket**. Membership is checked
  on connect (close 4404 otherwise); only that conversation's events are delivered.

Events are always sent to **per-user groups** chosen by the server at send time, never to a shared
conversation group, so a socket can never subscribe to someone else's conversation.

### Authentication (browsers cannot send headers on WebSockets)
```js
// preferred: JWT as subprotocol (not in the URL, so not in proxy logs)
const ws = new WebSocket(`${WS_BASE}/ws/messaging/`, ["deas.jwt", accessToken]);
// alternative: one-time ticket (30 s, single use) from POST /api/messaging/ws-ticket/
const ws = new WebSocket(`${WS_BASE}/ws/messaging/?ticket=${ticket}`);
```
The `Origin` must be in `MESSAGING_WS_ALLOWED_ORIGINS` / `CORS_ALLOWED_ORIGINS` / `ALLOWED_HOSTS`.
When the access token expires the server sends `auth.expired` and closes with **4401**: refresh the
token and reconnect. Close codes: 4401 unauthenticated/expired, 4403 account not allowed,
4404 conversation not found, 4429 too many invalid events.

### Envelope
```json
// client -> server
{"type": "message.send", "request_id": "c-17", "conversation_id": "6c1…",
 "data": {"content": "Hi!", "client_id": "2b5e…", "reply_to_id": null}}
// server -> client (answer to a request)
{"type": "ack",   "request_id": "c-17", "data": {"message": {…}, "created": true, "messaging": {…}}}
{"type": "error", "request_id": "c-17", "code": "message_limit_reached", "message": "…",
 "status": 403, "messages_used": 4, "messages_allowed": 4, "can_message": false}
// server -> client (push)
{"type": "message.new", "conversation_id": "6c1…", "data": {…message…}}
```

### Client → server events
| type | data | notes |
|---|---|---|
| `message.send` | `content`, `client_id`?, `reply_to_id`? | attachments only via REST (multipart) |
| `message.edit` | `message_id`, `content` | |
| `message.delete` | `message_id`, `scope` (`me`/`everyone`) | |
| `message.reaction` | `message_id`, `reaction_type` (or `null` to remove) | |
| `message.read` | `up_to_message_id`? | needs `conversation_id` on the inbox socket |
| `message.delivered` | `message_ids` (1–500) | delivery acknowledgement |
| `message.typing` | `is_typing` (bool) | "started" forwarded ≤ every 2 s; "stopped" always |
| `presence.heartbeat` | — | every ~25 s **while the tab is visible and the user active** |
| `ping` | — | → `pong` |

### Server → client events
| type | data |
|---|---|
| `connection.ready` | `user_id`, `conversation_id`, `heartbeat_interval` |
| `message.new`, `message.updated` | full message (as REST) |
| `message.deleted` | `message_id`, `scope` (`everyone` to all; `me` to your other devices), `deleted_at` |
| `message.reaction_updated` | `message_id`, `user_id`, `reaction_type`, `reactions`, `my_reaction` |
| `message.delivered` | `message_ids`, `user_id`, `delivered_at` (to the sender) |
| `message.read` | `message_ids`, `user_id`, `read_at` (to the sender) |
| `conversation.read` | same, to the reader's other devices (clear badges) |
| `conversation.updated` | `is_muted`, `is_archived` (to your other devices) |
| `conversation.permissions` | the `messaging` state (friendship/block changed) |
| `user.typing` | `user_id`, `is_typing`, `expires_in` (seconds; hide the indicator after it) |
| `user.presence` | `user_id`, `is_online`, `last_seen_at` |
| `auth.expired` | — then close 4401 |

### Reconnect without duplicates
Generate a `client_id` (UUID) for every outgoing message and **reuse it when retrying**. The
server returns the original message (`created: false`, HTTP 200) instead of creating a second one,
and does not re-broadcast or re-notify. After reconnecting, fetch
`GET …/messages/` to fill any gap, and de-duplicate by `id` (you also receive your own
`message.new` besides the `ack`).

## 12. Typing and presence

* **Typing** is never stored: it goes through the channel layer to non-blocked participants only;
  clients hide it after `expires_in` (`MESSAGING_TYPING_TTL_SECONDS`, 6 s) without a refresh.
* **Presence** lives in the cache (Redis): a per-user online key with TTL
  `MESSAGING_PRESENCE_TTL_SECONDS` (70 s) refreshed by heartbeats, plus a connection counter for
  multiple tabs/devices. An open-but-idle tab stops sending heartbeats and goes offline after the
  TTL. The database is written **only** when the last connection closes (`last_seen_at`), never per
  heartbeat. `user.presence` events are sent on connect, return-from-idle and last disconnect;
  an expiry after idleness is visible on the next REST fetch.
* **Visibility** (`MESSAGING_PRESENCE_VISIBILITY`): `friends` (default) | `participants` | `nobody`.
  Blocks always hide presence. The hook is `messaging.presence.presence_visible()` — when a user
  settings module exists, add a per-user preference there (no settings model was created here).

## 13. Notifications integration

`messaging/signals.py` (no notification storage or delivery is built here):

| Signal | kwargs |
|---|---|
| `conversation_started` | `conversation`, `created_by_id`, `participant_ids` |
| `message_sent` | `message`, `sender_id`, `recipient_ids`, **`notify_user_ids`** (muted recipients removed) |
| `message_edited` | `message`, `editor_id` |
| `message_deleted` | `message`, `deleted_by_id` (delete for everyone) |
| `messages_read` | `conversation_id`, `reader_id`, `message_ids`, `read_at` |
| `reaction_changed` | `message`, `user_id`, `reaction_type` (`None` = removed) |

Sent after commit, with `send_robust` (a broken receiver is logged and never breaks messaging),
once per event (idempotent retries do not re-send). The Notifications module should import these
signals; Messaging never imports Notifications, so there is no circular import.

## 14. Configuration

All in `config/settings.py`, overridable via environment (see `.env.example`):
`MESSAGING_NON_FRIEND_MESSAGE_LIMIT` (4), `MESSAGING_MAX_MESSAGE_LENGTH` (5000),
`MESSAGING_EDIT_WINDOW_MINUTES` (15), `MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES` (60),
`MESSAGING_UNARCHIVE_ON_NEW_MESSAGE` (True — a new message returns an archived conversation to
both inboxes), `MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE` (5), `MESSAGING_IMAGE_MAX_BYTES` (5 MB),
`MESSAGING_FILE_MAX_BYTES` (10 MB), `MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS` (600),
`PRIVATE_MEDIA_ROOT`, `MESSAGING_PRIVATE_STORAGE_BACKEND`, `MESSAGING_PRESENCE_VISIBILITY`,
`MESSAGING_PRESENCE_TTL_SECONDS` (70), `MESSAGING_TYPING_TTL_SECONDS` (6),
`MESSAGING_THROTTLE_RATES` (send 60/min, actions 300/min, uploads 60/h, WS events 120/min — shared
between REST and WebSocket), `MESSAGING_WS_ALLOWED_ORIGINS`.

## 15. Redis, Channels and deployment

```bash
pip install -r requirements.txt          # adds channels, channels-redis, daphne, redis
export REDIS_URL=redis://localhost:6379/0
python manage.py migrate
python manage.py runserver               # dev: serves HTTP + WebSockets (daphne in INSTALLED_APPS)
daphne -b 0.0.0.0 -p 8000 config.asgi:application    # production (or uvicorn/gunicorn+uvicorn workers)
```
* **`REDIS_URL` is mandatory when `DEBUG=False`** (startup fails otherwise). It backs the channel
  layer *and* the cache (throttles, presence, WS tickets) for all processes. The in-memory layer
  only works inside one process and is for development/tests.
* Run the ASGI app (not WSGI) for any process that must accept WebSockets. A reverse proxy must
  forward `Upgrade`/`Connection` headers for `/ws/` (nginx: `proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`).
* Use `wss://` in production (TLS at the proxy).
* Use private object storage for attachments when running more than one server.
* Optional cron: `python manage.py messaging_cleanup_orphans --delete`.

## 16. Database performance notes

* Conversation list: one query with correlated subqueries for unread count and latest visible
  message (no row multiplication), then one participants+profiles query, one latest-messages
  query and presence (≤ 5 queries + 1 cache call) — **constant** regardless of page size (tested).
* Message history: cursor pagination over `(conversation, -created_at, -id)`; sender, profile,
  reply target joined; attachments, reactions, receipts prefetched — constant query count (tested).
* Unread counts: partial index `(user, conversation) WHERE read_at IS NULL`.
* Limit check: partial index on stamped messages, under a row lock held only for the send.
* Search is always scoped to one conversation (index bounds the scan) and uses `ILIKE`. For very
  large histories add `pg_trgm` with a GIN trigram index on `content`.
* Typing and heartbeats never touch PostgreSQL.

## 17. Testing

```bash
python manage.py test messaging                       # 148 tests, needs PostgreSQL
REDIS_URL=redis://localhost:6379/1 python manage.py test messaging   # same, on Redis
python manage.py test                                 # whole project (638 tests)
```
| File | Covers |
|---|---|
| `test_conversations.py` (18) | start/reuse, duplicates, self, unknown/unverified, blocked, access, listing, constant queries, mute/archive |
| `test_message_limit.py` (13) | 1–4 allowed, 5th rejected, shared count, deletes still count, failures don't count, friends lift it, unfriend policy, block override, config, idempotency, **12-thread race** |
| `test_messages.py` (26) | send, validation, impersonation, pagination, constant queries, edit (+window), delete for me/everyone, replies, forwarding |
| `test_message_permissions.py` (6) | outsiders, anonymous, bad tokens, server-only fields, inactive recipient, throttling |
| `test_reactions.py` (9) | add/change/remove, duplicates, outsiders, blocks, deleted |
| `test_read_receipts.py` (10) | sent→delivered→read, sender can't fake, unread counts, badge |
| `test_attachments.py` (15) | images/PDF, 10 malicious/invalid files, size/count limits, EXIF, private storage, signed/JWT download, expiry, cleanup, forward copy |
| `test_blocking.py` (7) | blocks, history kept, edit vs delete, presence hidden, unblock |
| `test_search.py` (5) | scoped, case-insensitive, deletions, validation |
| `test_presence.py` (7) | multi-session, no DB writes on heartbeat, expiry, privacy policies |
| `test_notifications.py` (5) | once, after commit, mute, retry, failing receiver |
| `test_websockets.py` (27) | auth (JWT, ticket, origin, expiry), participant-only delivery, all events, typing, receipts, limit and blocks over WS, reconnect idempotency, scoped sockets, rate limit, presence, permission push |

## 18. Changes made outside `messaging/`

| File | Change |
|---|---|
| `accounts/migrations/0001_initial.py` | **new** — was missing, so `migrate` failed on an empty DB |
| `config/settings.py` | `daphne`, `channels`, `social`, `messaging` installed; Social + Messaging settings; `STORAGES` with private attachment storage; `CHANNEL_LAYERS` (Redis required in production); loggers |
| `config/urls.py` | `/api/social/` (was never routed) and `/api/messaging/` |
| `config/asgi.py` | Channels `ProtocolTypeRouter` with origin validation + JWT middleware |
| `profiles/tests/base.py`, `social/tests/base.py` | each test gets its own media folder (4 profile tests failed because all tests shared one folder) |
| `social/README.md` | verification status updated |
| `requirements.txt`, `.env.example`, `.gitignore` | Channels/Redis deps, new settings, `private_media/` |

## 19. Known limitations

* Group conversations are modelled but not implemented (sending to a group raises `messaging_not_allowed`).
* Attachments are sent over REST only (WebSocket frames are JSON, ≤ 64 KB).
* PDF screening is heuristic (see §9); no antivirus scan is included — add one (e.g. ClamAV) before storing if required.
* Presence "went idle" is not pushed as an event; it is reflected after the TTL on the next fetch.
* Delete-for-everyone wipes content; if moderation needs evidence retention, change the tombstone policy in `services.delete_for_everyone`.
* If both participants delete their accounts the conversation row remains (no participants); harmless, can be purged by a periodic job.
