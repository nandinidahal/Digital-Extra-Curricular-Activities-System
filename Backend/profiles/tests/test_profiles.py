import io
import os
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import User
from achievements.models import Achievement, AchievementCategory
from profiles.models import PendingEmailChange, UserProfile

PASSWORD = "Str0ng!Passw0rd"
MEDIA = tempfile.mkdtemp(prefix="profile-tests-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def make_user(username, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD,
        full_name=username.title(), phone_number="+9779800000000", country="Nepal",
        date_of_birth=extra.pop("date_of_birth", date(2000, 5, 17)),
        is_active=extra.pop("is_active", True), is_email_verified=extra.pop("is_email_verified", True), **extra,
    )


def image_upload(name="me.png", fmt="PNG", content_type="image/png", size=(20, 20), exif=False):
    buf = io.BytesIO()
    img = Image.new("RGB", size, "blue")
    if exif:
        e = Image.Exif()
        e[0x010F] = "SecretCameraMaker"
        img.save(buf, fmt, exif=e)
    else:
        img.save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def make_achievement(user, visibility, title="Award"):
    category = AchievementCategory.objects.first() or AchievementCategory.objects.create(name="Misc")
    return Achievement.objects.create(
        user=user, category=category, title=title, issuing_organization="Org",
        achievement_date=date.today() - timedelta(days=10), certificate_number="SECRET-123", visibility=visibility,
    )


@override_settings(MEDIA_ROOT=MEDIA)
class ProfileBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.alice = make_user("alice")
        self.bob = make_user("bob")

    def login(self, user):
        r = self.client.post(reverse("login"), {"identifier": user.username, "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
        return r.json()

    def as_user(self, user):
        self.client.force_authenticate(user)


class OwnProfileTests(ProfileBase):
    def test_user_can_view_own_profile(self):
        UserProfile.objects.filter(user=self.alice).update(bio="Hello there")
        self.login(self.alice)
        r = self.client.get(reverse("profile-me"))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["id"], self.alice.id)
        self.assertEqual(d["username"], "alice")
        self.assertEqual(d["full_name"], "Alice")
        self.assertEqual(d["email"], "alice@example.com")
        self.assertEqual(d["date_of_birth"], "2000-05-17")
        self.assertEqual(d["bio"], "Hello there")
        self.assertIn("account_created_at", d)
        self.assertEqual(d["account_status"], "active")
        self.assertIsNone(d["profile_picture_url"])
        self.assertEqual(d["privacy"]["profile_visibility"], "private")
        self.assertEqual(d["privacy"]["email_visibility"], "private")

    def test_never_exposes_password_or_token_data(self):
        self.as_user(self.alice)
        body = self.client.get(reverse("profile-me")).content.decode()
        for forbidden in ("password", "pbkdf2", "token_version", "is_superuser"):
            self.assertNotIn(forbidden, body)

    def test_own_profile_lists_own_public_and_private_achievements(self):
        make_achievement(self.alice, "public", "Pub")
        make_achievement(self.alice, "private", "Priv")
        self.as_user(self.alice)
        d = self.client.get(reverse("profile-me")).json()
        self.assertEqual({a["title"] for a in d["achievements"]}, {"Pub", "Priv"})
        self.assertEqual(d["achievement_counts"], {"total": 2, "public": 1, "private": 1})

    def test_profile_created_automatically_for_new_user(self):
        self.assertTrue(UserProfile.objects.filter(user=self.alice).exists())

    def test_profile_recreated_if_missing(self):
        UserProfile.objects.filter(user=self.alice).delete()
        self.as_user(self.alice)
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=self.alice).exists())


class UpdateProfileTests(ProfileBase):
    def test_patch_updates_profile(self):
        self.as_user(self.alice)
        r = self.client.patch(reverse("profile-update"), {
            "full_name": "Alice Smith", "bio": "I love robotics", "date_of_birth": "1999-01-02",
            "username": "alice_s", "country": "India",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.full_name, "Alice Smith")
        self.assertEqual(self.alice.username, "alice_s")
        self.assertEqual(self.alice.date_of_birth, date(1999, 1, 2))
        self.assertEqual(self.alice.country, "India")
        self.assertEqual(self.alice.user_profile.bio, "I love robotics")
        self.assertEqual(r.json()["bio"], "I love robotics")

    def test_put_requires_name_and_username(self):
        self.as_user(self.alice)
        r = self.client.put(reverse("profile-update"), {"bio": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("full_name", r.json())
        self.assertIn("username", r.json())
        r = self.client.put(reverse("profile-update"),
                            {"full_name": "A B", "username": "alice", "bio": "put ok"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_user_id_in_payload_cannot_target_another_user(self):
        self.as_user(self.alice)
        r = self.client.patch(reverse("profile-update"),
                              {"id": self.bob.id, "user": self.bob.id, "user_id": self.bob.id, "full_name": "Hacked"},
                              format="json")
        self.assertEqual(r.status_code, 200)
        self.bob.refresh_from_db()
        self.alice.refresh_from_db()
        self.assertEqual(self.bob.full_name, "Bob")
        self.assertEqual(self.alice.full_name, "Hacked")

    def test_cannot_escalate_role_or_flags_via_update(self):
        self.as_user(self.alice)
        self.client.patch(reverse("profile-update"),
                          {"role": "admin", "is_staff": True, "is_superuser": True, "is_active": False,
                           "is_email_verified": False}, format="json")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, "user")
        self.assertFalse(self.alice.is_staff)
        self.assertTrue(self.alice.is_active)
        self.assertTrue(self.alice.is_email_verified)

    def test_username_validation(self):
        self.as_user(self.alice)
        url = reverse("profile-update")
        r = self.client.patch(url, {"username": "BOB"}, format="json")  # case-insensitive duplicate
        self.assertEqual(r.status_code, 400)
        self.assertIn("username", r.json())
        self.assertEqual(self.client.patch(url, {"username": "bad name!"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"username": "x" * 151}, format="json").status_code, 400)
        # keeping your own username (even re-cased) is fine
        self.assertEqual(self.client.patch(url, {"username": "Alice"}, format="json").status_code, 200)

    def test_email_cannot_be_changed_through_update(self):
        self.as_user(self.alice)
        r = self.client.patch(reverse("profile-update"), {"email": "new@example.com"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")
        # re-sending the current address is harmless
        r = self.client.patch(reverse("profile-update"), {"email": "ALICE@example.com", "bio": "ok"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_field_validation(self):
        self.as_user(self.alice)
        url = reverse("profile-update")
        self.assertEqual(self.client.patch(url, {"date_of_birth": "2999-01-01"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"date_of_birth": "not-a-date"}, format="json").status_code, 400)
        young = (date.today() - timedelta(days=365 * 5)).isoformat()
        self.assertEqual(self.client.patch(url, {"date_of_birth": young}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"bio": "x" * 501}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"full_name": "   "}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"phone_number": "abc"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"bio": ""}, format="json").status_code, 200)  # bio may be cleared


class ProfilePictureTests(ProfileBase):
    def setUp(self):
        super().setUp()
        self.as_user(self.alice)

    def upload(self, f):
        return self.client.post(reverse("profile-upload-picture"), {"profile_picture": f}, format="multipart")

    def test_upload_picture(self):
        r = self.upload(image_upload())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["profile_picture_url"].startswith("http"))
        self.alice.user_profile.refresh_from_db()
        profile = UserProfile.objects.get(user=self.alice)
        self.assertTrue(profile.profile_picture.name.startswith(f"profiles/{self.alice.id}/"))
        self.assertTrue(profile.profile_picture.name.endswith(".png"))
        self.assertTrue(self.client.get(reverse("profile-me")).json()["profile_picture_url"])

    def test_replace_picture_deletes_old_file(self):
        self.upload(image_upload())
        old = UserProfile.objects.get(user=self.alice).profile_picture
        old_name, storage = old.name, old.storage
        with self.captureOnCommitCallbacks(execute=True):
            r = self.upload(image_upload("b.jpg", "JPEG", "image/jpeg"))
        self.assertEqual(r.status_code, 200)
        new_name = UserProfile.objects.get(user=self.alice).profile_picture.name
        self.assertNotEqual(old_name, new_name)
        self.assertTrue(new_name.endswith(".jpg"))
        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(new_name))

    def test_remove_picture(self):
        self.upload(image_upload())
        profile = UserProfile.objects.get(user=self.alice)
        name, storage = profile.profile_picture.name, profile.profile_picture.storage
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.delete(reverse("profile-remove-picture"))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["profile_picture_url"])
        self.assertFalse(UserProfile.objects.get(user=self.alice).profile_picture)
        self.assertFalse(storage.exists(name))
        self.assertEqual(self.client.delete(reverse("profile-remove-picture")).status_code, 404)

    def test_accepts_all_allowed_formats(self):
        for name, fmt, ctype in (("a.jpg", "JPEG", "image/jpeg"), ("a.jpeg", "JPEG", "image/jpeg"),
                                 ("a.png", "PNG", "image/png"), ("a.webp", "WEBP", "image/webp")):
            r = self.upload(image_upload(name, fmt, ctype))
            self.assertIn(r.status_code, (200, 201), f"{name}: {r.content}")

    def test_rejects_bad_uploads(self):
        bad = {
            "gif": image_upload("a.gif", "GIF", "image/gif"),
            "svg": SimpleUploadedFile("a.svg", b"<svg onload=alert(1)/>", content_type="image/svg+xml"),
            "php": SimpleUploadedFile("a.php.png", b"<?php echo 1;", content_type="image/png"),
            "text-as-png": SimpleUploadedFile("a.png", b"not an image at all", content_type="image/png"),
            "ext-mismatch": image_upload("a.jpg", "PNG", "image/jpeg"),
            "bad-content-type": image_upload("a.png", "PNG", "application/pdf"),
            "empty": SimpleUploadedFile("a.png", b"", content_type="image/png"),
            "no-extension": image_upload("avatar", "PNG", "image/png"),
        }
        for label, f in bad.items():
            r = self.upload(f)
            self.assertEqual(r.status_code, 400, f"{label} was accepted: {r.content}")
        self.assertFalse(UserProfile.objects.get(user=self.alice).profile_picture)

    def test_rejects_truncated_image(self):
        good = image_upload(size=(200, 200)).read()
        r = self.upload(SimpleUploadedFile("a.png", good[: len(good) // 2], content_type="image/png"))
        self.assertEqual(r.status_code, 400)

    @override_settings(PROFILE_PICTURE_MAX_SIZE=1024)
    def test_rejects_oversized_file(self):
        big = io.BytesIO()
        Image.frombytes("RGB", (200, 200), os.urandom(200 * 200 * 3)).save(big, "PNG")
        self.assertGreater(len(big.getvalue()), 1024)
        r = self.upload(SimpleUploadedFile("big.png", big.getvalue(), content_type="image/png"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("too large", str(r.json()))

    @override_settings(PROFILE_PICTURE_MAX_DIMENSION=50)
    def test_rejects_huge_dimensions(self):
        self.assertEqual(self.upload(image_upload(size=(100, 100))).status_code, 400)

    def test_missing_file(self):
        self.assertEqual(self.client.post(reverse("profile-upload-picture"), {}, format="multipart").status_code, 400)

    def test_exif_metadata_is_stripped(self):
        self.assertEqual(self.upload(image_upload("a.jpg", "JPEG", "image/jpeg", exif=True)).status_code, 201)
        stored = UserProfile.objects.get(user=self.alice).profile_picture
        with stored.open("rb") as fh:
            img = Image.open(fh)
            self.assertNotIn(0x010F, dict(img.getexif()))


class PrivacySettingsTests(ProfileBase):
    def test_get_and_update_settings(self):
        self.as_user(self.alice)
        d = self.client.get(reverse("profile-settings")).json()
        self.assertEqual(d["profile_visibility"], "private")
        self.assertEqual(d["email_visibility"], "private")
        self.assertEqual(d["date_of_birth_visibility"], "private")
        self.assertEqual(d["bio_visibility"], "public")
        self.assertIn("total", d["achievements"])
        r = self.client.patch(reverse("profile-settings"),
                              {"profile_visibility": "public", "email_visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        profile = UserProfile.objects.get(user=self.alice)
        self.assertEqual(profile.profile_visibility, "public")
        self.assertEqual(profile.email_visibility, "public")
        self.assertEqual(profile.date_of_birth_visibility, "private")

    def test_invalid_settings_rejected(self):
        self.as_user(self.alice)
        url = reverse("profile-settings")
        self.assertEqual(self.client.patch(url, {"profile_visibility": "friends"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"nonsense": "public"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {}, format="json").status_code, 400)
        # a user id in the payload cannot redirect the change to someone else
        self.assertEqual(self.client.patch(url, {"user": self.bob.id, "profile_visibility": "public"},
                                           format="json").status_code, 400)
        self.assertEqual(UserProfile.objects.get(user=self.bob).profile_visibility, "private")


class OtherUsersProfileTests(ProfileBase):
    def publish(self, user, **over):
        UserProfile.objects.filter(user=user).update(profile_visibility="public", **over)

    def test_public_profile_shows_only_permitted_fields(self):
        self.publish(self.alice, bio="About Alice")
        self.as_user(self.bob)
        r = self.client.get(reverse("profile-detail", args=[self.alice.id]))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["username"], "alice")
        self.assertEqual(d["full_name"], "Alice")
        self.assertEqual(d["bio"], "About Alice")
        for hidden in ("email", "date_of_birth", "phone_number", "country", "role", "is_email_verified",
                       "privacy", "account_status"):
            self.assertNotIn(hidden, d)
        body = r.content.decode()
        self.assertNotIn("alice@example.com", body)
        self.assertNotIn("2000-05-17", body)

    def test_owner_controls_email_dob_and_bio_visibility(self):
        self.publish(self.alice, bio="About Alice", email_visibility="public", date_of_birth_visibility="public")
        self.as_user(self.bob)
        d = self.client.get(reverse("profile-detail", args=[self.alice.id])).json()
        self.assertEqual(d["email"], "alice@example.com")
        self.assertEqual(d["date_of_birth"], "2000-05-17")
        UserProfile.objects.filter(user=self.alice).update(bio_visibility="private")
        d = self.client.get(reverse("profile-detail", args=[self.alice.id])).json()
        self.assertNotIn("bio", d)

    def test_private_profile_is_protected(self):
        make_achievement(self.alice, "public")
        self.as_user(self.bob)
        r = self.client.get(reverse("profile-detail", args=[self.alice.id]))
        self.assertEqual(r.status_code, 403)
        body = r.content.decode()
        for leaked in ("alice", "Alice", "example.com", "Award"):
            self.assertNotIn(leaked, body)
        self.assertEqual(self.client.get(reverse("profile-achievements", args=[self.alice.id])).status_code, 403)

    def test_owner_always_sees_complete_profile_via_id_route(self):
        self.as_user(self.alice)  # profile is private
        r = self.client.get(reverse("profile-detail", args=[self.alice.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "alice@example.com")
        self.assertIn("privacy", r.json())

    def test_public_achievements_visible_private_hidden(self):
        self.publish(self.alice)
        make_achievement(self.alice, "public", "Visible Award")
        make_achievement(self.alice, "private", "Secret Award")
        self.as_user(self.bob)
        r = self.client.get(reverse("profile-detail", args=[self.alice.id]))
        d = r.json()
        self.assertEqual([a["title"] for a in d["achievements"]], ["Visible Award"])
        self.assertEqual(d["public_achievements_count"], 1)
        self.assertNotIn("Secret Award", r.content.decode())
        self.assertNotIn("SECRET-123", r.content.decode())  # certificate number never shown to others
        lst = self.client.get(reverse("profile-achievements", args=[self.alice.id])).json()
        self.assertEqual([a["title"] for a in lst["results"]], ["Visible Award"])

    def test_profile_visibility_and_achievement_visibility_are_separate(self):
        # private profile + public achievement: still closed. public profile + private achievement: still hidden.
        make_achievement(self.alice, "public", "Pub")
        self.as_user(self.bob)
        self.assertEqual(self.client.get(reverse("profile-detail", args=[self.alice.id])).status_code, 403)
        self.publish(self.alice)
        Achievement.objects.all().update(visibility="private")
        d = self.client.get(reverse("profile-detail", args=[self.alice.id])).json()
        self.assertEqual(d["achievements"], [])
        self.assertEqual(d["public_achievements_count"], 0)

    def test_owner_achievement_list_includes_private(self):
        make_achievement(self.alice, "private", "Mine")
        self.as_user(self.alice)
        lst = self.client.get(reverse("profile-achievements", args=[self.alice.id])).json()
        self.assertEqual([a["title"] for a in lst["results"]], ["Mine"])
        self.assertEqual(lst["results"][0]["visibility"], "private")

    def test_unknown_and_deactivated_users_are_404(self):
        self.as_user(self.bob)
        self.assertEqual(self.client.get(reverse("profile-detail", args=[999999])).status_code, 404)
        self.publish(self.alice)
        User.objects.filter(pk=self.alice.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("profile-detail", args=[self.alice.id])).status_code, 404)

    def test_other_user_cannot_modify_profile(self):
        self.publish(self.alice)
        self.as_user(self.bob)
        url = reverse("profile-detail", args=[self.alice.id])
        for method in (self.client.put, self.client.patch, self.client.post, self.client.delete):
            self.assertEqual(method(url, {"full_name": "Hacked"}, format="json").status_code, 405)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.full_name, "Alice")


class DashboardTests(ProfileBase):
    def test_dashboard_counts_and_fields(self):
        for vis in ("public", "public", "private"):
            make_achievement(self.alice, vis)
        make_achievement(self.bob, "public")  # someone else's must not count
        self.as_user(self.alice)
        r = self.client.get(reverse("profile-dashboard"))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["achievement_counts"], {"total": 3, "public": 2, "private": 1})
        for key in ("username", "full_name", "email", "bio", "profile_picture_url", "privacy",
                    "account_status", "account_created_at", "date_of_birth"):
            self.assertIn(key, d)
        self.assertEqual(d["privacy"]["profile_visibility"], "private")

    def test_dashboard_with_no_achievements(self):
        self.as_user(self.alice)
        self.assertEqual(self.client.get(reverse("profile-dashboard")).json()["achievement_counts"],
                         {"total": 0, "public": 0, "private": 0})


class AuthenticationTests(ProfileBase):
    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(None)
        self.client.credentials()
        calls = [
            ("get", reverse("profile-me")), ("put", reverse("profile-update")), ("patch", reverse("profile-update")),
            ("post", reverse("profile-upload-picture")), ("delete", reverse("profile-remove-picture")),
            ("get", reverse("profile-settings")), ("patch", reverse("profile-settings")),
            ("get", reverse("profile-account")), ("post", reverse("profile-email-change")),
            ("post", reverse("profile-email-confirm")), ("post", reverse("profile-deactivate")),
            ("get", reverse("profile-dashboard")), ("get", reverse("profile-detail", args=[self.alice.id])),
            ("get", reverse("profile-achievements", args=[self.alice.id])),
        ]
        for method, url in calls:
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, f"{method} {url}")

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.token")
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)

    def test_real_jwt_flow(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)


class EmailChangeTests(ProfileBase):
    def code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def request_change(self, new="alice.new@example.com", password=PASSWORD):
        return self.client.post(reverse("profile-email-change"),
                                {"new_email": new, "current_password": password}, format="json")

    def test_full_flow(self):
        self.as_user(self.alice)
        r = self.request_change()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mail.outbox[-1].to, ["alice.new@example.com"])
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")  # unchanged until confirmed
        self.assertEqual(self.client.get(reverse("profile-account")).json()["pending_email"], "alice.new@example.com")
        code = self.code()
        self.assertNotEqual(PendingEmailChange.objects.get().code_hash, code)  # never stored in plain text
        r = self.client.post(reverse("profile-email-confirm"), {"otp": code}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice.new@example.com")
        self.assertFalse(PendingEmailChange.objects.exists())
        self.assertEqual(mail.outbox[-1].to, ["alice@example.com"])  # old address is told
        self.assertIsNone(self.client.get(reverse("profile-account")).json()["pending_email"])

    def test_wrong_password_duplicate_and_same_email_rejected(self):
        self.as_user(self.alice)
        self.assertEqual(self.request_change(password="wrong").status_code, 400)
        self.assertEqual(self.request_change(new="BOB@example.com").status_code, 400)  # taken (case-insensitive)
        self.assertEqual(self.request_change(new="alice@example.com").status_code, 400)
        self.assertEqual(self.request_change(new="not-an-email").status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_code_and_attempt_limit(self):
        self.as_user(self.alice)
        self.request_change()
        url = reverse("profile-email-confirm")
        real = self.code()
        wrong = "000000" if real != "000000" else "111111"
        with override_settings(OTP_MAX_ATTEMPTS=3):
            for _ in range(3):
                self.assertEqual(self.client.post(url, {"otp": wrong}, format="json").status_code, 400)
            # attempts exhausted: even the right code no longer works
            self.assertEqual(self.client.post(url, {"otp": real}, format="json").status_code, 400)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")

    def test_expired_code(self):
        self.as_user(self.alice)
        self.request_change()
        PendingEmailChange.objects.update(expires_at=PendingEmailChange.objects.get().created_at - timedelta(minutes=1))
        r = self.client.post(reverse("profile-email-confirm"), {"otp": self.code()}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_confirm_fails_if_address_was_taken_meanwhile(self):
        self.as_user(self.alice)
        self.request_change(new="race@example.com")
        code = self.code()
        make_user("carol", ) and User.objects.filter(username="carol").update(email="race@example.com")
        self.assertEqual(self.client.post(reverse("profile-email-confirm"), {"otp": code}, format="json").status_code, 400)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")

    def test_resend_cooldown(self):
        self.as_user(self.alice)
        self.assertEqual(self.request_change().status_code, 200)
        self.assertEqual(self.request_change(new="other@example.com").status_code, 429)

    def test_confirm_without_request(self):
        self.as_user(self.alice)
        self.assertEqual(self.client.post(reverse("profile-email-confirm"), {"otp": "123456"}, format="json").status_code, 400)

    def test_one_user_cannot_confirm_anothers_change(self):
        self.as_user(self.alice)
        self.request_change()
        code = self.code()
        self.as_user(self.bob)
        self.assertEqual(self.client.post(reverse("profile-email-confirm"), {"otp": code}, format="json").status_code, 400)
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.email, "bob@example.com")


class AccountSettingsTests(ProfileBase):
    def test_account_info(self):
        self.as_user(self.alice)
        d = self.client.get(reverse("profile-account")).json()
        self.assertEqual(d["account_status"], "active")
        self.assertEqual(d["email"], "alice@example.com")
        self.assertTrue(d["is_email_verified"])
        self.assertIn("account_created_at", d)
        self.assertNotIn("password", d)

    def test_deactivate_requires_password_and_confirmation(self):
        self.as_user(self.alice)
        url = reverse("profile-deactivate")
        self.assertEqual(self.client.post(url, {"current_password": "bad", "confirm": True}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"current_password": PASSWORD, "confirm": False}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"current_password": PASSWORD}, format="json").status_code, 400)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_active)

    def test_deactivate_then_reactivate(self):
        tokens = self.login(self.alice)
        r = self.client.post(reverse("profile-deactivate"), {"current_password": PASSWORD, "confirm": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_active)
        self.assertIsNotNone(self.alice.user_profile.deactivated_at)
        # old tokens are dead and login is refused
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]}, format="json").status_code, 401)
        self.assertEqual(self.client.post(reverse("login"), {"identifier": "alice", "password": PASSWORD}, format="json").status_code, 403)
        # data is kept, profile is hidden from others
        self.assertTrue(UserProfile.objects.filter(user=self.alice).exists())
        UserProfile.objects.filter(user=self.alice).update(profile_visibility="public")
        self.as_user(self.bob)
        self.assertEqual(self.client.get(reverse("profile-detail", args=[self.alice.id])).status_code, 404)
        self.client.force_authenticate(None)
        # wrong password cannot reactivate
        url = reverse("profile-reactivate")
        self.assertEqual(self.client.post(url, {"identifier": "alice", "password": "bad"}, format="json").status_code, 401)
        r = self.client.post(url, {"identifier": "alice@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_active)
        self.assertIsNone(self.alice.user_profile.deactivated_at)
        self.assertEqual(self.client.post(reverse("login"), {"identifier": "alice", "password": PASSWORD}, format="json").status_code, 200)

    def test_admin_disabled_or_unverified_accounts_cannot_self_reactivate(self):
        make_user("dave", is_active=False)
        make_user("erin", is_active=False, is_email_verified=False)
        url = reverse("profile-reactivate")
        for name in ("dave", "erin"):
            r = self.client.post(url, {"identifier": name, "password": PASSWORD}, format="json")
            self.assertEqual(r.status_code, 403, name)
        self.assertFalse(User.objects.get(username="dave").is_active)

    def test_reactivate_active_account(self):
        r = self.client.post(reverse("profile-reactivate"), {"identifier": "alice", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 400)


class ChangePasswordTests(ProfileBase):
    """The change-password endpoint is still available and unaffected by the profile module."""

    url = "change-password"

    def test_change_password_works(self):
        tokens = self.login(self.alice)
        new = "An0ther!Passw0rd"
        r = self.client.post(reverse(self.url),
                             {"current_password": PASSWORD, "new_password": new, "confirm_password": new}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.post(reverse("login"), {"identifier": "alice", "password": new}, format="json").status_code, 200)
        self.assertEqual(self.client.post(reverse("login"), {"identifier": "alice", "password": PASSWORD}, format="json").status_code, 401)
        # the returned access token still works; the old one is revoked
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)

    def test_change_password_rejections(self):
        self.login(self.alice)
        url = reverse(self.url)
        new = "An0ther!Passw0rd"
        self.assertEqual(self.client.post(url, {"current_password": "bad", "new_password": new, "confirm_password": new}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"current_password": PASSWORD, "new_password": new, "confirm_password": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"current_password": PASSWORD, "new_password": "123", "confirm_password": "123"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"current_password": PASSWORD, "new_password": PASSWORD, "confirm_password": PASSWORD}, format="json").status_code, 400)
        self.client.credentials()
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 401)

    def test_profile_apis_never_touch_the_password(self):
        before = User.objects.get(pk=self.alice.pk).password
        self.as_user(self.alice)
        self.client.patch(reverse("profile-update"), {"password": "Hacked!12345", "bio": "x"}, format="json")
        self.client.patch(reverse("profile-settings"), {"profile_visibility": "public"}, format="json")
        self.assertEqual(User.objects.get(pk=self.alice.pk).password, before)


class ExistingModulesStillWorkTests(ProfileBase):
    def test_login_register_and_me_unchanged(self):
        r = self.client.post(reverse("login"), {"identifier": "alice", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["username"], "alice")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
        self.assertEqual(self.client.get(reverse("me")).json()["username"], "alice")

    def test_achievement_endpoints_still_mounted(self):
        make_achievement(self.alice, "public")
        self.as_user(self.bob)
        self.assertEqual(self.client.get(reverse("achievement-categories")).status_code, 200)
        self.assertEqual(self.client.get(reverse("user-achievements", args=[self.alice.id])).status_code, 200)

    def test_user_deletion_cascades_and_removes_picture(self):
        self.as_user(self.alice)
        self.client.post(reverse("profile-upload-picture"), {"profile_picture": image_upload()}, format="multipart")
        stored = UserProfile.objects.get(user=self.alice).profile_picture
        name, storage = stored.name, stored.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.alice.delete()
        self.assertFalse(UserProfile.objects.filter(user_id=self.alice.id).exists())
        self.assertFalse(storage.exists(name))
