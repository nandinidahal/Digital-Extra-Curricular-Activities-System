"""Announcements module tests (user-based creation, lifecycle, visibility, search, bookmarks, reports)."""
from datetime import timedelta
from unittest import mock

from django.utils import timezone

from announcements import services
from announcements.models import Announcement, AnnouncementBookmark, AnnouncementReport, Category
from common.testing import DEASTestCase
from notifications.models import Notification

BASE = "/api/announcements/"


def future(days=7, hours=0):
    return timezone.now() + timedelta(days=days, hours=hours)


class AnnouncementTestCase(DEASTestCase):
    def setUp(self):
        super().setUp()
        self.tech = Category.objects.get(slug="technology")
        self.sports = Category.objects.get(slug="sports")

    def payload(self, **extra):
        data = {
            "title": "Robotics Workshop",
            "short_description": "Build a robot in a day",
            "description": "Hands-on robotics workshop for beginners.",
            "category": str(self.tech.pk),
            "activity_type": "physical",
            "organizer_name": "Robotics Club",
            "organizer_email": "club@example.com",
            "organizer_phone": "+977 1 5551234",
            "location": "Hall A, Kathmandu",
            "start_datetime": future(10).isoformat(),
            "end_datetime": future(10, 4).isoformat(),
            "registration_deadline": future(8).isoformat(),
            "registration_link": "https://example.com/register",
            "eligibility_criteria": "Students aged 15+",
            "requirements": "Laptop",
        }
        data.update(extra)
        return data

    def make(self, author=None, *, status="published", visibility="public", **extra):
        fields = dict(
            author=author or self.alice, title=extra.pop("title", "Hackathon"), slug=extra.pop("slug", None),
            short_description="Short", description="Long description", category=extra.pop("category", self.tech),
            activity_type="physical", location=extra.pop("location", "Kathmandu"), start_datetime=extra.pop("start", future(5)),
            status=status, visibility=visibility,
            published_at=timezone.now() if status == "published" else None,
        )
        fields.update(extra)
        if fields["slug"] is None:
            import uuid

            fields["slug"] = f"a-{uuid.uuid4().hex[:10]}"
        return Announcement.objects.create(**fields)

    def url(self, announcement, action=""):
        return f"{BASE}{announcement.pk}/{action + '/' if action else ''}"


class CreationTests(AnnouncementTestCase):
    def test_authenticated_user_creates_draft_and_becomes_author(self):
        self.login(self.alice)
        data = self.assertOk(self.client.post(BASE, self.payload(), format="json"), 201)["announcement"]
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["author"]["id"], str(self.alice.pk))
        announcement = Announcement.objects.get(pk=data["id"])
        self.assertEqual(announcement.author, self.alice)
        self.assertIsNone(announcement.published_at)

    def test_regular_user_does_not_need_admin_role(self):
        self.assertEqual(self.bob.role, "user")
        self.login(self.bob)
        self.assertOk(self.client.post(BASE, self.payload(status="published"), format="json"), 201)

    def test_visitor_cannot_create(self):
        self.assertError(self.client.post(BASE, self.payload(), format="json"), 401)

    def test_cannot_assign_author_or_protected_fields(self):
        self.login(self.alice)
        for field, value in (("author", str(self.bob.pk)), ("published_at", timezone.now().isoformat()),
                             ("slug", "x"), ("is_edited", True), ("archived_by", str(self.bob.pk))):
            with self.subTest(field=field):
                body = self.assertError(self.client.post(BASE, self.payload(**{field: value}), format="json"), 400, "validation_error")
                self.assertIn(field, body["errors"])
        self.assertFalse(Announcement.objects.exists())

    def test_create_published_directly(self):
        self.login(self.alice)
        data = self.assertOk(self.client.post(BASE, self.payload(status="published"), format="json"), 201)["announcement"]
        self.assertEqual(data["status"], "published")
        self.assertIsNotNone(data["published_at"])

    def test_status_archived_not_allowed_on_create(self):
        self.login(self.alice)
        self.assertError(self.client.post(BASE, self.payload(status="archived"), format="json"), 400)

    def test_title_required(self):
        self.login(self.alice)
        body = self.assertError(self.client.post(BASE, self.payload(title="   "), format="json"), 400)
        self.assertIn("title", body["errors"])

    def test_draft_may_be_incomplete_but_publish_validates(self):
        self.login(self.alice)
        data = self.assertOk(self.client.post(BASE, {"title": "Idea"}, format="json"), 201)["announcement"]
        body = self.assertError(self.client.post(f"{BASE}{data['id']}/publish/"), 400, "validation_error")
        for field in ("short_description", "description", "category", "start_datetime", "location"):
            self.assertIn(field, body["errors"])

    def test_inactive_category_rejected_for_new_announcements(self):
        self.tech.is_active = False
        self.tech.save()
        self.login(self.alice)
        body = self.assertError(self.client.post(BASE, self.payload(), format="json"), 400)
        self.assertIn("category", body["errors"])

    def test_existing_announcement_keeps_deactivated_category(self):
        announcement = self.make()
        self.tech.is_active = False
        self.tech.save()
        self.login(self.alice)
        self.assertOk(self.client.patch(self.url(announcement), {"title": "New title"}, format="json"))
        announcement.refresh_from_db()
        self.assertEqual(announcement.category, self.tech)

    def test_html_and_script_links_rejected(self):
        self.login(self.alice)
        for field, value in (("description", "<script>alert(1)</script>"), ("registration_link", "javascript:alert(1)"),
                             ("online_link", "ftp://example.com"), ("title", "two\nlines")):
            with self.subTest(field=field):
                body = self.assertError(self.client.post(BASE, self.payload(**{field: value}), format="json"), 400)
                self.assertIn(field, body["errors"])

    def test_email_and_phone_validated(self):
        self.login(self.alice)
        self.assertIn("organizer_email", self.assertError(self.client.post(BASE, self.payload(organizer_email="nope"), format="json"), 400)["errors"])
        self.assertIn("organizer_phone", self.assertError(self.client.post(BASE, self.payload(organizer_phone="call me"), format="json"), 400)["errors"])


class DateAndActivityValidationTests(AnnouncementTestCase):
    def setUp(self):
        super().setUp()
        self.login(self.alice)

    def test_end_before_start_rejected(self):
        body = self.assertError(self.client.post(BASE, self.payload(end_datetime=future(9).isoformat()), format="json"), 400)
        self.assertIn("end_datetime", body["errors"])

    def test_deadline_after_start_rejected(self):
        body = self.assertError(self.client.post(BASE, self.payload(registration_deadline=future(11).isoformat()), format="json"), 400)
        self.assertIn("registration_deadline", body["errors"])

    def test_past_event_cannot_be_published(self):
        payload = self.payload(start_datetime=(timezone.now() - timedelta(days=2)).isoformat(),
                               end_datetime=(timezone.now() - timedelta(days=1)).isoformat(),
                               registration_deadline=(timezone.now() - timedelta(days=3)).isoformat(), status="published")
        self.assertIn("start_datetime", self.assertError(self.client.post(BASE, payload, format="json"), 400)["errors"])

    def test_physical_requires_location(self):
        body = self.assertError(self.client.post(BASE, self.payload(location="", status="published"), format="json"), 400)
        self.assertIn("location", body["errors"])

    def test_online_requires_link(self):
        body = self.assertError(self.client.post(BASE, self.payload(activity_type="online", location="", status="published"), format="json"), 400)
        self.assertIn("online_link", body["errors"])
        self.assertOk(self.client.post(BASE, self.payload(activity_type="online", location="", online_link="https://meet.example.com/x", status="published"), format="json"), 201)

    def test_hybrid_requires_both(self):
        body = self.assertError(self.client.post(BASE, self.payload(activity_type="hybrid", location="", status="published"), format="json"), 400)
        self.assertIn("location", body["errors"])
        self.assertIn("online_link", body["errors"])

    def test_invalid_activity_type_and_visibility(self):
        self.assertIn("activity_type", self.assertError(self.client.post(BASE, self.payload(activity_type="virtual"), format="json"), 400)["errors"])
        self.assertIn("visibility", self.assertError(self.client.post(BASE, self.payload(visibility="secret"), format="json"), 400)["errors"])


class CoverImageTests(AnnouncementTestCase):
    def test_valid_cover_accepted_and_reencoded(self):
        self.login(self.alice)
        payload = self.payload()
        payload["cover_image"] = self.image_file("JPEG")
        data = self.assertOk(self.client.post(BASE, payload, format="multipart"), 201)["announcement"]
        self.assertTrue(data["cover_image"].startswith("http://testserver/media/announcements/covers/"))
        self.assertEqual(len(self.files_in(self.media_root)), 1)

    def test_invalid_cover_rejected(self):
        self.login(self.alice)
        for upload in (self.image_file("GIF"), self.pdf_file("cover.pdf")):
            with self.subTest(upload=upload.name):
                payload = self.payload()
                payload["cover_image"] = upload
                body = self.assertError(self.client.post(BASE, payload, format="multipart"), 400)
                self.assertIn("cover_image", body["errors"])
        self.assertEqual(self.files_in(self.media_root), [])

    def test_replace_and_remove_cover_cleans_old_files(self):
        self.login(self.alice)
        payload = self.payload()
        payload["cover_image"] = self.image_file("PNG")
        with self.captureOnCommitCallbacks(execute=True):
            announcement_id = self.assertOk(self.client.post(BASE, payload, format="multipart"), 201)["announcement"]["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.patch(f"{BASE}{announcement_id}/", {"cover_image": self.image_file("WEBP")}, format="multipart"))
        files = self.files_in(self.media_root)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith(".webp"))
        with self.captureOnCommitCallbacks(execute=True):
            data = self.assertOk(self.client.patch(f"{BASE}{announcement_id}/", {"remove_cover_image": True}, format="json"))
        self.assertIsNone(data["announcement"]["cover_image"])
        self.assertEqual(self.files_in(self.media_root), [])


class VisibilityTests(AnnouncementTestCase):
    def test_draft_invisible_to_visitors_and_others(self):
        draft = self.make(status="draft")
        self.assertError(self.client.get(self.url(draft)), 404)
        self.login(self.bob)
        self.assertError(self.client.get(self.url(draft)), 404)
        self.assertNotIn(str(draft.pk), self.ids(self.assertOk(self.client.get(BASE))))
        self.login(self.alice)
        self.assertOk(self.client.get(self.url(draft)))

    def test_published_public_visible_without_login(self):
        announcement = self.make()
        data = self.assertOk(self.client.get(self.url(announcement)))["announcement"]
        self.assertEqual(data["title"], "Hackathon")
        self.assertIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(f"{BASE}public/"))))
        self.assertOk(self.client.get(f"{BASE}slug/{announcement.slug}/"))

    def test_members_only_requires_login(self):
        announcement = self.make(visibility="members_only")
        self.assertError(self.client.get(self.url(announcement)), 401, "authentication_required")
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(f"{BASE}public/"))))
        self.login(self.bob)
        self.assertOk(self.client.get(self.url(announcement)))
        self.assertIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(BASE))))

    def test_private_only_author_and_admin(self):
        announcement = self.make(visibility="private")
        self.assertError(self.client.get(self.url(announcement)), 404)
        self.login(self.bob)
        self.assertError(self.client.get(self.url(announcement)), 404)
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(BASE))))
        for user in (self.alice, self.admin):
            self.login(user)
            self.assertOk(self.client.get(self.url(announcement)))

    def test_archived_not_in_public_listings(self):
        announcement = self.make(status="archived")
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(f"{BASE}public/"))))
        self.assertError(self.client.get(self.url(announcement)), 404)
        self.login(self.bob)
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(BASE))))

    def test_inactive_author_hidden(self):
        announcement = self.make()
        self.alice.is_active = False
        self.alice.save()
        self.assertError(self.client.get(self.url(announcement)), 404)

    def test_blocked_users_do_not_see_each_others_announcements(self):
        announcement = self.make()
        self.block(self.alice, self.bob)
        self.login(self.bob)
        self.assertError(self.client.get(self.url(announcement)), 404)
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(BASE))))
        self.assertNotIn(str(announcement.pk), self.ids(self.assertOk(self.client.get(f"{BASE}public/"))))

    def test_private_organizer_info_not_exposed(self):
        announcement = self.make(organizer_email="org@example.com", organizer_phone="+977 1234567",
                                 contact_information="Call Ram", online_link="https://meet.example.com/abc")
        visitor = self.assertOk(self.client.get(self.url(announcement)))["announcement"]
        for field in ("organizer_email", "organizer_phone", "contact_information", "online_link"):
            self.assertIsNone(visitor[field], field)
        self.assertTrue(visitor["contact_details_hidden"])
        self.assertTrue(visitor["requires_login_for_online_link"])
        self.assertNotIn("org@example.com", str(self.client.get(f"{BASE}public/").content))
        self.login(self.bob)
        member = self.assertOk(self.client.get(self.url(announcement)))["announcement"]
        self.assertIsNone(member["organizer_email"])
        self.assertEqual(member["online_link"], "https://meet.example.com/abc")
        announcement.show_contact_details = True
        announcement.save()
        member = self.assertOk(self.client.get(self.url(announcement)))["announcement"]
        self.assertEqual(member["organizer_email"], "org@example.com")
        self.login(self.alice)
        own = self.assertOk(self.client.get(self.url(announcement)))["announcement"]
        self.assertEqual(own["organizer_phone"], "+977 1234567")

    def test_uuid_guessing_returns_404(self):
        import uuid

        self.assertError(self.client.get(f"{BASE}{uuid.uuid4()}/"), 404, "announcement_not_found")


class OwnershipAndLifecycleTests(AnnouncementTestCase):
    def test_owner_can_edit_and_edited_flag_set_after_publication(self):
        announcement = self.make()
        self.login(self.alice)
        data = self.assertOk(self.client.patch(self.url(announcement), {"title": "Hackathon 2.0"}, format="json"))["announcement"]
        self.assertEqual(data["title"], "Hackathon 2.0")
        self.assertTrue(data["is_edited"])

    def test_other_user_cannot_edit_delete_publish_or_archive(self):
        announcement = self.make()
        draft = self.make(status="draft")
        self.login(self.bob)
        self.assertError(self.client.patch(self.url(announcement), {"title": "Hacked"}, format="json"), 403, "not_owner")
        self.assertError(self.client.delete(self.url(announcement)), 403, "not_owner")
        self.assertError(self.client.post(self.url(announcement, "archive")), 403, "not_owner")
        self.assertError(self.client.post(self.url(draft, "publish")), 404)
        announcement.refresh_from_db()
        self.assertEqual((announcement.title, announcement.status), ("Hackathon", "published"))

    def test_status_cannot_be_changed_by_patch(self):
        announcement = self.make(status="draft")
        self.login(self.alice)
        self.assertError(self.client.patch(self.url(announcement), {"status": "published"}, format="json"), 400)

    def test_publish_archive_restore_cycle(self):
        self.login(self.alice)
        announcement_id = self.assertOk(self.client.post(BASE, self.payload(), format="json"), 201)["announcement"]["id"]
        url = f"{BASE}{announcement_id}/"
        self.assertEqual(self.assertOk(self.client.post(url + "publish/"))["announcement"]["status"], "published")
        self.assertEqual(self.assertOk(self.client.post(url + "publish/"))["announcement"]["status"], "published")  # idempotent
        self.assertEqual(self.assertOk(self.client.post(url + "archive/"))["announcement"]["status"], "archived")
        self.assertError(self.client.patch(url, {"title": "x"}, format="json"), 400, "announcement_archived")
        self.assertError(self.client.post(url + "publish/"), 400, "invalid_status_transition")
        self.assertEqual(self.assertOk(self.client.post(url + "restore/"))["announcement"]["status"], "draft")
        self.assertError(self.client.post(url + "restore/"), 400, "invalid_status_transition")

    def test_owner_can_delete(self):
        announcement = self.make()
        self.login(self.alice)
        self.assertOk(self.client.delete(self.url(announcement)))
        self.assertFalse(Announcement.objects.filter(pk=announcement.pk).exists())

    def test_moderator_can_archive_and_delete_but_not_edit(self):
        announcement = self.make()
        self.login(self.admin)
        self.assertError(self.client.patch(self.url(announcement), {"title": "x"}, format="json"), 403)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post(self.url(announcement, "archive")))
        announcement.refresh_from_db()
        self.assertEqual(announcement.archived_by, self.admin)
        self.assertTrue(Notification.objects.filter(recipient=self.alice, notification_type="announcement.archived").exists())
        self.login(self.coordinator)
        self.assertOk(self.client.delete(self.url(announcement)))

    def test_my_announcement_lists(self):
        draft, published, archived = self.make(status="draft"), self.make(), self.make(status="archived")
        self.make(self.bob)
        self.login(self.alice)
        self.assertEqual(set(self.ids(self.assertOk(self.client.get(f"{BASE}me/")))), {str(draft.pk), str(published.pk), str(archived.pk)})
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{BASE}me/drafts/"))), [str(draft.pk)])
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{BASE}me/published/"))), [str(published.pk)])
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{BASE}me/archived/"))), [str(archived.pk)])
        self.logout()
        self.assertError(self.client.get(f"{BASE}me/"), 401)


class SearchAndFilterTests(AnnouncementTestCase):
    def setUp(self):
        super().setUp()
        self.robotics = self.make(title="Robotics Bootcamp", location="Pokhara", start=future(3))
        self.football = self.make(self.bob, title="Football Cup", category=self.sports, start=future(20))
        self.past = self.make(title="Old Robotics Meetup", start=timezone.now() - timedelta(days=3),
                              end_datetime=timezone.now() - timedelta(days=2))
        self.secret = self.make(self.bob, title="Robotics secret", visibility="private")
        self.draft = self.make(self.bob, title="Robotics draft", status="draft")

    def search(self, query):
        return set(self.ids(self.assertOk(self.client.get(f"{BASE}search/{query}"))))

    def test_search_requires_login(self):
        self.assertError(self.client.get(f"{BASE}search/?q=robotics"), 401)

    def test_search_respects_visibility(self):
        self.login(self.carol)
        self.assertEqual(self.search("?q=robotics"), {str(self.robotics.pk), str(self.past.pk)})

    def test_public_listing_ignores_text_search(self):
        ids = set(self.ids(self.assertOk(self.client.get(f"{BASE}public/?q=football"))))
        self.assertIn(str(self.robotics.pk), ids)

    def test_filters(self):
        self.login(self.carol)
        self.assertEqual(self.search("?category=sports"), {str(self.football.pk)})
        self.assertEqual(self.search(f"?category={self.sports.pk}"), {str(self.football.pk)})
        self.assertEqual(self.search("?location=pokhara"), {str(self.robotics.pk)})
        self.assertEqual(self.search("?when=past"), {str(self.past.pk)})
        self.assertEqual(self.search("?when=upcoming"), {str(self.robotics.pk), str(self.football.pk)})
        start_to = (timezone.now() + timedelta(days=10)).isoformat().replace("+", "%2B")
        self.assertEqual(self.search(f"?when=upcoming&start_to={start_to}"), {str(self.robotics.pk)})
        ordered = self.ids(self.assertOk(self.client.get(f"{BASE}search/?when=upcoming&ordering=-start")))
        self.assertEqual(ordered, [str(self.football.pk), str(self.robotics.pk)])

    def test_registration_open_filter(self):
        Announcement.objects.filter(pk=self.robotics.pk).update(registration_deadline=timezone.now() - timedelta(hours=1))
        self.login(self.carol)
        self.assertEqual(self.search("?registration_open=true"), {str(self.football.pk)})

    def test_status_filter_does_not_leak_others_drafts(self):
        self.login(self.carol)
        self.assertEqual(set(self.ids(self.assertOk(self.client.get(f"{BASE}?status=draft")))), {str(self.robotics.pk), str(self.football.pk), str(self.past.pk)})
        self.login(self.admin)
        self.assertEqual(set(self.ids(self.assertOk(self.client.get(f"{BASE}?status=draft")))), {str(self.draft.pk)})

    def test_invalid_filter_rejected(self):
        self.login(self.carol)
        self.assertError(self.client.get(f"{BASE}search/?when=tomorrow"), 400)

    def test_list_query_count_is_constant(self):
        for i in range(5):
            self.make(self.carol, title=f"Extra {i}")
        self.login(self.bob)
        with self.assertNumQueries(5):  # JWT user + block ids (2) + count + page, whatever the page size
            self.client.get(f"{BASE}search/")


class BookmarkTests(AnnouncementTestCase):
    def test_bookmark_flow_and_duplicates(self):
        announcement = self.make()
        self.login(self.bob)
        self.assertOk(self.client.post(self.url(announcement, "bookmark")), 201)
        self.assertOk(self.client.post(self.url(announcement, "bookmark")), 200)
        self.assertEqual(AnnouncementBookmark.objects.count(), 1)
        self.assertTrue(self.assertOk(self.client.get(self.url(announcement)))["announcement"]["is_bookmarked"])
        listing = self.assertOk(self.client.get(f"{BASE}bookmarks/"))
        self.assertEqual(listing["results"][0]["announcement"]["id"], str(announcement.pk))
        self.assertOk(self.client.delete(self.url(announcement, "bookmark")))
        self.assertOk(self.client.delete(self.url(announcement, "bookmark")))
        self.assertEqual(AnnouncementBookmark.objects.count(), 0)

    def test_visitor_cannot_bookmark(self):
        self.assertError(self.client.post(self.url(self.make(), "bookmark")), 401)

    def test_users_only_see_their_own_bookmarks(self):
        announcement = self.make()
        AnnouncementBookmark.objects.create(user=self.bob, announcement=announcement)
        self.login(self.carol)
        self.assertEqual(self.assertOk(self.client.get(f"{BASE}bookmarks/"))["results"], [])

    def test_cannot_bookmark_inaccessible(self):
        self.login(self.bob)
        self.assertError(self.client.post(self.url(self.make(visibility="private"), "bookmark")), 404)
        self.assertError(self.client.post(self.url(self.make(status="draft"), "bookmark")), 404)

    def test_bookmark_hides_content_when_announcement_becomes_inaccessible(self):
        announcement = self.make()
        AnnouncementBookmark.objects.create(user=self.bob, announcement=announcement)
        announcement.visibility = "private"
        announcement.save()
        self.login(self.bob)
        item = self.assertOk(self.client.get(f"{BASE}bookmarks/"))["results"][0]
        self.assertFalse(item["available"])
        self.assertIsNone(item["announcement"])
        self.assertNotIn("Hackathon", str(item))


class ReportTests(AnnouncementTestCase):
    def test_report_and_duplicate(self):
        announcement = self.make()
        self.login(self.bob)
        receipt = self.assertOk(self.client.post(self.url(announcement, "report"), {"reason": "spam", "description": "Ads"}, format="json"), 201)
        self.assertEqual(receipt["report"]["status"], "pending")
        self.assertError(self.client.post(self.url(announcement, "report"), {"reason": "spam"}, format="json"), 409, "already_reported")

    def test_cannot_report_own_or_as_visitor(self):
        announcement = self.make()
        self.assertError(self.client.post(self.url(announcement, "report"), {"reason": "spam"}, format="json"), 401)
        self.login(self.alice)
        self.assertError(self.client.post(self.url(announcement, "report"), {"reason": "spam"}, format="json"), 400, "cannot_report_own_content")

    def test_moderation_api_restricted(self):
        announcement = self.make()
        report = AnnouncementReport.objects.create(reporter=self.bob, announcement=announcement, reason="fraudulent")
        self.assertError(self.client.get(f"{BASE}reports/"), 401)
        self.login(self.carol)
        self.assertError(self.client.get(f"{BASE}reports/"), 403)
        self.assertError(self.client.patch(f"{BASE}reports/{report.pk}/", {"status": "resolved"}, format="json"), 403)

    def test_moderator_resolves_and_archives(self):
        announcement = self.make()
        report = AnnouncementReport.objects.create(reporter=self.bob, announcement=announcement, reason="fraudulent")
        self.login(self.coordinator)
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{BASE}reports/?status=pending"))), [str(report.pk)])
        data = self.assertOk(self.client.patch(
            f"{BASE}reports/{report.pk}/", {"status": "resolved", "review_comments": "Scam", "action": "archived"}, format="json"
        ))["report"]
        self.assertEqual((data["status"], data["action_taken"], data["reviewed_by"]["username"]), ("resolved", "archived", "coord1"))
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, "archived")
        self.assertError(self.client.patch(f"{BASE}reports/{report.pk}/", {"status": "pending"}, format="json"), 400, "invalid_status_transition")
        # after resolution the same user may report again
        announcement.status = "published"
        announcement.save()
        self.login(self.bob)
        self.assertOk(self.client.post(self.url(announcement, "report"), {"reason": "spam"}, format="json"), 201)


class CategoryApiTests(AnnouncementTestCase):
    def test_public_list_has_seeded_active_categories(self):
        names = {c["name"] for c in self.assertOk(self.client.get("/api/categories/"))["results"]}
        self.assertIn("Workshops and Training", names)
        self.assertEqual(len(names), 14)

    def test_only_admin_manages_categories(self):
        self.login(self.alice)
        self.assertError(self.client.post("/api/categories/", {"name": "Debate"}, format="json"), 403)
        self.login(self.admin)
        created = self.assertOk(self.client.post("/api/categories/", {"name": "Debate"}, format="json"), 201)["category"]
        self.assertEqual(created["slug"], "debate")
        body = self.assertError(self.client.post("/api/categories/", {"name": "debate"}, format="json"), 400)
        self.assertIn("name", body["errors"])

    def test_category_in_use_is_deactivated_not_deleted(self):
        self.make()
        self.login(self.admin)
        self.assertEqual(self.assertOk(self.client.delete(f"/api/categories/{self.tech.pk}/"))["result"], "deactivated")
        self.tech.refresh_from_db()
        self.assertFalse(self.tech.is_active)
        self.assertNotIn("technology", [c["slug"] for c in self.assertOk(self.client.get("/api/categories/"))["results"]])
        unused = Category.objects.create(name="Unused", slug="unused")
        self.assertEqual(self.assertOk(self.client.delete(f"/api/categories/{unused.pk}/"))["result"], "deleted")


class AnnouncementNotificationTests(AnnouncementTestCase):
    def test_publication_notifies_friends_once(self):
        self.befriend(self.alice, self.bob)
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            announcement_id = self.assertOk(self.client.post(BASE, self.payload(status="published"), format="json"), 201)["announcement"]["id"]
        notes = Notification.objects.filter(notification_type="announcement.published")
        self.assertEqual([n.recipient for n in notes], [self.bob])
        self.assertEqual(notes[0].target_id, announcement_id)
        url = f"{BASE}{announcement_id}/"
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url + "archive/")
            self.client.post(url + "restore/")
            self.client.post(url + "publish/")
        self.assertEqual(Notification.objects.filter(notification_type="announcement.published").count(), 1)
        self.assertFalse(Notification.objects.filter(recipient=self.carol).exists())

    def test_private_publication_notifies_nobody(self):
        self.befriend(self.alice, self.bob)
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(BASE, self.payload(status="published", visibility="private"), format="json")
        self.assertFalse(Notification.objects.filter(notification_type="announcement.published").exists())

    def test_draft_creation_confirms_to_author(self):
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(BASE, self.payload(), format="json")
        self.assertEqual(Notification.objects.get().notification_type, "announcement.created")

    def test_meaningful_update_notifies_bookmarkers_only(self):
        announcement = self.make()
        AnnouncementBookmark.objects.create(user=self.bob, announcement=announcement)
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(self.url(announcement), {"description": "Typos fixed"}, format="json")
        self.assertFalse(Notification.objects.filter(notification_type="announcement.updated").exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(self.url(announcement), {"location": "Hall B"}, format="json")
            self.client.patch(self.url(announcement), {"start_datetime": future(6).isoformat()}, format="json")
        note = Notification.objects.get(notification_type="announcement.updated")  # grouped while unread
        self.assertEqual(note.recipient, self.bob)
        self.assertEqual(note.metadata["count"], 2)
        self.assertIn("start time", note.message)

    def test_reminders_are_idempotent(self):
        soon = self.make(start=timezone.now() + timedelta(hours=5))
        later = self.make(start=future(10))
        AnnouncementBookmark.objects.create(user=self.bob, announcement=soon)
        AnnouncementBookmark.objects.create(user=self.bob, announcement=later)
        with self.captureOnCommitCallbacks(execute=True):
            services.send_due_reminders()
            services.send_due_reminders()
        reminders = Notification.objects.filter(notification_type="announcement.reminder")
        self.assertEqual(reminders.count(), 1)
        self.assertEqual(reminders[0].target_id, str(soon.pk))

    def test_reminder_command_runs(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        with mock.patch("announcements.services.send_due_reminders", return_value=3) as run:
            call_command("send_announcement_reminders", stdout=out)
        run.assert_called_once()
        self.assertIn("3 reminder", out.getvalue())
