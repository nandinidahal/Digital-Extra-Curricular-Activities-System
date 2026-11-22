"""Achievements module tests: submission, evidence, verification workflow, featured, privacy, stats."""
import datetime
import os
from urllib.parse import urlparse

from django.test import override_settings
from django.utils import timezone

from achievements.models import Achievement, AchievementCategory, AchievementEvidence, AchievementReview
from announcements.models import Announcement, Category
from common.testing import DEASTestCase
from notifications.models import Notification

BASE = "/api/achievements/"


class AchievementTestCase(DEASTestCase):
    def setUp(self):
        super().setUp()
        self.tech = AchievementCategory.objects.get(slug="technology")
        self.sports = AchievementCategory.objects.get(slug="sports")

    def payload(self, **extra):
        data = {
            "title": "National Robotics Olympiad - 1st place",
            "description": "Built an autonomous rover.",
            "category": str(self.tech.pk),
            "achievement_type": "competition",
            "organization": "Robotics Association",
            "event_name": "Robotics Olympiad 2026",
            "achievement_date": "2026-05-10",
            "location": "Kathmandu",
            "level": "national",
            "position": "1st place",
            "skills": ["Python", "Electronics"],
            "visibility": "public",
        }
        data.update(extra)
        return data

    def make(self, user=None, *, status="verified", visibility="public", **extra):
        fields = dict(
            user=user or self.alice, title=extra.pop("title", "Debate winner"), category=extra.pop("category", self.tech),
            achievement_date=datetime.date(2026, 3, 1), level=extra.pop("level", "national"),
            verification_status=status, visibility=visibility, submitted_at=timezone.now(),
            verified_at=timezone.now() if status == "verified" else None,
        )
        fields.update(extra)
        return Achievement.objects.create(**fields)

    def url(self, achievement, action=""):
        return f"{BASE}{achievement.pk}/{action + '/' if action else ''}"


class SubmissionTests(AchievementTestCase):
    def test_create_is_pending_and_owned(self):
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            data = self.assertOk(self.client.post(BASE, self.payload(), format="json"), 201)["achievement"]
        self.assertEqual((data["verification_status"], data["user"]["id"]), ("pending", str(self.alice.pk)))
        achievement = Achievement.objects.get(pk=data["id"])
        self.assertEqual(achievement.reviews.get().decision, "submitted")
        # reviewers (admin + coordinator) are told; the owner is not
        recipients = set(Notification.objects.filter(notification_type="achievement.submitted").values_list("recipient__username", flat=True))
        self.assertEqual(recipients, {"admin1", "coord1"})

    def test_visitor_cannot_create(self):
        self.assertError(self.client.post(BASE, self.payload(), format="json"), 401)

    def test_protected_fields_rejected(self):
        self.login(self.alice)
        for field, value in (("verification_status", "verified"), ("user", str(self.bob.pk)), ("is_featured", True),
                             ("verified_by", str(self.admin.pk)), ("submitted_at", timezone.now().isoformat())):
            with self.subTest(field=field):
                body = self.assertError(self.client.post(BASE, self.payload(**{field: value}), format="json"), 400)
                self.assertIn(field, body["errors"])
        self.assertFalse(Achievement.objects.exists())

    def test_validation(self):
        self.login(self.alice)
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        cases = {
            "achievement_date": tomorrow, "level": "galactic", "skills": ["a", "A"], "title": "",
            "description": "<b>bold</b>", "visibility": "everyone",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                self.assertIn(field, self.assertError(self.client.post(BASE, self.payload(**{field: value}), format="json"), 400)["errors"])

    def test_related_announcement_must_be_visible(self):
        category = Category.objects.get(slug="technology")
        private = Announcement.objects.create(author=self.bob, title="Secret", slug="secret-1", category=category, status="published",
                                              published_at=timezone.now(), visibility="private")
        public = Announcement.objects.create(author=self.bob, title="Open", slug="open-1", category=category, status="published",
                                             published_at=timezone.now())
        self.login(self.alice)
        self.assertIn("related_announcement", self.assertError(
            self.client.post(BASE, self.payload(related_announcement=str(private.pk)), format="json"), 400)["errors"])
        data = self.assertOk(self.client.post(BASE, self.payload(related_announcement=str(public.pk)), format="json"), 201)
        self.assertEqual(data["achievement"]["related_announcement"]["title"], "Open")

    def test_inactive_category_rejected(self):
        self.tech.is_active = False
        self.tech.save()
        self.login(self.alice)
        self.assertIn("category", self.assertError(self.client.post(BASE, self.payload(), format="json"), 400)["errors"])


class EvidenceTests(AchievementTestCase):
    def setUp(self):
        super().setUp()
        self.achievement = self.make(status="pending")

    def upload(self, *files, user=None):
        self.login(user or self.alice)
        return self.client.post(self.url(self.achievement, "evidence"), {"files": list(files)}, format="multipart")

    def test_upload_pdf_and_image_to_private_storage(self):
        data = self.assertOk(self.upload(self.pdf_file(), self.image_file("JPEG", name="My Cert (1).jpg")), 201)
        self.assertEqual([e["kind"] for e in data["evidence"]], ["pdf", "image"])
        self.assertEqual(data["evidence"][1]["original_name"], "My Cert 1.jpg")
        stored = self.files_in(self.private_root)
        self.assertEqual(len(stored), 2)
        self.assertEqual(self.files_in(self.media_root), [])  # never in public MEDIA_ROOT
        self.assertTrue(all("/achievements/" in path and "/evidence/" in path for path in stored))

    def test_invalid_evidence_rejected(self):
        for upload in (self.image_file("GIF"), self.pdf_file("x.pdf", b"MZ\x90\x00 not a pdf"), self.pdf_file("cert.png")):
            with self.subTest(name=upload.name):
                self.assertError(self.upload(upload), 400)
        self.assertEqual(AchievementEvidence.objects.count(), 0)
        self.assertEqual(self.files_in(self.private_root), [])

    @override_settings(ACHIEVEMENT_EVIDENCE_PDF_MAX_BYTES=50)
    def test_size_limit(self):
        self.assertError(self.upload(self.pdf_file()), 400)

    @override_settings(ACHIEVEMENT_MAX_EVIDENCE_FILES=2)
    def test_file_count_limit(self):
        self.assertOk(self.upload(self.pdf_file(), self.pdf_file()), 201)
        self.assertError(self.upload(self.pdf_file()), 400)

    def test_other_users_cannot_upload_or_delete(self):
        self.assertError(self.upload(self.pdf_file(), user=self.bob), 404)  # pending: invisible to others
        evidence_id = self.assertOk(self.upload(self.pdf_file()), 201)["evidence"][0]["id"]
        self.login(self.bob)
        self.assertError(self.client.delete(f"{BASE}evidence/{evidence_id}/"), 404)
        self.login(self.admin)
        self.assertError(self.client.delete(f"{BASE}evidence/{evidence_id}/"), 403)

    def test_owner_deletes_evidence_and_file(self):
        evidence_id = self.assertOk(self.upload(self.pdf_file()), 201)["evidence"][0]["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.delete(f"{BASE}evidence/{evidence_id}/"))
        self.assertEqual(self.files_in(self.private_root), [])

    def test_download_owner_reviewer_and_signed_link(self):
        evidence = self.assertOk(self.upload(self.pdf_file()), 201)["evidence"][0]
        path = f"{BASE}evidence/{evidence['id']}/download/"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
        self.login(self.coordinator)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.login(self.bob)
        self.assertError(self.client.get(path), 404)
        self.logout()
        self.assertError(self.client.get(path), 401)
        signed = urlparse(evidence["download_url"])
        self.assertEqual(self.client.get(f"{signed.path}?{signed.query}").status_code, 200)
        self.assertError(self.client.get(f"{signed.path}?token=forged"), 401)

    def test_evidence_hidden_from_public_detail(self):
        self.assertOk(self.upload(self.pdf_file()), 201)
        self.achievement.verification_status = "verified"
        self.achievement.verified_at = timezone.now()
        self.achievement.save()
        self.login(self.bob)
        data = self.assertOk(self.client.get(self.url(self.achievement)))["achievement"]
        self.assertNotIn("evidence", data)
        self.assertNotIn("rejection_reason", data)
        self.login(self.alice)
        self.assertEqual(len(self.assertOk(self.client.get(self.url(self.achievement)))["achievement"]["evidence"]), 1)


class VerificationWorkflowTests(AchievementTestCase):
    def setUp(self):
        super().setUp()
        self.login(self.alice)
        self.achievement_id = self.assertOk(self.client.post(BASE, self.payload(), format="json"), 201)["achievement"]["id"]

    def review(self, action, user, comments=""):
        self.login(user)
        return self.client.post(f"{BASE}{self.achievement_id}/{action}/", {"comments": comments} if comments else {}, format="json")

    def test_reviewer_verifies_and_owner_notified(self):
        with self.captureOnCommitCallbacks(execute=True):
            data = self.assertOk(self.review("verify", self.coordinator))["achievement"]
        self.assertEqual(data["verification_status"], "verified")
        achievement = Achievement.objects.get(pk=self.achievement_id)
        self.assertEqual(achievement.verified_by, self.coordinator)
        note = Notification.objects.get(recipient=self.alice, notification_type="achievement.verified")
        self.assertEqual(note.actor, self.coordinator)

    def test_regular_user_cannot_review_or_see_queue(self):
        self.assertError(self.review("verify", self.bob), 403)
        self.assertError(self.client.get(f"{BASE}pending/"), 403)

    def test_cannot_verify_own_achievement(self):
        self.login(self.admin)
        own = self.assertOk(self.client.post(BASE, self.payload(), format="json"), 201)["achievement"]["id"]
        self.assertError(self.client.post(f"{BASE}{own}/verify/"), 403, "cannot_review_own")
        self.assertNotIn(own, self.ids(self.assertOk(self.client.get(f"{BASE}pending/"))))
        self.assertIn(self.achievement_id, self.ids(self.assertOk(self.client.get(f"{BASE}pending/"))))

    def test_reject_requires_comment_and_records_reason(self):
        self.assertError(self.review("reject", self.admin), 400)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.review("reject", self.admin, "Certificate is not legible"))
        self.login(self.alice)
        data = self.assertOk(self.client.get(f"{BASE}{self.achievement_id}/"))["achievement"]
        self.assertEqual((data["verification_status"], data["rejection_reason"]), ("rejected", "Certificate is not legible"))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type="achievement.rejected").exists())
        email_note = Notification.objects.get(recipient=self.alice, notification_type="achievement.rejected")
        self.assertIn("Certificate is not legible", email_note.message)

    def test_request_information_then_resubmit_then_verify(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.review("request-information", self.coordinator, "Please upload the certificate"))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type="achievement.more_information_required").exists())
        self.login(self.alice)
        self.client.post(f"{BASE}{self.achievement_id}/evidence/", {"files": [self.pdf_file()]}, format="multipart")
        self.assertOk(self.client.post(f"{BASE}{self.achievement_id}/resubmit/", {"note": "Uploaded"}, format="json"))
        self.assertError(self.client.post(f"{BASE}{self.achievement_id}/resubmit/"), 400, "invalid_status_transition")
        self.assertOk(self.review("verify", self.coordinator))
        history = self.assertOk(self.client.get(f"{BASE}{self.achievement_id}/history/"))["history"]
        self.assertEqual([h["decision"] for h in history], ["submitted", "more_information_required", "resubmitted", "verified"])
        self.assertEqual(history[1]["reviewer"]["username"], "coord1")
        self.assertEqual((history[1]["previous_status"], history[1]["new_status"]), ("pending", "more_information_required"))

    def test_verified_cannot_be_reviewed_again(self):
        self.assertOk(self.review("verify", self.coordinator))
        self.assertError(self.review("reject", self.admin, "x"), 400, "not_reviewable")

    def test_history_private(self):
        self.login(self.bob)
        self.assertError(self.client.get(f"{BASE}{self.achievement_id}/history/"), 404)

    def test_material_change_triggers_reverification(self):
        self.assertOk(self.review("verify", self.coordinator))
        self.login(self.alice)
        self.assertOk(self.client.post(f"{BASE}{self.achievement_id}/feature/"))
        data = self.assertOk(self.client.patch(f"{BASE}{self.achievement_id}/", {"visibility": "members_only", "skills": ["Python"]}, format="json"))
        self.assertEqual(data["achievement"]["verification_status"], "verified")  # not material
        response = self.client.patch(f"{BASE}{self.achievement_id}/", {"position": "Winner"}, format="json")
        data = self.assertOk(response)
        self.assertEqual(data["achievement"]["verification_status"], "pending")
        self.assertFalse(data["achievement"]["is_featured"])
        self.assertIn("sent back for verification", response.json()["message"])
        self.assertEqual(AchievementReview.objects.filter(achievement_id=self.achievement_id).last().decision, "reverification_required")

    def test_new_evidence_on_verified_triggers_reverification(self):
        self.assertOk(self.review("verify", self.coordinator))
        self.login(self.alice)
        self.client.post(f"{BASE}{self.achievement_id}/evidence/", {"files": [self.pdf_file()]}, format="multipart")
        self.assertEqual(Achievement.objects.get(pk=self.achievement_id).verification_status, "pending")

    def test_uploading_evidence_does_not_verify(self):
        self.login(self.alice)
        self.client.post(f"{BASE}{self.achievement_id}/evidence/", {"files": [self.pdf_file()]}, format="multipart")
        self.assertEqual(Achievement.objects.get(pk=self.achievement_id).verification_status, "pending")


class FeaturedTests(AchievementTestCase):
    def test_only_verified_can_be_featured(self):
        pending = self.make(status="pending")
        self.login(self.alice)
        self.assertError(self.client.post(self.url(pending, "feature")), 400, "not_verified")

    @override_settings(ACHIEVEMENT_MAX_FEATURED=2)
    def test_limit_and_unfeature(self):
        items = [self.make(title=f"A{i}") for i in range(3)]
        self.login(self.alice)
        self.assertOk(self.client.post(self.url(items[0], "feature")))
        self.assertOk(self.client.post(self.url(items[1], "feature")))
        self.assertError(self.client.post(self.url(items[2], "feature")), 400, "featured_limit_reached")
        self.assertOk(self.client.delete(self.url(items[0], "feature")))
        self.assertOk(self.client.post(self.url(items[2], "feature")))
        featured = self.ids(self.assertOk(self.client.get(f"{BASE}featured/?user_id={self.alice.pk}")))
        self.assertEqual(set(featured), {str(items[1].pk), str(items[2].pk)})

    def test_other_user_cannot_feature_admin_can_and_owner_notified(self):
        item = self.make()
        self.login(self.bob)
        self.assertError(self.client.post(self.url(item, "feature")), 403)
        self.login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post(self.url(item, "feature")))
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type="achievement.featured").exists())

    def test_featured_listing_respects_visibility(self):
        public = self.make(is_featured=True, title="Public")
        private = self.make(is_featured=True, title="Private", visibility="private")
        ids = self.ids(self.assertOk(self.client.get(f"{BASE}featured/")))
        self.assertIn(str(public.pk), ids)
        self.assertNotIn(str(private.pk), ids)
        self.assertError(self.client.get(f"{BASE}featured/?user_id=nope"), 400)


class PrivacyTests(AchievementTestCase):
    def setUp(self):
        super().setUp()
        self.public = self.make(title="Public win")
        self.members = self.make(title="Members win", visibility="members_only")
        self.private = self.make(title="Private win", visibility="private")
        self.pending = self.make(title="Pending win", status="pending")
        self.rejected = self.make(title="Rejected win", status="rejected")

    def test_visitor_sees_verified_public_only(self):
        listing = self.ids(self.assertOk(self.client.get(f"{BASE}users/{self.alice.pk}/")))
        self.assertEqual(listing, [str(self.public.pk)])
        self.assertError(self.client.get(self.url(self.members)), 401, "authentication_required")
        for item in (self.private, self.pending, self.rejected):
            self.assertError(self.client.get(self.url(item)), 404)

    def test_member_sees_members_only_but_not_private_or_unverified(self):
        self.login(self.bob)
        listing = set(self.ids(self.assertOk(self.client.get(f"{BASE}users/{self.alice.pk}/"))))
        self.assertEqual(listing, {str(self.public.pk), str(self.members.pk)})
        self.assertEqual(set(self.ids(self.assertOk(self.client.get(f"{BASE}search/?q=win")))), listing)

    def test_owner_sees_everything_in_me(self):
        self.login(self.alice)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{BASE}me/")))), 5)
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{BASE}me/?status=pending"))), [str(self.pending.pk)])

    def test_reviewer_can_open_pending(self):
        self.login(self.coordinator)
        self.assertOk(self.client.get(self.url(self.pending)))

    def test_others_cannot_modify_or_delete(self):
        self.login(self.bob)
        self.assertError(self.client.patch(self.url(self.public), {"title": "Mine"}, format="json"), 403, "not_owner")
        self.assertError(self.client.delete(self.url(self.public)), 403, "not_owner")
        self.assertError(self.client.patch(self.url(self.private), {"title": "Mine"}, format="json"), 404)

    def test_blocked_user_cannot_see(self):
        self.block(self.alice, self.bob)
        self.login(self.bob)
        self.assertError(self.client.get(self.url(self.public)), 404)
        self.assertError(self.client.get(f"{BASE}users/{self.alice.pk}/"), 404)
        self.assertNotIn(str(self.public.pk), self.ids(self.assertOk(self.client.get(BASE))))

    def test_owner_delete_removes_evidence_files(self):
        self.login(self.alice)
        self.client.post(self.url(self.pending, "evidence"), {"files": [self.pdf_file()]}, format="multipart")
        self.assertEqual(len(self.files_in(self.private_root)), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.delete(self.url(self.pending)))
        self.assertEqual(self.files_in(self.private_root), [])


class StatsAndCategoryTests(AchievementTestCase):
    def test_own_stats(self):
        self.make(title="v1", level="national")
        self.make(title="v2", level="international", category=self.sports, is_featured=True)
        self.make(title="p", status="pending")
        self.make(title="r", status="rejected")
        self.make(self.bob, title="bob's")
        self.login(self.alice)
        stats = self.assertOk(self.client.get(f"{BASE}stats/"))["statistics"]
        self.assertEqual((stats["total"], stats["verified"], stats["pending"], stats["rejected"], stats["featured"]), (4, 2, 1, 1, 1))
        self.assertEqual(stats["by_level"]["national"], 3)
        self.assertEqual({c["slug"]: c["count"] for c in stats["by_category"]}, {"technology": 3, "sports": 1})

    def test_platform_stats_reviewers_only(self):
        self.make()
        self.make(self.bob)
        self.login(self.alice)
        self.assertError(self.client.get(f"{BASE}stats/?scope=platform"), 403)
        self.login(self.admin)
        self.assertEqual(self.assertOk(self.client.get(f"{BASE}stats/?scope=platform"))["statistics"]["total"], 2)

    def test_categories_endpoint(self):
        names = [c["name"] for c in self.assertOk(self.client.get("/api/achievement-categories/"))["results"]]
        self.assertEqual(len(names), 11)
        self.assertIn("Academic", names)

    def test_search_requires_login_and_filters(self):
        self.make(title="Chess champion", skills=["Strategy"], level="local")
        self.make(title="Swimming gold", category=self.sports)
        self.assertError(self.client.get(f"{BASE}search/?q=chess"), 401)
        self.login(self.bob)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{BASE}search/?q=chess")))), 1)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{BASE}search/?skill=strategy")))), 1)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{BASE}search/?category=sports")))), 1)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{BASE}search/?level=local")))), 1)


class EvidenceStorageIsolationTest(AchievementTestCase):
    def test_private_root_outside_media_root_and_no_storage_url_exposed(self):
        from django.conf import settings

        media = os.path.abspath(str(settings.MEDIA_ROOT)) + os.sep
        self.assertFalse(os.path.abspath(str(settings.PRIVATE_MEDIA_ROOT)).startswith(media))
        achievement = self.make(status="pending")
        self.login(self.alice)
        self.client.post(self.url(achievement, "evidence"), {"files": [self.pdf_file()]}, format="multipart")
        body = self.client.get(self.url(achievement)).content.decode()
        stored_name = AchievementEvidence.objects.get().file.name
        self.assertNotIn(stored_name, body)  # only the signed download endpoint is exposed
        self.assertNotIn("/media/", body)
