import io
import shutil
import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import Role, User
from announcements.models import Announcement, Category

TMP_MEDIA = tempfile.mkdtemp()


def make_user(username, role=Role.USER):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="Str0ng!Passw0rd",
        full_name=username.title(), phone_number="+9779800000000", country="Nepal",
        role=role, is_active=True, is_email_verified=True,
    )


def future(days=10):
    return (date.today() + timedelta(days=days)).isoformat()


def payload(category, **over):
    data = {
        "title": "Kathmandu Football Cup",
        "short_description": "Inter-school tournament",
        "full_description": "Eight teams compete over two weekends.",
        "activity_name": "Football",
        "category": category.id,
        "activity_type": "physical",
        "country": "Nepal", "province": "Bagmati", "city": "Kathmandu", "venue": "Dasarath Stadium",
        "start_date": future(10), "end_date": future(12),
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": (timezone.now() + timedelta(days=5)).isoformat(),
        "registration_link": "https://example.com/register",
        "status": "published",
    }
    data.update(over)
    return data


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class AnnouncementBase(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = make_user("normal")
        self.coord = make_user("coord", Role.COORDINATOR)
        self.coord2 = make_user("coord2", Role.COORDINATOR)
        self.admin = make_user("boss", Role.ADMIN)
        self.sports = Category.objects.create(name="Sports")
        self.tech = Category.objects.create(name="Technology")
        self.url = reverse("announcement-list")

    def create(self, user, category=None, **over):
        self.client.force_authenticate(user)
        r = self.client.post(self.url, payload(category or self.sports, **over), format="json")
        self.client.force_authenticate(None)
        return r

    def seed(self):
        self.create(self.coord, title="Football Cup", activity_name="Football", keywords="futsal, soccer")
        self.create(self.coord, self.tech, title="Coding Competition", activity_name="Hackathon",
                    activity_type="online", city="", venue="", country="India", province="")
        self.create(self.coord, title="Pokhara Football Day", city="Pokhara", province="Gandaki")
        self.create(self.coord, title="Cricket Fest", activity_name="Cricket")


class CreateAndPermissionTests(AnnouncementBase):
    def test_coordinator_can_create(self):
        r = self.create(self.coord)
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual(body["organizer"]["username"], "coord")
        self.assertEqual(body["status"], "published")
        self.assertIsNotNone(body["published_at"])

    def test_normal_user_and_anonymous_cannot_create(self):
        self.assertEqual(self.create(self.user).status_code, 403)
        r = self.client.post(self.url, payload(self.sports), format="json")
        self.assertEqual(r.status_code, 401)

    def test_admin_can_create_edit_delete_any(self):
        pk = self.create(self.coord).json()["id"]
        self.client.force_authenticate(self.admin)
        detail = reverse("announcement-detail", args=[pk])
        self.assertEqual(self.client.patch(detail, {"title": "Edited by admin"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(detail).status_code, 204)

    def test_coordinator_cannot_edit_or_delete_others(self):
        pk = self.create(self.coord).json()["id"]
        self.client.force_authenticate(self.coord2)
        detail = reverse("announcement-detail", args=[pk])
        self.assertEqual(self.client.patch(detail, {"title": "Hijack"}, format="json").status_code, 403)
        self.assertEqual(self.client.put(detail, payload(self.sports), format="json").status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        self.assertEqual(Announcement.objects.get(pk=pk).title, "Kathmandu Football Cup")

    def test_owner_can_edit_and_normal_user_cannot(self):
        pk = self.create(self.coord).json()["id"]
        detail = reverse("announcement-detail", args=[pk])
        self.client.force_authenticate(self.coord)
        self.assertEqual(self.client.patch(detail, {"title": "New title"}, format="json").status_code, 200)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.patch(detail, {"title": "x"}, format="json").status_code, 403)

    def test_drafts_hidden_from_public_and_other_coordinators(self):
        pk = self.create(self.coord, status="draft").json()["id"]
        detail = reverse("announcement-detail", args=[pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(self.url).json()["count"], 0)
        self.client.force_authenticate(self.coord2)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_authenticate(self.coord)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(self.url, {"status": "draft"}).json()["count"], 1)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(self.url, {"status": "draft"}).json()["count"], 0)


class ValidationTests(AnnouncementBase):
    def test_invalid_registration_links(self):
        for bad in ("javascript:alert(1)", "not a url", "ftp://example.com/x"):
            r = self.create(self.coord, registration_link=bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("registration_link", r.json())
        r = self.create(self.coord, external_link="htp://broken")
        self.assertIn("external_link", r.json())

    def test_date_rules(self):
        r = self.create(self.coord, start_date=future(10), end_date=future(5))
        self.assertIn("end_date", r.json())
        r = self.create(self.coord, start_date=(date.today() - timedelta(days=2)).isoformat(), end_date=future(3))
        self.assertIn("start_date", r.json())
        r = self.create(self.coord, registration_deadline=(timezone.now() + timedelta(days=60)).isoformat())
        self.assertIn("registration_deadline", r.json())
        r = self.create(self.coord, start_date=future(10), end_date=future(10), start_time="10:00", end_time="09:00")
        self.assertIn("end_time", r.json())

    def test_physical_requires_venue_and_free_has_no_fee(self):
        self.assertIn("venue", self.create(self.coord, venue="").json())
        self.assertIn("fee_amount", self.create(self.coord, is_free=True, fee_amount="50.00").json())

    def test_banner_validation(self):
        self.client.force_authenticate(self.coord)
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buf, "PNG")
        good = SimpleUploadedFile("b.png", buf.getvalue(), content_type="image/png")
        data = {k: str(v) for k, v in payload(self.sports).items()}
        r = self.client.post(self.url, {**data, "banner": good}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("/media/announcements/banners/", r.json()["banner"])
        fake = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png")
        r = self.client.post(self.url, {**data, "banner": fake}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("banner", r.json())


class ListSearchFilterTests(AnnouncementBase):
    def titles(self, **params):
        r = self.client.get(self.url, params)
        self.assertEqual(r.status_code, 200, r.content)
        return sorted(i["title"] for i in r.json()["results"])

    def test_list_only_published_newest_first(self):
        self.seed()
        self.create(self.coord, title="Hidden draft", status="draft")
        self.create(self.coord, title="Old archived", status="archived")
        r = self.client.get(self.url).json()
        self.assertEqual(r["count"], 4)
        self.assertEqual(r["results"][0]["title"], "Cricket Fest")  # most recently published
        item = r["results"][0]
        for key in ("title", "category", "short_description", "banner", "location", "schedule",
                    "activity_type", "registration_link", "organizer", "published_at"):
            self.assertIn(key, item)

    def test_search_football(self):
        self.seed()
        self.assertEqual(self.titles(search="football"), ["Football Cup", "Pokhara Football Day"])
        self.assertEqual(self.titles(search="futsal"), ["Football Cup"])  # keywords field

    def test_search_coding(self):
        self.seed()
        self.assertEqual(self.titles(search="coding"), ["Coding Competition"])

    def test_search_by_category_and_location(self):
        self.seed()
        self.assertEqual(self.titles(search="technology"), ["Coding Competition"])
        self.assertEqual(self.titles(search="pokhara"), ["Pokhara Football Day"])

    def test_filter_country_city_type(self):
        self.seed()
        self.assertEqual(self.titles(country="nepal", city="Kathmandu"), ["Cricket Fest", "Football Cup"])
        self.assertEqual(self.titles(country="India"), ["Coding Competition"])
        self.assertEqual(self.titles(type="Online"), ["Coding Competition"])
        self.assertEqual(len(self.titles(type="Physical")), 3)
        self.assertEqual(self.titles(type="bogus"), [])

    def test_combined_search_and_filters(self):
        self.seed()
        self.assertEqual(
            self.titles(search="Football", country="Nepal", city="Kathmandu", type="Physical"),
            ["Football Cup"],
        )
        self.assertEqual(self.titles(search="Football", city="Pokhara"), ["Pokhara Football Day"])
        self.assertEqual(self.titles(search="Football", type="Online"), [])

    def test_filter_category_dates_and_free(self):
        self.seed()
        self.create(self.coord, title="Paid Workshop", is_free=False, fee_amount="500.00",
                    start_date=future(40), end_date=future(41), registration_deadline=None)
        self.assertEqual(self.titles(category=self.tech.id), ["Coding Competition"])
        self.assertEqual(self.titles(is_free="false"), ["Paid Workshop"])
        self.assertEqual(self.titles(start_date_from=future(30)), ["Paid Workshop"])
        self.assertEqual(self.titles(start_date=future(40)), ["Paid Workshop"])

    def test_pagination(self):
        for i in range(15):
            self.create(self.coord, title=f"Event {i}")
        r = self.client.get(self.url).json()
        self.assertEqual(r["count"], 15)
        self.assertEqual(len(r["results"]), 12)
        self.assertIsNotNone(r["next"])
        r2 = self.client.get(self.url, {"page": 2}).json()
        self.assertEqual(len(r2["results"]), 3)
        self.assertEqual(len(self.client.get(self.url, {"page_size": 5}).json()["results"]), 5)


class DetailAndCategoryTests(AnnouncementBase):
    def test_detail_fields(self):
        pk = self.create(self.coord, contact_email="info@example.com", contact_phone="+9779811111111",
                         external_link="https://example.org").json()["id"]
        r = self.client.get(reverse("announcement-detail", args=[pk]))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["full_description"], "Eight teams compete over two weekends.")
        self.assertEqual(d["contact"], {"email": "info@example.com", "phone": "+9779811111111"})
        self.assertEqual(d["registration_link"], "https://example.com/register")
        self.assertTrue(d["registration_open"])
        self.assertEqual(d["organizer"]["full_name"], "Coord")
        self.assertNotIn("email", d["organizer"])

    def test_category_permissions(self):
        url = reverse("category-list")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(self.coord)
        self.assertEqual(self.client.post(url, {"name": "Dance"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        r = self.client.post(url, {"name": "Dance"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["slug"], "dance")
        self.assertEqual(self.client.post(url, {"name": "dance"}, format="json").status_code, 400)
        detail = reverse("category-detail", args=[r.json()["id"]])
        self.assertEqual(self.client.patch(detail, {"description": "x"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(detail).status_code, 204)

    def test_cannot_delete_category_in_use(self):
        self.create(self.coord)
        self.client.force_authenticate(self.admin)
        r = self.client.delete(reverse("category-detail", args=[self.sports.id]))
        self.assertEqual(r.status_code, 409)
