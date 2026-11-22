# Common module (shared utilities)

No business logic and no database tables: only things every module needs. Endpoint: `GET /api/health/`.

| File | Provides | Used by |
|---|---|---|
| `models.py` | abstract `BaseModel` = UUID pk + `created_at`/`updated_at` (`UUIDPrimaryKeyModel`, `TimeStampedModel`) | Announcements, Achievements, Notifications (existing models are not changed) |
| `validators.py` | `validate_upload()` (JPEG/PNG/WebP/PDF by real content, extension **and** MIME must agree, size limits, executables/archives/SVG/HTML rejected, PDFs with JavaScript/Launch/embedded files rejected), `validate_image_content()` (now also used by Profiles and Social), plain-text/single-line/http-URL/phone/tag-list validators | all modules |
| `files.py` | server-generated storage names (`build_storage_name`, rejects `..` and `/` in segments), `safe_display_name`, `reencode_image` (strips EXIF/GPS), after-commit deletion, `private_storage()` | Announcements (covers), Achievements (evidence) |
| `signing.py` | short-lived signed download tokens bound to file kind + object + user | Achievements evidence downloads |
| `permissions.py` | re-exports Accounts' `IsAdminRole`, `IsCoordinatorOrAdmin`, `IsEmailVerified`, `IsOwnerOrAdmin` (not duplicated); `IsModerator`, `IsOwner`, `ReadAnyWriteAuthenticated`, `is_admin/is_moderator` | all |
| `relationships.py` | thin wrappers over `friends.services` (`hidden_user_ids`, `friend_ids`, `is_blocked_between`, `exclude_hidden`); Friends stays the single source of truth | Social, Announcements, Achievements, Notifications |
| `serializers.py` | `user_card()`: privacy-aware person card (private profile → no picture except owner/admin) | all new modules + Social |
| `pagination.py` | `StandardPagination` (project envelope) + `paginate()` helper; Social's pagination now subclasses it | all |
| `throttles.py` | `SettingsScopedThrottle` (per-user rates from settings) | new modules |
| `exceptions.py` | `ResourceNotFound`, `AuthenticationRequired`, `NotOwner`, `Conflict` (409), `BusinessRuleViolation`, `UploadTooLarge`, `check_content_length` (rendered by the existing global handler in Accounts) | all |
| `testing.py` | test base class / helpers (temp media + private storage, users, files) | tests only |
| `management/commands/cleanup_orphan_media.py` | dry-run by default; `--delete` removes files no row references (older than 24 h) | ops |

Private files live in `STORAGES["private"]` (default: `PRIVATE_MEDIA_ROOT`, outside `MEDIA_ROOT`, never served by URL).
Set `PRIVATE_STORAGE_BACKEND` to a private bucket in production.
