# Achievements module (`/api/achievements/`, `/api/achievement-categories/`)

Records extra-curricular accomplishments, private supporting evidence and a reviewer verification workflow.
Full endpoint reference: `../API_DOCUMENTATION.md` §4.

## Models
| Model | Notes |
|---|---|
| `AchievementCategory` | 11 defaults seeded by migration `0002`; PROTECT. |
| `Achievement` | all requested fields; `skills` is a validated JSON list (same design as `Profile.skills`). CHECKs: status/visibility/level values, **featured ⇒ verified**, verified ⇒ `verified_at`. Indexes for owner lists, review queue, public listing, featured. |
| `AchievementEvidence` | many per achievement; file in **private storage** (`achievements/<id>/evidence/<random>.<ext>`), detected type, size, sanitised display name, uploader. |
| `AchievementReview` | append-only history: reviewer (actor), `actor_role` owner/reviewer/system, previous/new status, decision, comments, timestamp. |

## Workflow
1. Owner creates → `pending` (history: `submitted`; reviewers notified).
2. Owner uploads evidence (images are re-encoded to strip EXIF/GPS; PDFs checked for scripts/embedded files).
3. Reviewer (admin/coordinator, never the owner, row-locked) → `verify` | `reject` (comment required) | `request-information` (comment required). Owner notified (and e-mailed).
4. Owner edits/adds evidence and `resubmit`s → `pending` → review again.
5. Changing a verified achievement materially (claim fields or evidence) sends it back to `pending`, removes "featured" and is recorded as `reverification_required`.

Uploading a certificate never verifies anything. Reviewers can open any achievement and download evidence;
evidence downloads are `attachment`, `Cache-Control: no-store`, authorised by JWT or a 10-minute signed link bound to the user.

## Featured
Only verified achievements; owner (or admin) features; at most `ACHIEVEMENT_MAX_FEATURED` (5) per user, enforced under a row lock.

## Privacy
Lists show only **verified** achievements, filtered by visibility and blocks. Owners see everything in `/me/`.
Evidence, history, rejection reason and reviewer identity are visible to the owner and reviewers only.
Statistics: `/stats/` = own; `/stats/?scope=platform` = reviewers only.
