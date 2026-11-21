import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from accounts.services import tokens_for_user
from announcements import ranking
from announcements.models import Announcement, AnnouncementStatus, Bookmark, Category

TMP_MEDIA = tempfile.mkdtemp(prefix="ann_test_media_")
TMP_PRIVATE = tempfile.mkdtemp(prefix="ann_test_private_")


def mk_user(name, role=Role.USER):
    return User.objects.create_user(
        username=name, email=f"{name}@example.com", password="Str0ng!Passw0rd", full_name=name.title(),
        phone_number="+9779800000000", country="Nepal", role=role)


def png_file(name="pic.png", size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def pdf_file(name="rules.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n%fake but valid header\n", content_type="application/pdf")


@override_settings(MEDIA_ROOT=TMP_MEDIA, ANNOUNCEMENT_PRIVATE_ROOT=TMP_PRIVATE,
                   ROOT_URLCONF="announcements.tests.urls")
class Base(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        call_command("seed_announcement_categories", stdout=io.StringIO())
        self.sports = Category.objects.get(name="Sports")
        self.arts = Category.objects.get(name="Cultural Activities")
        self.general = Category.objects.get(name="General Notice")
        self.a, self.b, self.c = mk_user("alice"), mk_user("bob"), mk_user("carol")
        self.coord = mk_user("coach", role=Role.COORDINATOR)

    # helpers ---------------------------------------------------------------------------
    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make(self, author, **over):
        data = dict(title="Football Cup", short_description="short", full_description="Full text here",
                    category=self.sports, published_by=author, status=AnnouncementStatus.PUBLISHED,
                    published_at=timezone.now())
        data.update(over)
        return Announcement.objects.create(**data)

    def payload(self, **over):
        data = {"title": "Inter-college football cup", "full_description": "Register your team now.",
                "category": self.sports.id, "status": "published", "location": "Main ground"}
        data.update(over)
        return data

    def ids(self, resp):
        return [r["id"] for r in resp.data["results"]]


# ================================================================ CRUD, ownership, visibility
class OwnershipTests(Base):
    def test_01_student_a_creates_announcement(self):
        r = self.as_user(self.a).post(reverse("announcement-list"), self.payload(
            activity_name="Football Cup 2026", start_date=(timezone.localdate() + timedelta(days=10)).isoformat(),
            deadline=(timezone.localdate() + timedelta(days=5)).isoformat()), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        obj = Announcement.objects.get(pk=r.data["id"])
        self.assertEqual(obj.published_by, self.a)
        self.assertEqual(r.data["author"]["username"], "alice")
        self.assertNotIn("email", r.data["author"])
        self.assertTrue(r.data["is_owner"])
        self.assertTrue(obj.short_description)           # derived from the full description
        self.assertIsNotNone(obj.published_at)

    def test_02_and_03_other_students_see_list_and_full_details(self):
        ann = self.make(self.a)
        for user in (self.b, self.c):
            client = self.as_user(user)
            self.assertIn(ann.id, self.ids(client.get(reverse("announcement-list"))))
            d = client.get(reverse("announcement-detail", args=[ann.id]))
            self.assertEqual(d.status_code, 200)
            self.assertEqual(d.data["full_description"], "Full text here")
            self.assertFalse(d.data["can_edit"])
            self.assertEqual(d.data["author"]["id"], self.a.id)

    def test_04_other_student_cannot_edit(self):
        ann = self.make(self.a)
        url = reverse("announcement-detail", args=[ann.id])
        for method in ("put", "patch"):
            r = getattr(self.as_user(self.b), method)(url, self.payload(title="Hacked title"), format="json")
            self.assertEqual(r.status_code, 403)
        ann.refresh_from_db()
        self.assertEqual(ann.title, "Football Cup")

    def test_05_other_student_cannot_delete(self):
        ann = self.make(self.a)
        r = self.as_user(self.b).delete(reverse("announcement-detail", args=[ann.id]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Announcement.objects.filter(pk=ann.id).exists())

    def test_06_owner_can_edit(self):
        ann = self.make(self.a)
        url = reverse("announcement-detail", args=[ann.id])
        r = self.as_user(self.a).patch(url, {"title": "Updated title", "location": "Hall 2"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["title"], "Updated title")
        r = self.as_user(self.a).put(url, self.payload(title="Full replace"), format="json")
        self.assertEqual(r.status_code, 200, r.data)
        ann.refresh_from_db()
        self.assertEqual(ann.title, "Full replace")
        self.assertEqual(ann.published_by, self.a)

    def test_07_owner_can_delete(self):
        ann = self.make(self.a)
        r = self.as_user(self.a).delete(reverse("announcement-detail", args=[ann.id]))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Announcement.objects.filter(pk=ann.id).exists())
        self.assertEqual(self.as_user(self.b).get(reverse("announcement-detail", args=[ann.id])).status_code, 404)

    def test_22_cannot_impersonate_author(self):
        client = self.as_user(self.a)
        r = client.post(reverse("announcement-list"),
                        self.payload(published_by=self.b.id, author=self.b.id, user=self.b.id), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Announcement.objects.get(pk=r.data["id"]).published_by, self.a)
        r = client.patch(reverse("announcement-detail", args=[r.data["id"]]),
                         {"published_by": self.b.id, "author": self.b.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Announcement.objects.get(pk=r.data["id"]).published_by, self.a)

    def test_bookmarking_does_not_grant_edit_rights(self):
        ann = self.make(self.a)
        client = self.as_user(self.b)
        self.assertEqual(client.post(reverse("announcement-bookmark", args=[ann.id])).status_code, 201)
        self.assertEqual(client.patch(reverse("announcement-detail", args=[ann.id]), {"title": "x y z"}, format="json").status_code, 403)
        self.assertEqual(client.delete(reverse("announcement-detail", args=[ann.id])).status_code, 403)


class AuthTests(Base):
    def test_09_unauthenticated_cannot_do_anything(self):
        ann = self.make(self.a)
        anon = APIClient()
        checks = [
            anon.get(reverse("announcement-list")), anon.post(reverse("announcement-list"), self.payload(), format="json"),
            anon.get(reverse("announcement-detail", args=[ann.id])), anon.patch(reverse("announcement-detail", args=[ann.id]), {}, format="json"),
            anon.delete(reverse("announcement-detail", args=[ann.id])), anon.post(reverse("announcement-bookmark", args=[ann.id])),
            anon.get(reverse("announcement-bookmarks")), anon.get(reverse("announcement-search") + "?q=a"),
            anon.get(reverse("announcement-recommended")), anon.get(reverse("announcement-landing")),
            anon.get(reverse("announcement-categories")), anon.get(reverse("announcement-attachment", args=[ann.id])),
        ]
        for r in checks:
            self.assertEqual(r.status_code, 401, r.request["PATH_INFO"])

    def test_real_jwt_from_existing_auth_system_works(self):
        access = tokens_for_user(self.a)["access"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        r = client.post(reverse("announcement-list"), self.payload(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Announcement.objects.get(pk=r.data["id"]).published_by, self.a)


class VisibilityTests(Base):
    def test_08_drafts_are_private(self):
        draft = self.make(self.a, status=AnnouncementStatus.DRAFT, published_at=None, title="Secret draft")
        b = self.as_user(self.b)
        self.assertEqual(b.get(reverse("announcement-detail", args=[draft.id])).status_code, 404)
        self.assertEqual(b.patch(reverse("announcement-detail", args=[draft.id]), {"title": "nope nope"}, format="json").status_code, 404)
        self.assertEqual(b.delete(reverse("announcement-detail", args=[draft.id])).status_code, 404)
        self.assertEqual(b.post(reverse("announcement-bookmark", args=[draft.id])).status_code, 404)
        self.assertEqual(b.get(reverse("announcement-attachment", args=[draft.id])).status_code, 404)
        self.assertNotIn(draft.id, self.ids(b.get(reverse("announcement-list"))))
        self.assertNotIn(draft.id, self.ids(b.get(reverse("announcement-by-author", args=[self.a.id]))))
        self.assertNotIn(draft.id, self.ids(b.get(reverse("announcement-search") + "?q=secret")))
        self.assertNotIn(draft.id, self.ids(b.get(reverse("announcement-recommended"))))
        self.assertEqual(b.get(reverse("announcement-share", args=[draft.id])).status_code, 404)
        # owner sees it in the right places only
        a = self.as_user(self.a)
        self.assertEqual(a.get(reverse("announcement-detail", args=[draft.id])).status_code, 200)
        self.assertIn(draft.id, self.ids(a.get(reverse("announcement-drafts"))))
        self.assertIn(draft.id, self.ids(a.get(reverse("announcement-mine"))))
        self.assertNotIn(draft.id, self.ids(a.get(reverse("announcement-list"))))
        self.assertEqual(self.ids(b.get(reverse("announcement-drafts"))), [])

    def test_scheduled_hidden_until_publication_time_and_expired_excluded(self):
        scheduled = self.make(self.a, published_at=timezone.now() + timedelta(days=2), title="Soon")
        expired = self.make(self.a, expires_at=timezone.now() - timedelta(hours=1), title="Old news")
        live = self.make(self.a, title="Live one")
        b = self.as_user(self.b)
        listed = self.ids(b.get(reverse("announcement-list")))
        self.assertEqual(listed, [live.id])
        self.assertEqual(b.get(reverse("announcement-detail", args=[scheduled.id])).status_code, 404)
        self.assertEqual(b.get(reverse("announcement-detail", args=[expired.id])).status_code, 404)
        a = self.as_user(self.a)
        self.assertEqual(a.get(reverse("announcement-detail", args=[scheduled.id])).data["state"], "scheduled")
        self.assertEqual(a.get(reverse("announcement-detail", args=[expired.id])).data["state"], "expired")
        self.assertEqual(self.ids(a.get(reverse("announcement-mine") + "?state=scheduled")), [scheduled.id])
        self.assertEqual(self.ids(a.get(reverse("announcement-mine") + "?state=expired")), [expired.id])

    def test_author_listing(self):
        mine, theirs = self.make(self.a), self.make(self.b, title="Bobs")
        r = self.as_user(self.c).get(reverse("announcement-by-author", args=[self.a.id]))
        self.assertEqual(self.ids(r), [mine.id])
        r = self.as_user(self.c).get(reverse("announcement-list") + f"?author={self.b.id}")
        self.assertEqual(self.ids(r), [theirs.id])
        self.assertEqual(self.ids(self.as_user(self.a).get(reverse("announcement-mine"))), [mine.id])

    def test_publish_flow_draft_to_published_and_back(self):
        client = self.as_user(self.a)
        r = client.post(reverse("announcement-list"), self.payload(status="draft"), format="json")
        self.assertEqual(r.data["state"], "draft")
        self.assertIsNone(r.data["published_at"])
        url = reverse("announcement-detail", args=[r.data["id"]])
        self.assertEqual(self.as_user(self.b).get(url).status_code, 404)
        r = client.patch(url, {"status": "published"}, format="json")
        self.assertEqual(r.data["state"], "published")
        self.assertEqual(self.as_user(self.b).get(url).status_code, 200)
        client.patch(url, {"status": "draft"}, format="json")
        self.assertEqual(self.as_user(self.b).get(url).status_code, 404)

    def test_scheduled_publish_via_api(self):
        when = (timezone.now() + timedelta(days=1)).isoformat()
        r = self.as_user(self.a).post(reverse("announcement-list"), self.payload(publish_at=when), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["state"], "scheduled")
        self.assertEqual(self.as_user(self.b).get(reverse("announcement-detail", args=[r.data["id"]])).status_code, 404)


# ================================================================ search / filter / sort / pagination
class SearchFilterSortTests(Base):
    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        now = timezone.now()
        self.football = self.make(self.a, title="Inter-college Football Cup", activity_name="Kathmandu Cup",
                                  location="Dhangadhi Stadium", keywords="soccer, league",
                                  start_date=today + timedelta(days=10), deadline=today + timedelta(days=3),
                                  published_at=now - timedelta(days=3))
        self.dance = self.make(self.b, title="Folk Dance Night", category=self.arts, full_description="Traditional dances",
                               location="Auditorium", start_date=today + timedelta(days=4),
                               published_at=now - timedelta(days=2))
        self.chess = self.make(self.c, title="Chess workshop", category=self.general, full_description="Learn openings and endgames",
                               deadline=today + timedelta(days=1), published_at=now - timedelta(days=1))
        self.draft = self.make(self.a, title="Football draft only", status=AnnouncementStatus.DRAFT, published_at=None)

    def search(self, q, user=None, extra=""):
        return self.as_user(user or self.c).get(reverse("announcement-search") + f"?q={q}{extra}")

    def test_10_search_across_students(self):
        self.assertEqual(self.ids(self.search("football")), [self.football.id])            # title
        self.assertEqual(self.ids(self.search("FOOT")), [self.football.id])                 # partial + case-insensitive
        self.assertEqual(self.ids(self.search("traditional")), [self.dance.id])             # description
        self.assertEqual(self.ids(self.search("sports")), [self.football.id])               # category name
        self.assertEqual(self.ids(self.search("stadium")), [self.football.id])              # location
        self.assertEqual(self.ids(self.search("soccer")), [self.football.id])               # keywords
        self.assertEqual(self.ids(self.search("kathmandu")), [self.football.id])            # event name
        self.assertEqual(self.ids(self.search("college%20cup")), [self.football.id])        # multiple words (AND)
        self.assertEqual(self.ids(self.search("football%20chess")), [])                     # all words must match
        self.assertEqual(self.ids(self.search("draft")), [])                                # drafts never match
        self.assertEqual(self.search("zzzz").data["count"], 0)

    def test_search_requires_query_and_is_injection_safe(self):
        self.assertEqual(self.as_user(self.a).get(reverse("announcement-search")).status_code, 400)
        r = self.search("%27%3B%20DROP%20TABLE%20announcements_announcement%3B--")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(Announcement.objects.count(), 4)

    def test_search_relevance_prefers_title_matches(self):
        weak = self.make(self.b, title="Gathering", full_description="football mentioned only in the body",
                         published_at=timezone.now())
        r = self.search("football")
        self.assertEqual(self.ids(r), [self.football.id, weak.id])

    def test_11_category_filters(self):
        c = self.as_user(self.a)
        self.assertEqual(self.ids(c.get(reverse("announcement-list") + f"?category={self.arts.id}")), [self.dance.id])
        self.assertEqual(self.ids(c.get(reverse("announcement-list") + f"?category={self.sports.slug}")), [self.football.id])
        self.assertEqual(self.ids(self.search("a", extra=f"&category={self.general.id}")), [self.chess.id])  # combined with search
        self.assertEqual(c.get(reverse("announcement-list") + "?category=999999").data["count"], 0)

    def test_12_sorting(self):
        c = self.as_user(self.a)
        url = reverse("announcement-list")
        self.assertEqual(self.ids(c.get(url + "?sort=latest")), [self.chess.id, self.dance.id, self.football.id])
        self.assertEqual(self.ids(c.get(url + "?sort=oldest")), [self.football.id, self.dance.id, self.chess.id])
        self.assertEqual(self.ids(c.get(url)), [self.chess.id, self.dance.id, self.football.id])   # default = latest
        self.assertEqual(self.ids(c.get(url + "?sort=event_date")), [self.dance.id, self.football.id, self.chess.id])
        self.assertEqual(self.ids(c.get(url + "?sort=deadline")), [self.chess.id, self.football.id, self.dance.id])
        Bookmark.objects.create(user=self.b, announcement=self.football)
        Bookmark.objects.create(user=self.c, announcement=self.football)
        Bookmark.objects.create(user=self.c, announcement=self.dance)
        r = c.get(url + "?sort=bookmarks")
        self.assertEqual(self.ids(r), [self.football.id, self.dance.id, self.chess.id])
        self.assertEqual([x["bookmark_count"] for x in r.data["results"]], [2, 1, 0])
        self.assertEqual(self.ids(c.get(url + "?sort=latest&category=%s" % self.sports.id)), [self.football.id])  # sort + filter

    def test_filters_dates_featured_and_events(self):
        today = timezone.localdate()
        past = self.make(self.a, title="Past gala", start_date=today - timedelta(days=5), end_date=today - timedelta(days=4),
                         published_at=timezone.now() - timedelta(days=9))
        featured = self.make(self.coord, title="Featured thing", is_featured=True)
        c = self.as_user(self.c)
        url = reverse("announcement-list")
        self.assertEqual(self.ids(c.get(url + "?event=past")), [past.id])
        self.assertEqual(set(self.ids(c.get(url + "?event=upcoming"))), {self.football.id, self.dance.id})
        self.assertEqual(set(self.ids(c.get(url + "?deadline=upcoming"))), {self.football.id, self.chess.id})
        self.assertEqual(self.ids(c.get(url + "?featured=true")), [featured.id])
        self.assertNotIn(featured.id, self.ids(c.get(url + "?featured=false")))
        frm = (today + timedelta(days=8)).isoformat()
        to = (today + timedelta(days=12)).isoformat()
        self.assertEqual(self.ids(c.get(url + f"?event_from={frm}&event_to={to}")), [self.football.id])
        d = (timezone.localdate() - timedelta(days=2)).isoformat()
        r = c.get(url + f"?published_from={d}&published_to={timezone.localdate().isoformat()}")
        self.assertIn(self.dance.id, self.ids(r))
        self.assertNotIn(self.football.id, self.ids(r))

    def test_21_invalid_query_params_rejected(self):
        c = self.as_user(self.a)
        url = reverse("announcement-list")
        for bad in ("?sort=bogus", "?event=sometime", "?published_from=notadate", "?author=abc",
                    "?featured=maybe", "?event_from=2030-02-01&event_to=2030-01-01", "?activity_type=xyz"):
            self.assertEqual(c.get(url + bad).status_code, 400, bad)

    def test_20_pagination(self):
        for i in range(15):
            self.make(self.a, title=f"Bulk {i:02d}", published_at=timezone.now() + timedelta(seconds=-100 + i))
        c = self.as_user(self.b)
        url = reverse("announcement-list")
        r = c.get(url)
        self.assertEqual((r.data["count"], len(r.data["results"])), (18, 12))
        self.assertIsNotNone(r.data["next"])
        r = c.get(url + "?page_size=5&page=3")
        self.assertEqual(len(r.data["results"]), 5)
        seen = []
        for page in range(1, 5):
            seen += self.ids(c.get(url + f"?page_size=5&page={page}"))
        self.assertEqual(len(seen), len(set(seen)), "no duplicates across pages")
        self.assertEqual(len(seen), 18)
        self.assertEqual(c.get(url + "?page_size=5&page=9").status_code, 404)
        self.assertLessEqual(len(c.get(url + "?page_size=500").data["results"]), 50)

    def test_14_15_upcoming_events_exclude_expired(self):
        today = timezone.localdate()
        past = self.make(self.a, title="Over already", start_date=today - timedelta(days=3), end_date=today - timedelta(days=1))
        ongoing = self.make(self.a, title="Ongoing fest", start_date=today - timedelta(days=1), end_date=today + timedelta(days=2))
        r = self.as_user(self.b).get(reverse("announcement-upcoming"))
        self.assertEqual(self.ids(r), [ongoing.id, self.dance.id, self.football.id])   # soonest first, ongoing counts
        self.assertNotIn(past.id, self.ids(r))
        self.assertNotIn(self.chess.id, self.ids(r))                                    # no event date
        self.assertNotIn(self.draft.id, self.ids(r))

    def test_16_upcoming_deadlines_exclude_passed(self):
        today = timezone.localdate()
        passed = self.make(self.a, title="Closed", deadline=today - timedelta(days=1))
        r = self.as_user(self.b).get(reverse("announcement-deadlines"))
        self.assertEqual(self.ids(r), [self.chess.id, self.football.id])                # nearest first
        self.assertNotIn(passed.id, self.ids(r))

    def test_featured_important_latest_endpoints_and_categories(self):
        f = self.make(self.coord, title="Pinned", is_featured=True)
        imp = self.make(self.coord, title="Notice", is_important=True)
        c = self.as_user(self.a)
        self.assertEqual(self.ids(c.get(reverse("announcement-featured"))), [f.id])
        self.assertEqual(self.ids(c.get(reverse("announcement-important"))), [imp.id])
        self.assertEqual(self.ids(c.get(reverse("announcement-latest")))[:2], [imp.id, f.id])
        cats = c.get(reverse("announcement-categories"))
        self.assertEqual(cats.status_code, 200)
        self.assertEqual(len(cats.data), 12)


# ================================================================ ranking
class RankingTests(Base):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.t = self.now - timedelta(days=2)       # shared timestamp so only the boost decides
        self.today = timezone.localdate()

    def rec(self, user=None, **extra):
        return self.as_user(user or self.c).get(reverse("announcement-recommended") + extra.get("qs", ""))

    def order(self, resp):
        return [r["title"] for r in resp.data["results"]]

    def test_13_components_unit(self):
        n, t = self.now, self.today
        self.assertAlmostEqual(ranking.recency_score(n, n), 1.0)
        self.assertAlmostEqual(ranking.recency_score(n - timedelta(days=7), n), 0.5, places=4)
        self.assertGreater(ranking.recency_score(n - timedelta(hours=1), n), ranking.recency_score(n - timedelta(days=5), n))
        self.assertEqual(ranking.event_score(None, None, t), 0.0)
        self.assertEqual(ranking.event_score(t - timedelta(days=3), t - timedelta(days=1), t), 0.0)   # over
        self.assertEqual(ranking.event_score(t - timedelta(days=1), t + timedelta(days=1), t), 1.0)   # ongoing
        self.assertGreater(ranking.event_score(t + timedelta(days=1), None, t), ranking.event_score(t + timedelta(days=20), None, t))
        self.assertEqual(ranking.event_score(t + timedelta(days=60), None, t), 0.0)
        self.assertEqual(ranking.deadline_score(None, t), 0.0)
        self.assertEqual(ranking.deadline_score(t - timedelta(days=1), t), 0.0)
        self.assertEqual(ranking.deadline_score(t, t), 1.0)
        self.assertEqual(ranking.engagement_score(0, 5), 0.0)
        self.assertEqual(ranking.engagement_score(5, 5), 1.0)
        self.assertEqual(ranking.engagement_score(3, 0), 0.0)
        self.assertAlmostEqual(sum(ranking.WEIGHTS.values()), 1.0)
        for v in (ranking.recency_score(n - timedelta(days=900), n), ranking.event_score(t, t, t)):
            self.assertTrue(0.0 <= v <= 1.0)

    def test_13_recent_beats_old_and_new_with_no_engagement_is_not_hidden(self):
        old = self.make(self.a, title="Old", published_at=self.now - timedelta(days=60))
        popular_old = self.make(self.a, title="Popular old", published_at=self.now - timedelta(days=40))
        for u in (self.a, self.b, self.coord):
            Bookmark.objects.create(user=u, announcement=popular_old)
        fresh = self.make(self.b, title="Fresh", published_at=self.now - timedelta(hours=1))
        r = self.rec()
        self.assertEqual(self.order(r)[0], "Fresh")
        self.assertIn("score", r.data["results"][0])
        self.assertLess(self.order(r).index("Popular old"), self.order(r).index("Old"))

    def test_13_event_deadline_featured_engagement_boost_beat_tiebreak(self):
        # boosted items are created FIRST (lower id): the id tie-break would rank them last,
        # so seeing them first proves the score decided.
        ev = self.make(self.a, title="Event soon", published_at=self.t, start_date=self.today + timedelta(days=1))
        dl = self.make(self.a, title="Deadline soon", published_at=self.t, deadline=self.today + timedelta(days=1))
        ft = self.make(self.coord, title="Featured", published_at=self.t, is_featured=True)
        eng = self.make(self.a, title="Engaged", published_at=self.t)
        Bookmark.objects.create(user=self.a, announcement=eng)
        Bookmark.objects.create(user=self.b, announcement=eng)
        plain = self.make(self.a, title="Plain", published_at=self.t)
        past = self.make(self.a, title="Past event", published_at=self.t, start_date=self.today - timedelta(days=4),
                         end_date=self.today - timedelta(days=3))
        far = self.make(self.a, title="Far event", published_at=self.t, start_date=self.today + timedelta(days=25))
        order = self.order(self.rec())
        self.assertEqual(order[0], "Event soon")
        for boosted in ("Event soon", "Deadline soon", "Featured", "Engaged", "Far event"):
            self.assertLess(order.index(boosted), order.index("Plain"), boosted)
        self.assertLess(order.index("Event soon"), order.index("Far event"))     # closer event wins
        scores = {r["title"]: r["score"] for r in self.rec().data["results"]}
        self.assertEqual(scores["Plain"], scores["Past event"])
        # deterministic: same request twice gives the same order
        self.assertEqual(self.order(self.rec()), self.order(self.rec()))

    def test_13_neutral_category_without_history_and_personal_interest_with_history(self):
        s1 = self.make(self.a, title="Sports one", published_at=self.t)
        s2 = self.make(self.a, title="Sports two", published_at=self.t - timedelta(days=30))
        art = self.make(self.a, title="Arts newer id", category=self.arts, published_at=self.t)
        # Carol has no bookmarks -> neutral: tie-break by id (art is newest id)
        self.assertEqual(self.order(self.rec(self.c))[:2], ["Arts newer id", "Sports one"])
        # Bob bookmarks sports -> sports preferred for Bob only
        Bookmark.objects.create(user=self.b, announcement=s2)
        self.assertEqual(self.order(self.rec(self.b))[0], "Sports one")
        self.assertEqual(self.order(self.rec(self.c))[0], "Arts newer id")    # Carol unaffected by Bob's data

    def test_recommended_excludes_drafts_expired_and_scheduled(self):
        ok = self.make(self.a, title="ok")
        self.make(self.a, title="d", status=AnnouncementStatus.DRAFT, published_at=None)
        self.make(self.a, title="e", expires_at=self.now - timedelta(minutes=1))
        self.make(self.a, title="s", published_at=self.now + timedelta(days=1))
        self.assertEqual(self.order(self.rec()), ["ok"])

    def test_landing_page_sections(self):
        f = self.make(self.coord, title="Feat", is_featured=True, start_date=self.today + timedelta(days=2),
                      deadline=self.today + timedelta(days=1), is_important=True)
        r = self.as_user(self.b).get(reverse("announcement-landing") + "?limit=3")
        self.assertEqual(r.status_code, 200)
        for key in ("featured", "latest", "recommended", "upcoming_events", "upcoming_deadlines", "important"):
            self.assertEqual([x["id"] for x in r.data[key]], [f.id], key)
        item = r.data["featured"][0]
        for key in ("id", "title", "short_description", "category", "author", "image_url", "published_at",
                    "event_date", "deadline"):
            self.assertIn(key, item)
        self.assertEqual(self.as_user(self.b).get(reverse("announcement-landing") + "?limit=99").status_code, 400)


# ================================================================ bookmarks / share
class BookmarkTests(Base):
    def test_17_bookmark_lifecycle(self):
        ann = self.make(self.a)
        b = self.as_user(self.b)
        url = reverse("announcement-bookmark", args=[ann.id])
        self.assertEqual(b.get(url).data, {"bookmarked": False})
        r = b.post(url)
        self.assertEqual((r.status_code, r.data["bookmarked"], r.data["bookmark_count"]), (201, True, 1))
        self.assertEqual(b.get(url).data, {"bookmarked": True})
        self.assertEqual(self.ids(b.get(reverse("announcement-bookmarks"))), [ann.id])
        self.assertTrue(b.get(reverse("announcement-detail", args=[ann.id])).data["is_bookmarked"])
        self.assertEqual(b.delete(url).status_code, 204)
        self.assertEqual(b.delete(url).status_code, 204)          # idempotent
        self.assertEqual(self.ids(b.get(reverse("announcement-bookmarks"))), [])
        self.assertEqual(b.delete(reverse("announcement-bookmark", args=[999999])).status_code, 404)
        own = self.as_user(self.a).post(url)                       # bookmarking your own is allowed
        self.assertEqual(own.status_code, 201)

    def test_18_duplicate_bookmarks_prevented(self):
        ann = self.make(self.a)
        b = self.as_user(self.b)
        url = reverse("announcement-bookmark", args=[ann.id])
        self.assertEqual(b.post(url).status_code, 201)
        self.assertEqual(b.post(url).status_code, 200)
        self.assertEqual(Bookmark.objects.filter(user=self.b, announcement=ann).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Bookmark.objects.create(user=self.b, announcement=ann)       # database-level constraint

    def test_19_cannot_see_other_students_bookmarks(self):
        ann, other = self.make(self.a), self.make(self.a, title="Second")
        self.as_user(self.b).post(reverse("announcement-bookmark", args=[ann.id]))
        self.as_user(self.c).post(reverse("announcement-bookmark", args=[other.id]))
        self.assertEqual(self.ids(self.as_user(self.b).get(reverse("announcement-bookmarks"))), [ann.id])
        self.assertEqual(self.ids(self.as_user(self.c).get(reverse("announcement-bookmarks"))), [other.id])
        self.assertEqual(self.ids(self.as_user(self.a).get(reverse("announcement-bookmarks"))), [])

    def test_bookmarks_listed_most_recent_first_and_hide_unpublished(self):
        x, y = self.make(self.a, title="X"), self.make(self.a, title="Y")
        b = self.as_user(self.b)
        b.post(reverse("announcement-bookmark", args=[x.id]))
        b.post(reverse("announcement-bookmark", args=[y.id]))
        self.assertEqual(self.ids(b.get(reverse("announcement-bookmarks"))), [y.id, x.id])
        Announcement.objects.filter(pk=y.pk).update(status=AnnouncementStatus.DRAFT)
        self.assertEqual(self.ids(b.get(reverse("announcement-bookmarks"))), [x.id])

    def test_share(self):
        ann = self.make(self.a)
        r = self.as_user(self.b).get(reverse("announcement-share", args=[ann.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], ann.id)
        self.assertIn(f"/announcements/{ann.id}/", r.data["detail_url"])
        shared = self.as_user(self.c).get(reverse("announcement-shared", args=[ann.share_id]))
        self.assertEqual((shared.status_code, shared.data["id"]), (200, ann.id))
        self.assertEqual(APIClient().get(reverse("announcement-shared", args=[ann.share_id])).status_code, 401)
        draft = self.make(self.a, status=AnnouncementStatus.DRAFT, published_at=None)
        self.assertEqual(self.as_user(self.b).get(reverse("announcement-shared", args=[draft.share_id])).status_code, 404)
        self.assertEqual(self.as_user(self.a).get(reverse("announcement-share", args=[draft.id])).status_code, 400)


# ================================================================ validation / files / curation
class ValidationTests(Base):
    def post(self, user=None, **over):
        fmt = over.pop("_format", "json")
        return self.as_user(user or self.a).post(reverse("announcement-list"), self.payload(**over), format=fmt)

    def test_21_invalid_data_rejected(self):
        today = timezone.localdate()
        cases = {
            "missing title": {"title": ""},
            "short title": {"title": "ab"},
            "missing description": {"full_description": ""},
            "unknown category": {"category": 99999},
            "bad status": {"status": "archived"},
            "bad activity type": {"activity_type": "teleport"},
            "end before start": {"start_date": (today + timedelta(days=5)).isoformat(), "end_date": (today + timedelta(days=2)).isoformat()},
            "end without start": {"end_date": (today + timedelta(days=2)).isoformat()},
            "event in the past": {"start_date": (today - timedelta(days=1)).isoformat()},
            "deadline in the past": {"deadline": (today - timedelta(days=1)).isoformat()},
            "bad date format": {"start_date": "31/12/2030"},
            "publish_at needs published": {"status": "draft", "publish_at": (timezone.now() + timedelta(days=1)).isoformat()},
            "publish_at past": {"publish_at": (timezone.now() - timedelta(days=1)).isoformat()},
            "expires in past": {"expires_at": (timezone.now() - timedelta(days=1)).isoformat()},
        }
        for label, over in cases.items():
            r = self.post(**over)
            self.assertEqual(r.status_code, 400, f"{label}: {r.data}")
        self.assertEqual(Announcement.objects.count(), 0)

    def test_inactive_category_rejected(self):
        Category.objects.filter(pk=self.arts.pk).update(is_active=False)
        self.assertEqual(self.post(category=self.arts.id).status_code, 400)
        self.assertEqual(len(self.as_user(self.a).get(reverse("announcement-categories")).data), 11)

    def test_category_names_unique_case_insensitively(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="sports")
        call_command("seed_announcement_categories", stdout=io.StringIO())
        self.assertEqual(Category.objects.count(), 12)

    def test_featured_and_important_only_for_coordinators(self):
        r = self.post(is_featured=True)
        self.assertEqual(r.status_code, 400)
        r = self.post(is_important=True)
        self.assertEqual(r.status_code, 400)
        r = self.post(user=self.coord, is_featured=True, is_important=True)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_featured"] and r.data["is_important"])
        r = self.post(is_featured=False)                      # harmless false value is accepted
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["is_featured"])

    def test_image_upload_and_validation(self):
        r = self.post(_format="multipart", image=png_file())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["image_url"].endswith(".png"))
        self.assertEqual(self.post(_format="multipart", image=SimpleUploadedFile("evil.png", b"not an image", content_type="image/png")).status_code, 400)
        self.assertEqual(self.post(_format="multipart", image=SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")).status_code, 400)
        self.assertEqual(self.post(_format="multipart", image=SimpleUploadedFile("empty.png", b"", content_type="image/png")).status_code, 400)
        with override_settings(ANNOUNCEMENT_MAX_IMAGE_SIZE=50):
            self.assertEqual(self.post(_format="multipart", image=png_file()).status_code, 400)

    def test_image_replace_and_remove_delete_old_file(self):
        client = self.as_user(self.a)
        r = client.post(reverse("announcement-list"), self.payload(image=png_file("one.png")), format="multipart")
        ann = Announcement.objects.get(pk=r.data["id"])
        storage, old = ann.image.storage, ann.image.name
        self.assertTrue(storage.exists(old))
        with self.captureOnCommitCallbacks(execute=True):
            r = client.patch(reverse("announcement-detail", args=[ann.id]), {"image": png_file("two.png")}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        ann.refresh_from_db()
        self.assertNotEqual(ann.image.name, old)
        self.assertFalse(storage.exists(old))
        new = ann.image.name
        with self.captureOnCommitCallbacks(execute=True):
            r = client.patch(reverse("announcement-detail", args=[ann.id]), {"remove_image": "true"}, format="multipart")
        self.assertIsNone(r.data["image_url"])
        self.assertFalse(storage.exists(new))

    def test_private_attachment_access_control(self):
        r = self.as_user(self.a).post(reverse("announcement-list"),
                                      self.payload(attachment=pdf_file("../../etc/rules.pdf")), format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        att = r.data["attachment"]
        self.assertEqual(att["name"], "rules.pdf")
        ann = Announcement.objects.get(pk=r.data["id"])
        self.assertNotIn("rules", ann.attachment.name)                 # storage name is random
        with self.assertRaises(ValueError):
            ann.attachment.url                                        # no public URL exists
        url = reverse("announcement-attachment", args=[ann.id])
        got = self.as_user(self.b).get(url)
        self.assertEqual(got.status_code, 200)
        self.assertTrue(b"".join(got.streaming_content).startswith(b"%PDF"))
        self.assertEqual(APIClient().get(url).status_code, 401)
        Announcement.objects.filter(pk=ann.pk).update(status=AnnouncementStatus.DRAFT)
        self.assertEqual(self.as_user(self.b).get(url).status_code, 404)           # draft => private
        self.assertEqual(self.as_user(self.a).get(url).status_code, 200)           # owner still can
        self.assertEqual(self.post(_format="multipart", attachment=SimpleUploadedFile("x.pdf", b"nope", content_type="application/pdf")).status_code, 400)

    def test_deleting_announcement_removes_files(self):
        r = self.as_user(self.a).post(reverse("announcement-list"),
                                      self.payload(image=png_file(), attachment=pdf_file()), format="multipart")
        ann = Announcement.objects.get(pk=r.data["id"])
        files = [(ann.image.storage, ann.image.name), (ann.attachment.storage, ann.attachment.name)]
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.as_user(self.a).delete(reverse("announcement-detail", args=[ann.id])).status_code, 204)
        for storage, name in files:
            self.assertFalse(storage.exists(name))

    def test_no_n_plus_one_in_list(self):
        for i in range(10):
            self.make(self.a if i % 2 else self.b, title=f"N{i}")
        client = self.as_user(self.c)
        url = reverse("announcement-list")
        client.get(url)
        with self.assertNumQueries(2):    # one COUNT + one page query (category/author joined, bookmarks annotated)
            r = client.get(url)
        self.assertEqual(len(r.data["results"]), 10)
