# Friends module

Lets DEAS members connect: send / accept / reject / cancel friend requests, keep a friends list,
see mutual friends, check the relationship with another user, and block / unblock people.

Base URL: `/api/friends/` · Auth: JWT (`Authorization: Bearer <access token>`) · Format: JSON.

The module only owns **relationship data**. Users come from `accounts.User`, names and pictures
from `profiles.Profile`; nothing is copied.

---------------------------------------------------------------------------------------------------

## 1. Dependencies

| Module   | What Friends uses |
|----------|-------------------|
| Accounts | `settings.AUTH_USER_MODEL` (UUID pk), `is_active`, `is_email_verified`, `role`; the global error handler (`accounts.exceptions.api_exception_handler`) and `accounts.responses.success_response` |
| Profiles | `Profile.profile_visibility`, `headline`, `profile_picture` (read-only, via `select_related`); `profiles.permissions.CanViewProfile` for the mutual-friends privacy rule |
| Social   | **None.** Social may import `friends.services` later (section 11). Note: at the time this module was written `social` existed on disk but was not in `INSTALLED_APPS` / `config/urls.py`. Friends does not need it and does not change it. |

An account is **available** for friend features when it is active **and** e-mail verified (the same
rule Profiles uses for "public person"). Unavailable accounts can not be requested, blocked or
looked up (`404 user_not_found`), and are hidden from lists and counts.

## 2. Database models

```
FriendRequest  id(uuid) sender→User receiver→User status created_at updated_at responded_at
Friendship     id(uuid) user1→User  user2→User  created_at
UserBlock      id(uuid) blocker→User blocked→User created_at
```

Constraints (all enforced by the database, not only in Python):

| Table | Constraint | Purpose |
|-------|------------|---------|
| FriendRequest | `sender <> receiver` | no self requests |
| FriendRequest | status ∈ pending/accepted/rejected/cancelled | valid states |
| FriendRequest | `pending ⇔ responded_at IS NULL` | consistent timestamps |
| FriendRequest | unique `(sender, receiver)` where pending | one pending request per direction |
| FriendRequest | unique `(LEAST(sender,receiver), GREATEST(sender,receiver))` where pending | A→B and B→A can not both be pending |
| Friendship | `user1 < user2` | canonical order ⇒ a pair exists once, never reversed, never with itself |
| Friendship | unique `(user1, user2)` | no duplicate friendship |
| UserBlock | `blocker <> blocked`, unique `(blocker, blocked)` | no self block, no duplicate block |

Design decisions

* **One row per friendship, canonical order.** `Friendship.save()` swaps the two ids if needed and
  the CHECK `user1 < user2` rejects anything else. Lookups are therefore one indexed equality
  query, and "who sent the request" is irrelevant to the friendship.
* **Partial unique indexes** keep history possible: only *pending* rows are unique, so a request
  can be sent again after a cancellation or rejection without deleting old rows.
* **Indexes** match the queries: `(receiver,status,-created_at)` and `(sender,status,-created_at)`
  for the request lists, `(user2,user1)` and `(user1,-created_at)` for friend lists, `(blocked,blocker)`
  for "who blocked me".
* **No Redis/Celery/Elasticsearch.** Everything uses PostgreSQL row locks, constraints and indexes.

### History policy
Requests are never deleted. `accepted`, `rejected` and `cancelled` rows stay as history (they also
power the rejection cool-down). The lists only show `pending` requests. A friendship, in contrast,
is **deleted** when a friend is removed.

## 3. Friend-request lifecycle

```
            send                     accept (receiver)  ─► accepted  + Friendship row
 (none) ─────────► pending ──────────reject (receiver)  ─► rejected
                      │               cancel (sender)    ─► cancelled
                      └── block between the two users    ─► cancelled
```

`POST /requests/` checks, in this order: self → receiver exists & is available → blocked either
way → already friends → **reverse pending request** → duplicate pending → rejection cool-down.

* **Reverse pending request (documented choice):** if B already asked A and A now asks B, the
  existing request is **auto-accepted** (both want it). Response is `200`, `auto_accepted: true`,
  and no second request row is created.
* **Rejection cool-down:** after B rejects A, A can not ask B again for
  `FRIENDS_REJECTION_COOLDOWN_HOURS` (default 24; `0` disables) → `429 request_cooldown` with
  `retry_after` seconds. This stops repeat-asking harassment. Cancelled requests have no cool-down.
* Only the **receiver** can accept/reject, only the **sender** can cancel. Wrong participant →
  `403` (`not_request_receiver` / `not_request_sender`); a stranger → `404 request_not_found`.
* Anything not `pending` → `409 request_not_pending` (with `current_status`).
* There is deliberately **no generic update endpoint**; status only changes through the three actions.

## 4. Friendship lifecycle

Created only when a request is accepted (or auto-accepted). Either user may remove it with
`DELETE /api/friends/<user_id>/` (hard delete; both sides see it immediately). Removing does not
block anyone and does not touch request history. Afterwards either person may send a new request.

## 5. Blocking rules (single consistent policy)

Blocking user X:
1. creates the block (directional, only the blocker can remove it);
2. **deletes** an existing friendship;
3. **cancels** pending requests in **both** directions (status `cancelled`);
4. from then on no request can be sent in either direction (`403 request_not_allowed`, a message
   that does not say who blocked whom) and pending-request/friend lists never show the other person.

Unblocking only deletes the block. It does **not** restore the friendship, does **not** revive old
requests and sends nothing. Normal rules apply to a new request.

Privacy of blocks: nobody can read another user's block list; `GET blocked/status/<id>/` only says
whether **you** blocked them. Whether somebody blocked you is only visible through the relationship
status `blocked_you` (listed in the product spec). If you prefer to hide it, set
`FRIENDS_REVEAL_BLOCKED_BY_OTHER=False`: the status API then returns `not_friends` instead.

## 6. Mutual friends

`GET /mutual/<user_id>/` returns users who are friends with **both** you and the target, as two
indexed `IN (subquery)` filters on one `User` query (no per-row queries, no duplicates).

* available accounts only, ordered by username, paginated;
* `404 user_not_found` if either of you blocked the other;
* `403 profile_private` if the target's profile is **private** (Profiles' own rule, admins excepted):
  mutual friends would otherwise reveal a private user's connections;
* `400` for yourself.

## 7. Privacy and security rules

* JWT required everywhere; also requires an active, e-mail-verified account (`403 account_unavailable`).
* Every actor/owner comes from `request.user` and database rows. Request bodies are **strict**:
  unknown keys (`sender_id`, `status`, `blocker_id`, …) → `400 validation_error`.
* Object-level permissions (`IsRequestReceiver`, `IsRequestSender`) **and** a second authoritative
  check inside the service while the row is locked.
* Person cards (`user_id, username, full_name, profile_picture, headline`) never contain e-mail,
  phone, date of birth, role, etc. Profile content (picture, headline) is hidden when the person's
  profile is `private` (viewer = that person or an admin excepted).
* Write endpoints are rate-limited per user (`FRIENDS_REQUEST_RATE` default 30/hour for sending,
  `FRIENDS_ACTION_RATE` default 300/hour for accept/reject/cancel/block). Reads and DELETEs are not limited.
* **Concurrency:** each write runs in `transaction.atomic()` and first locks the two user rows with
  `SELECT … FOR UPDATE` in primary-key order (deadlock-free). Two simultaneous accepts, or A→B racing
  B→A, are serialised; the unique/check constraints are the safety net.

## 8. API reference

All success responses use the project envelope `{"success": true, "message": "...", "data": {...}}`.
Errors: `{"success": false, "message": "...", "code": "...", "errors": {...}}` (plus extras such as
`current_status`, `retry_after`). Because of this envelope the payloads in the product brief appear
under `data`. Endpoint names are exactly as specified, plus one temporary extra (`discover/`).

### Friend requests
| Method | Endpoint | Success | Errors |
|---|---|---|---|
| POST | `/requests/` body `{"receiver_id"}` | `201` (or `200` when auto-accepted) | 400 `cannot_target_self`/`validation_error`, 403 `request_not_allowed`, 404 `user_not_found`, 409 `already_friends`/`request_already_sent`, 429 `request_cooldown`/`throttled` |
| GET | `/requests/received/` | pending requests sent to me, newest first, with `sender` card | |
| GET | `/requests/sent/` | pending requests sent by me, with `receiver` card | |
| POST | `/requests/<id>/accept/` | `200` request + friendship | 403 `not_request_receiver`, 404 `request_not_found`, 409 `request_not_pending` |
| POST | `/requests/<id>/reject/` | `200` | same as accept |
| POST | `/requests/<id>/cancel/` | `200` | 403 `not_request_sender`, 404, 409 |

```jsonc
// POST /api/friends/requests/   {"receiver_id": "5b0e…"}   → 201
{ "success": true, "message": "Friend request sent successfully.",
  "data": {
    "request": { "id": "c1d2…", "sender_id": "a1…", "receiver_id": "5b0e…", "status": "pending",
                 "created_at": "2026-11-22T10:00:00Z", "updated_at": "…", "responded_at": null },
    "auto_accepted": false, "friendship": null } }

// GET /api/friends/requests/received/
{ "success": true, "message": "", "data": {
  "results": [ { "id": "c1d2…", "sender_id": "9f…", "receiver_id": "a1…", "status": "pending",
                 "created_at": "…", "updated_at": "…", "responded_at": null,
                 "sender": { "user_id": "9f…", "username": "bob", "full_name": "Bob Rai",
                             "profile_picture": "http://…/media/….jpg", "headline": "Robotics club" } } ],
  "pagination": { "count": 1, "page": 1, "page_size": 20, "total_pages": 1, "next": null, "previous": null } } }
```

### Friendships
| Method | Endpoint | Notes |
|---|---|---|
| GET | `/` | my friends, newest friendship first, paginated. Entry: person card + `friendship_id`, `friendship_created_at`, `friendship_status: "friends"` |
| DELETE | `/<user_id>/` | remove a friend. 404 `not_friends` if you are not friends, 400 for yourself |
| GET | `/count/` | `{"friend_count": 3}` (same rule as the list) |
| GET | `/status/<user_id>/` | see below. 404 for unknown/unavailable users |
| GET | `/mutual/<user_id>/` | see section 6 |
| GET | `/discover/` | **TEMPORARY** paginated user list with `friendship_status`; no search logic. Replace with the shared Search service, then delete or set `FRIENDS_ENABLE_TEMP_DISCOVERY=False` |

```jsonc
// GET /api/friends/status/<user_id>/
{ "success": true, "message": "", "data": {
  "user_id": "5b0e…", "friendship_status": "request_received", "is_friend": false,
  "request_sent": false, "request_received": true, "request_id": "c1d2…", "blocked": false } }
```
`friendship_status` ∈ `self`, `friends`, `request_sent`, `request_received`, `blocked_by_me`,
`blocked_you`, `not_friends` (precedence in that order of strength: self > blocked_by_me > blocked_you >
friends > request_sent > request_received). `request_id` is only set for the two request statuses so
the frontend can accept/cancel directly.

### Blocking
| Method | Endpoint | Notes |
|---|---|---|
| POST | `/blocked/` body `{"user_id"}` | `201`. 400 self, 404 unknown/unavailable, 409 `already_blocked` |
| GET | `/blocked/` | **my** blocked users, newest first, paginated, with `blocked_at` |
| DELETE | `/blocked/<user_id>/` | unblock. 404 `block_not_found` unless **you** created that block |
| GET | `/blocked/status/<user_id>/` | `{"user_id": "…", "blocked_by_me": true}` only |

### Pagination
`?page=<n>&page_size=<n>` (default 20, max 100). Same envelope as Social:
`data.results` + `data.pagination {count, page, page_size, total_pages, next, previous}`.

## 9. Frontend (React + TypeScript) quick types

```ts
type FriendshipStatus = "self" | "friends" | "request_sent" | "request_received"
  | "blocked_by_me" | "blocked_you" | "not_friends";
interface PersonCard { user_id: string; username: string; full_name: string;
  profile_picture: string | null; headline: string | null }
interface FriendEntry extends PersonCard { friendship_id: string;
  friendship_created_at: string; friendship_status: "friends" }
```

## 10. Integration points

Import from `friends.services` (never from models/views). Do not import other modules *into* Friends.

| Need | Call |
|------|------|
| Friend-only visibility (Social feed, post privacy) | `services.are_friends(a, b)`, `services.get_friend_ids(user)` |
| Hide blocked users everywhere | `services.get_hidden_user_ids(user)` → `.exclude(author_id__in=…)` |
| Restrict an interaction (comment, like, message) | `services.can_interact(a, b)` (different users, no block either way) |
| Status badge on posts / search results | `services.get_relationship_statuses(viewer, user_ids)` (3 queries for any number of ids) |
| Search & Discovery | start from `services.discoverable_users(viewer)` (available, not blocked, not private) |

**Social:** use the calls above in `social/permissions.py` where its README says friend-only
visibility is a future step. **Messaging:** gate "start conversation / more than N messages" with
`are_friends` and `can_interact`; Friends creates no conversations. **Profiles:** when a "friend"
visibility level is added, call `are_friends(viewer, profile.user)` (Profiles' own README asks for this).

**Notifications:** Friends only emits Django signals (`friends/signals.py`), after the transaction
commits and via `send_robust` (a failing receiver is logged and can not break a friendship action):

| Signal | kwargs |
|---|---|
| `friend_request_sent` | `friend_request` |
| `friend_request_accepted` | `friend_request`, `friendship`, `auto_accepted` |
| `friend_request_rejected` | `friend_request` |
| `friend_request_cancelled` | `friend_request`, `reason` |
| `friend_removed` | `user_id`, `other_user_id`, `reason` (`removed`/`blocked`) |
| `user_blocked` / `user_unblocked` | `block`, `friendship_removed`, `requests_cancelled` / `blocker_id`, `blocked_id` |

Product decision still open: whether rejection / removal should notify anyone. The signals exist;
the Notifications module decides whether to listen.

## 11. Configuration (all optional, in `.env`)

`FRIENDS_REQUEST_RATE`, `FRIENDS_ACTION_RATE`, `FRIENDS_REJECTION_COOLDOWN_HOURS`,
`FRIENDS_REVEAL_BLOCKED_BY_OTHER`, `FRIENDS_ENABLE_TEMP_DISCOVERY` (see `.env.example`).
Throttle counters use Django's cache; set `REDIS_URL` in production so all workers share them
(existing project behaviour).

## 12. Testing

```bash
cd Backend
python manage.py makemigrations --check --dry-run   # must report "No changes detected"
python manage.py migrate
python manage.py test friends -v 2
```
Use PostgreSQL (`DB_ENGINE=postgresql`, the test runner creates `test_<DB_NAME>`) so the expression
unique index and the row-lock concurrency tests run; `DB_ENGINE=sqlite` runs everything except
the three thread-based tests in `ConcurrencyTests`, which are skipped.
`test_*.py` files: requests, friendships (incl. DB constraints), lists/pagination/query counts,
status, mutual friends, blocking, permissions/tampering, integration (services, signals, rollback,
discovery, concurrency).

## 13. Known limitations

* Friend-based profile visibility (a "friends only" level) belongs to Profiles; until then a
  private profile hides picture/headline even from its friends.
* `discover/` is a placeholder, not a search engine.
* Blocking/unfriending is not retroactive for content other modules already stored; those modules
  must call the services above when they read.
