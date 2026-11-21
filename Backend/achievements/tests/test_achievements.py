import io
import os
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import Role, User
from achievements.models import (
    Achievement, AchievementCategory, AchievementDocument, DocumentType, Visibility,
)

TMP_ROOT = tempfile.mkdtemp(prefix="achievement-tests-")


def tearDownModule():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def make_user(username, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="Str0ng!Passw0rd",
        full_name=username.title(), phone_number="+9779800000000", country="Nepal",
        role=extra.pop("role", Role.USER), is_active=extra.pop("is_active", True),
        is_email_verified=True, **extra,
    )


def pdf_file(name="certificate.pdf", pad=0):
    return SimpleUploadedFile(name, b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n" + b"0" * pad,
                              content_type="application/pdf")


def image_file(name="photo.png", fmt="PNG", content_type="image/png"):
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), "red").save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def base_data(category, **over):
    data = {
        "title": "National Science Olympiad",
        "category": category.id,
        "description": "Gold medal in the national round.",
        "issuing_organization": "Ministry of Education",
        "achievement_date": (date.today() - timedelta(days=30)).isoformat(),
        "certificate_number": "NSO-2026-001",
        "location": "Kathmandu",
        "visibility": "public",
    }
    data.update(over)
    return data


@override_settings(ACHIEVEMENT_PRIVATE_ROOT=TMP_ROOT)
class AchievementBase(APITestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.category = AchievementCategory.objects.get(slug="academic-achievement")

    # helpers ---------------------------------------------------------------
    def login(self, user):
        self.client.force_authenticate(user)

    def create_via_api(self, user, visibility="public", files=None, **over):
        self.login(user)
        data = base_data(self.category, visibility=visibility, **over)
        data.update(files if files is not None else {"certificate": pdf_file()})
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.json()

    def doc_ids(self, achievement_id):
        return list(AchievementDocument.objects.filter(achievement_id=achievement_id).values_list("id", flat=True))

    def download_url(self, achievement_id, document_id):
        return reverse("achievement-document-download",
                       kwargs={"pk": achievement_id, "document_id": document_id})


class CategoryTests(AchievementBase):
    def test_initial_categories_are_seeded(self):
        names = set(AchievementCategory.objects.values_list("name", flat=True))
        self.assertEqual(names, {
            "Academic Achievement", "Sports Achievement", "Competition Achievement",
            "Participation Certificate", "Training and Workshop", "Leadership Achievement",
            "Volunteering Achievement", "Research and Innovation", "Professional Achievement",
            "Award and Recognition", "Other Achievement",
        })

    def test_category_list_endpoint_and_new_categories_need_no_code(self):
        self.login(self.alice)
        AchievementCategory.objects.create(name="Cultural Achievement")
        AchievementCategory.objects.create(name="Retired Category", is_active=False)
        resp = self.client.get(reverse("achievement-categories"))
        self.assertEqual(resp.status_code, 200)
        names = [c["name"] for c in resp.json()]
        self.assertEqual(len(names), 12)
        self.assertIn("Cultural Achievement", names)
        self.assertNotIn("Retired Category", names)
        self.assertEqual(names[-1], "Other Achievement")  # seeded "Other" stays last

    def test_other_achievement_sorts_after_seeded_categories(self):
        names = list(AchievementCategory.objects.values_list("name", flat=True))
        self.assertEqual(names[-1], "Other Achievement")


class CreateTests(AchievementBase):
    def test_create_with_certificate(self):
        body = self.create_via_api(self.alice)
        self.assertEqual(body["title"], "National Science Olympiad")
        self.assertEqual(body["visibility"], "public")
        self.assertEqual(body["owner"]["id"], self.alice.id)
        self.assertEqual(body["category"]["slug"], "academic-achievement")
        self.assertEqual(len(body["documents"]), 1)
        doc = body["documents"][0]
        self.assertEqual(doc["document_type"], "certificate")
        self.assertEqual(doc["content_type"], "application/pdf")
        self.assertTrue(doc["download_url"].endswith(f"/api/achievements/{body['id']}/documents/{doc['id']}/download/"))
        self.assertNotIn("file", doc)

    def test_owner_cannot_be_set_through_payload(self):
        self.login(self.alice)
        data = base_data(self.category, user=self.bob.id, owner=self.bob.id, certificate=pdf_file())
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Achievement.objects.get(pk=resp.json()["id"]).user_id, self.alice.id)

    def test_visibility_defaults_to_private(self):
        self.login(self.alice)
        data = base_data(self.category, certificate=pdf_file())
        data.pop("visibility")
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["visibility"], "private")

    def test_optional_fields_may_be_omitted(self):
        self.login(self.alice)
        data = base_data(self.category, certificate=pdf_file())
        for key in ("certificate_number", "location", "description"):
            data.pop(key)
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_certificate_and_multiple_supporting_documents(self):
        body = self.create_via_api(self.alice, files={
            "certificate": pdf_file(),
            "supporting_documents": [image_file("photo1.png"), image_file("photo2.jpg", "JPEG", "image/jpeg")],
        })
        self.assertEqual(len(body["documents"]), 3)
        types = sorted(d["document_type"] for d in body["documents"])
        self.assertEqual(types, ["certificate", "supporting", "supporting"])

    def test_supporting_document_alone_is_enough(self):
        body = self.create_via_api(self.alice, files={"supporting_documents": [image_file()]})
        self.assertEqual(len(body["documents"]), 1)

    def test_document_is_required_on_create(self):
        self.login(self.alice)
        resp = self.client.post(reverse("achievement-create"), base_data(self.category), format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("certificate", resp.json())

    def test_required_fields_are_validated(self):
        self.login(self.alice)
        resp = self.client.post(reverse("achievement-create"), {"certificate": pdf_file()}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        for field in ("title", "category", "issuing_organization", "achievement_date"):
            self.assertIn(field, resp.json())

    def test_future_date_rejected(self):
        self.login(self.alice)
        data = base_data(self.category, achievement_date=(date.today() + timedelta(days=2)).isoformat(),
                         certificate=pdf_file())
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("achievement_date", resp.json())

    def test_inactive_or_unknown_category_rejected(self):
        self.login(self.alice)
        inactive = AchievementCategory.objects.create(name="Old", is_active=False)
        for cat_id in (inactive.id, 99999):
            data = base_data(self.category, certificate=pdf_file())
            data["category"] = cat_id
            resp = self.client.post(reverse("achievement-create"), data, format="multipart")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("category", resp.json())

    def test_invalid_visibility_rejected(self):
        self.login(self.alice)
        data = base_data(self.category, visibility="friends", certificate=pdf_file())
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("visibility", resp.json())

    @override_settings(ACHIEVEMENT_MAX_DOCUMENTS=2)
    def test_too_many_documents_rejected(self):
        self.login(self.alice)
        data = base_data(self.category, certificate=pdf_file(),
                         supporting_documents=[image_file("a.png"), image_file("b.png")])
        resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("supporting_documents", resp.json())

    @override_settings(ACHIEVEMENT_REQUIRE_DOCUMENT=False)
    def test_document_requirement_can_be_switched_off(self):
        self.login(self.alice)
        resp = self.client.post(reverse("achievement-create"), base_data(self.category), format="multipart")
        self.assertEqual(resp.status_code, 201, resp.content)


class UploadValidationTests(AchievementBase):
    def post_certificate(self, upload):
        self.login(self.alice)
        data = base_data(self.category, certificate=upload)
        return self.client.post(reverse("achievement-create"), data, format="multipart")

    def test_allowed_formats_are_accepted(self):
        uploads = [
            pdf_file("a.pdf"),
            image_file("a.jpg", "JPEG", "image/jpeg"),
            image_file("a.jpeg", "JPEG", "image/jpeg"),
            image_file("a.png", "PNG", "image/png"),
            image_file("a.webp", "WEBP", "image/webp"),
            image_file("UPPER.PNG", "PNG", "image/png"),
        ]
        for upload in uploads:
            resp = self.post_certificate(upload)
            self.assertEqual(resp.status_code, 201, f"{upload.name}: {resp.content}")

    def test_unsupported_extensions_rejected(self):
        for name, content in (("virus.exe", b"MZ..."), ("notes.txt", b"hello"), ("page.html", b"<html>"),
                              ("doc.docx", b"PK..."), ("archive.pdf.exe", b"%PDF-1.4"), ("noextension", b"%PDF-1.4")):
            resp = self.post_certificate(SimpleUploadedFile(name, content, content_type="application/pdf"))
            self.assertEqual(resp.status_code, 400, name)
            self.assertIn("certificate", resp.json(), name)

    def test_unsupported_declared_content_type_rejected(self):
        upload = SimpleUploadedFile("cert.pdf", b"%PDF-1.4 ...", content_type="text/html")
        resp = self.post_certificate(upload)
        self.assertEqual(resp.status_code, 400)

    def test_renamed_non_pdf_rejected(self):
        resp = self.post_certificate(SimpleUploadedFile("fake.pdf", b"<script>alert(1)</script>",
                                                        content_type="application/pdf"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("valid PDF", str(resp.json()))

    def test_renamed_non_image_rejected(self):
        resp = self.post_certificate(SimpleUploadedFile("fake.png", b"not really an image",
                                                        content_type="image/png"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("valid image", str(resp.json()))

    def test_image_with_wrong_extension_rejected(self):
        png = image_file("a.png", "PNG", "image/png")
        wrong = SimpleUploadedFile("a.jpg", png.read(), content_type="image/jpeg")
        resp = self.post_certificate(wrong)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("do not match", str(resp.json()))

    def test_empty_file_rejected(self):
        resp = self.post_certificate(SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf"))
        self.assertEqual(resp.status_code, 400)

    @override_settings(ACHIEVEMENT_MAX_UPLOAD_SIZE=2048)
    def test_file_size_limit_is_configurable(self):
        resp = self.post_certificate(pdf_file(pad=4096))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("too large", str(resp.json()))
        resp = self.post_certificate(pdf_file(pad=100))
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_oversized_supporting_document_rejected(self):
        with override_settings(ACHIEVEMENT_MAX_UPLOAD_SIZE=2048):
            self.login(self.alice)
            data = base_data(self.category, supporting_documents=[pdf_file(pad=5000)])
            resp = self.client.post(reverse("achievement-create"), data, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("supporting_documents", resp.json())

    def test_failed_upload_creates_nothing(self):
        self.post_certificate(SimpleUploadedFile("fake.pdf", b"nope", content_type="application/pdf"))
        self.assertEqual(Achievement.objects.count(), 0)
        self.assertEqual(AchievementDocument.objects.count(), 0)

    def test_stored_names_are_safe_unique_and_private(self):
        first = self.create_via_api(self.alice, files={"certificate": pdf_file("../../evil name.pdf")})
        second = self.create_via_api(self.alice, files={"certificate": pdf_file("../../evil name.pdf")})
        docs = list(AchievementDocument.objects.order_by("id"))
        self.assertEqual(len(docs), 2)
        pattern = re.compile(rf"^achievements/{self.alice.id}/[0-9a-f]{{32}}\.pdf$")
        for doc in docs:
            self.assertRegex(doc.file.name, pattern)
            self.assertNotIn("evil", doc.file.name)
            self.assertNotIn("/", doc.original_filename)
            self.assertNotIn("..", doc.original_filename)
            self.assertTrue(os.path.exists(doc.file.path))
            # stored outside MEDIA_ROOT, so a /media/ URL can never reach it
            self.assertTrue(os.path.abspath(doc.file.path).startswith(os.path.abspath(TMP_ROOT)))
            self.assertFalse(os.path.abspath(doc.file.path).startswith(os.path.abspath(str(settings.MEDIA_ROOT))))
            with self.assertRaises(ValueError):
                doc.file.url
        self.assertNotEqual(docs[0].file.name, docs[1].file.name)


class ListAndDetailTests(AchievementBase):
    def test_my_list_contains_public_and_private_but_not_others(self):
        self.create_via_api(self.alice, "public", title="Alice public")
        self.create_via_api(self.alice, "private", title="Alice private")
        self.create_via_api(self.bob, "public", title="Bob public")
        self.login(self.alice)
        resp = self.client.get(reverse("achievement-my-list"))
        self.assertEqual(resp.status_code, 200)
        titles = {a["title"] for a in resp.json()["results"]}
        self.assertEqual(titles, {"Alice public", "Alice private"})
        self.assertEqual(resp.json()["count"], 2)

    def test_my_detail_includes_private_and_owner_only_fields(self):
        private = self.create_via_api(self.alice, "private")
        self.login(self.alice)
        resp = self.client.get(reverse("achievement-my-detail", kwargs={"pk": private["id"]}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["visibility"], "private")
        self.assertEqual(resp.json()["certificate_number"], "NSO-2026-001")

    def test_my_detail_of_someone_elses_achievement_is_404(self):
        public = self.create_via_api(self.bob, "public")
        self.login(self.alice)
        resp = self.client.get(reverse("achievement-my-detail", kwargs={"pk": public["id"]}))
        self.assertEqual(resp.status_code, 404)

    def test_pagination(self):
        for i in range(15):
            Achievement.objects.create(
                user=self.alice, category=self.category, title=f"A{i}", issuing_organization="Org",
                achievement_date=date.today() - timedelta(days=i), visibility=Visibility.PUBLIC)
        self.login(self.alice)
        url = reverse("achievement-my-list")
        first = self.client.get(url).json()
        self.assertEqual(first["count"], 15)
        self.assertEqual(len(first["results"]), 12)
        self.assertIsNotNone(first["next"])
        second = self.client.get(url, {"page": 2}).json()
        self.assertEqual(len(second["results"]), 3)
        small = self.client.get(url, {"page_size": 5}).json()
        self.assertEqual(len(small["results"]), 5)
        # newest achievement first
        self.assertEqual(first["results"][0]["title"], "A0")

    def test_public_profile_list_is_paginated(self):
        for i in range(14):
            Achievement.objects.create(
                user=self.alice, category=self.category, title=f"P{i}", issuing_organization="Org",
                achievement_date=date.today(), visibility=Visibility.PUBLIC)
        self.login(self.bob)
        body = self.client.get(reverse("user-achievements", kwargs={"user_id": self.alice.id})).json()
        self.assertEqual(body["count"], 14)
        self.assertEqual(len(body["results"]), 12)


class VisibilityTests(AchievementBase):
    def setUp(self):
        super().setUp()
        self.public = self.create_via_api(self.alice, "public", title="Public one")
        self.private = self.create_via_api(self.alice, "private", title="Private one")

    def test_other_user_can_view_public_detail_without_owner_only_fields(self):
        self.login(self.bob)
        resp = self.client.get(reverse("achievement-detail", kwargs={"pk": self.public["id"]}))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["title"], "Public one")
        for key in ("title", "category", "description", "issuing_organization", "achievement_date", "documents"):
            self.assertIn(key, body)
        self.assertNotIn("visibility", body)
        self.assertNotIn("certificate_number", body)
        self.assertEqual(len(body["documents"]), 1)

    def test_other_user_cannot_view_private_detail(self):
        self.login(self.bob)
        resp = self.client.get(reverse("achievement-detail", kwargs={"pk": self.private["id"]}))
        self.assertEqual(resp.status_code, 404)

    def test_owner_can_view_own_private_via_detail(self):
        self.login(self.alice)
        resp = self.client.get(reverse("achievement-detail", kwargs={"pk": self.private["id"]}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["visibility"], "private")

    def test_profile_shows_only_public_achievements_to_others(self):
        self.login(self.bob)
        resp = self.client.get(reverse("user-achievements", kwargs={"user_id": self.alice.id}))
        self.assertEqual(resp.status_code, 200)
        titles = [a["title"] for a in resp.json()["results"]]
        self.assertEqual(titles, ["Public one"])
        raw = resp.content.decode()
        self.assertNotIn("Private one", raw)
        self.assertNotIn("private", raw.lower().replace("private_media", ""))

    def test_profile_endpoint_is_public_only_even_for_the_owner(self):
        self.login(self.alice)
        resp = self.client.get(reverse("user-achievements", kwargs={"user_id": self.alice.id}))
        self.assertEqual([a["title"] for a in resp.json()["results"]], ["Public one"])

    def test_profile_of_unknown_or_inactive_user_is_404(self):
        ghost = make_user("ghost", is_active=False)
        self.login(self.bob)
        for user_id in (ghost.id, 987654):
            resp = self.client.get(reverse("user-achievements", kwargs={"user_id": user_id}))
            self.assertEqual(resp.status_code, 404)

    def test_making_public_private_hides_it_immediately(self):
        doc_id = self.doc_ids(self.public["id"])[0]
        self.login(self.bob)
        self.assertEqual(self.client.get(self.download_url(self.public["id"], doc_id)).status_code, 200)
        self.login(self.alice)
        resp = self.client.patch(reverse("achievement-detail", kwargs={"pk": self.public["id"]}),
                                 {"visibility": "private"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.login(self.bob)
        self.assertEqual(self.client.get(reverse("achievement-detail", kwargs={"pk": self.public["id"]})).status_code, 404)
        self.assertEqual(self.client.get(self.download_url(self.public["id"], doc_id)).status_code, 404)
        listing = self.client.get(reverse("user-achievements", kwargs={"user_id": self.alice.id})).json()
        self.assertEqual(listing["count"], 0)

    def test_making_private_public_exposes_it(self):
        self.login(self.alice)
        self.client.patch(reverse("achievement-detail", kwargs={"pk": self.private["id"]}),
                          {"visibility": "public"}, format="json")
        self.login(self.bob)
        listing = self.client.get(reverse("user-achievements", kwargs={"user_id": self.alice.id})).json()
        self.assertEqual(listing["count"], 2)

    def test_no_global_listing_or_search_endpoints(self):
        self.login(self.bob)
        self.assertEqual(self.client.get("/api/achievements/").status_code, 405)
        self.assertEqual(self.client.get("/api/achievements/search/").status_code, 404)
        # query parameters on the profile list never filter results
        url = reverse("user-achievements", kwargs={"user_id": self.alice.id})
        self.assertEqual(self.client.get(url, {"search": "zzz-no-match"}).json()["count"], 1)


class UpdateTests(AchievementBase):
    def setUp(self):
        super().setUp()
        self.item = self.create_via_api(self.alice, "public", files={
            "certificate": pdf_file("original.pdf"), "supporting_documents": [image_file("proof.png")]})
        self.url = reverse("achievement-detail", kwargs={"pk": self.item["id"]})

    def test_owner_patch_fields(self):
        self.login(self.alice)
        other_cat = AchievementCategory.objects.get(slug="sports-achievement")
        resp = self.client.patch(self.url, {
            "title": "Renamed", "category": other_cat.id, "description": "New", "issuing_organization": "New Org",
            "achievement_date": "2025-01-02", "certificate_number": "X-1", "location": "Pokhara",
            "visibility": "private",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual((body["title"], body["category"]["id"], body["visibility"], body["location"]),
                         ("Renamed", other_cat.id, "private", "Pokhara"))
        self.assertEqual(len(body["documents"]), 2)  # untouched

    def test_owner_put(self):
        self.login(self.alice)
        resp = self.client.put(self.url, base_data(self.category, title="Replaced via PUT", visibility="private"),
                               format="multipart")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["title"], "Replaced via PUT")
        self.assertEqual(len(resp.json()["documents"]), 2)

    def test_replacing_certificate_keeps_other_documents(self):
        old_cert = AchievementDocument.objects.get(achievement_id=self.item["id"], document_type="certificate")
        old_path = old_cert.file.path
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(self.url, {"certificate": pdf_file("renewed.pdf")}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.content)
        docs = AchievementDocument.objects.filter(achievement_id=self.item["id"])
        self.assertEqual(docs.count(), 2)
        self.assertEqual(docs.filter(document_type="certificate").count(), 1)
        self.assertEqual(docs.filter(document_type="supporting").count(), 1)
        self.assertFalse(AchievementDocument.objects.filter(pk=old_cert.pk).exists())
        self.assertFalse(os.path.exists(old_path))  # old file removed from storage

    def test_adding_supporting_documents_never_deletes_existing_ones(self):
        before = set(self.doc_ids(self.item["id"]))
        self.login(self.alice)
        resp = self.client.patch(self.url, {"supporting_documents": [image_file("more.png")]}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        after = set(self.doc_ids(self.item["id"]))
        self.assertTrue(before < after)
        self.assertEqual(len(after), 3)

    def test_removing_a_document(self):
        support = AchievementDocument.objects.get(achievement_id=self.item["id"], document_type="supporting")
        path = support.file.path
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(self.url, {"remove_document_ids": [support.id]}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.json()["documents"]), 1)
        self.assertFalse(os.path.exists(path))

    def test_cannot_remove_the_last_document(self):
        ids = self.doc_ids(self.item["id"])
        self.login(self.alice)
        resp = self.client.patch(self.url, {"remove_document_ids": ids}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(self.doc_ids(self.item["id"])), 2)

    def test_cannot_remove_a_document_of_another_achievement(self):
        bobs = self.create_via_api(self.bob, "public")
        bobs_doc = self.doc_ids(bobs["id"])[0]
        self.login(self.alice)
        resp = self.client.patch(self.url, {"remove_document_ids": [bobs_doc]}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(AchievementDocument.objects.filter(pk=bobs_doc).exists())

    def test_invalid_replacement_leaves_everything_unchanged(self):
        before = set(self.doc_ids(self.item["id"]))
        self.login(self.alice)
        bad = SimpleUploadedFile("bad.pdf", b"not a pdf", content_type="application/pdf")
        resp = self.client.patch(self.url, {"title": "Should not stick", "certificate": bad}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(self.doc_ids(self.item["id"])), before)
        self.assertEqual(Achievement.objects.get(pk=self.item["id"]).title, "National Science Olympiad")

    def test_owner_cannot_be_changed_by_update(self):
        self.login(self.alice)
        resp = self.client.patch(self.url, {"user": self.bob.id, "owner": self.bob.id}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Achievement.objects.get(pk=self.item["id"]).user_id, self.alice.id)

    def test_other_user_cannot_update_public_achievement(self):
        self.login(self.bob)
        for method in (self.client.patch, self.client.put):
            resp = method(self.url, {"title": "Hacked"}, format="json")
            self.assertEqual(resp.status_code, 403)
        self.assertEqual(Achievement.objects.get(pk=self.item["id"]).title, "National Science Olympiad")

    def test_other_user_cannot_update_private_achievement(self):
        private = self.create_via_api(self.alice, "private")
        self.login(self.bob)
        resp = self.client.patch(reverse("achievement-detail", kwargs={"pk": private["id"]}),
                                 {"title": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(Achievement.objects.get(pk=private["id"]).title, "Hacked")


class DeleteTests(AchievementBase):
    def test_owner_deletes_achievement_documents_and_files(self):
        item = self.create_via_api(self.alice, "public", files={
            "certificate": pdf_file(), "supporting_documents": [image_file()]})
        paths = [d.file.path for d in AchievementDocument.objects.filter(achievement_id=item["id"])]
        self.assertTrue(all(os.path.exists(p) for p in paths))
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.delete(reverse("achievement-detail", kwargs={"pk": item["id"]}))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Achievement.objects.filter(pk=item["id"]).exists())
        self.assertEqual(AchievementDocument.objects.filter(achievement_id=item["id"]).count(), 0)
        self.assertFalse(any(os.path.exists(p) for p in paths))

    def test_other_user_cannot_delete_public_or_private(self):
        public = self.create_via_api(self.alice, "public")
        private = self.create_via_api(self.alice, "private")
        self.login(self.bob)
        self.assertEqual(self.client.delete(reverse("achievement-detail", kwargs={"pk": public["id"]})).status_code, 403)
        self.assertEqual(self.client.delete(reverse("achievement-detail", kwargs={"pk": private["id"]})).status_code, 404)
        self.assertEqual(Achievement.objects.filter(user=self.alice).count(), 2)

    def test_deleting_the_user_removes_their_files(self):
        item = self.create_via_api(self.alice, "public")
        path = AchievementDocument.objects.get(achievement_id=item["id"]).file.path
        with self.captureOnCommitCallbacks(execute=True):
            self.alice.delete()
        self.assertFalse(os.path.exists(path))
        self.assertEqual(AchievementDocument.objects.count(), 0)

    def test_deleting_missing_achievement_is_404(self):
        self.login(self.alice)
        self.assertEqual(self.client.delete(reverse("achievement-detail", kwargs={"pk": 424242})).status_code, 404)


class DownloadTests(AchievementBase):
    def setUp(self):
        super().setUp()
        self.public = self.create_via_api(self.alice, "public", files={"certificate": pdf_file("my cert.pdf")})
        self.private = self.create_via_api(self.alice, "private", files={"certificate": pdf_file("secret.pdf")})
        self.public_doc = self.doc_ids(self.public["id"])[0]
        self.private_doc = self.doc_ids(self.private["id"])[0]

    def test_owner_downloads_public_and_private_documents(self):
        self.login(self.alice)
        for item, doc in ((self.public, self.public_doc), (self.private, self.private_doc)):
            resp = self.client.get(self.download_url(item["id"], doc))
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(b"".join(resp.streaming_content).startswith(b"%PDF-"))

    def test_download_headers_are_safe(self):
        self.login(self.alice)
        resp = self.client.get(self.download_url(self.public["id"], self.public_doc))
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp["Content-Disposition"].startswith("attachment"))
        self.assertIn("my_cert.pdf", resp["Content-Disposition"])
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", resp["Cache-Control"])
        stored = AchievementDocument.objects.get(pk=self.public_doc).file.name
        for value in resp.headers.values():
            self.assertNotIn(os.path.basename(stored), value)
            self.assertNotIn(TMP_ROOT, value)
        list(resp.streaming_content)

    def test_image_download_content_type(self):
        item = self.create_via_api(self.alice, "public", files={"certificate": image_file("p.png")})
        doc_id = self.doc_ids(item["id"])[0]
        self.login(self.bob)
        resp = self.client.get(self.download_url(item["id"], doc_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        list(resp.streaming_content)

    def test_other_user_downloads_public_document(self):
        self.login(self.bob)
        resp = self.client.get(self.download_url(self.public["id"], self.public_doc))
        self.assertEqual(resp.status_code, 200)
        list(resp.streaming_content)

    def test_other_user_cannot_download_private_document(self):
        self.login(self.bob)
        resp = self.client.get(self.download_url(self.private["id"], self.private_doc))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(b"%PDF", resp.content)

    def test_document_id_must_belong_to_the_achievement_in_the_url(self):
        # Trying to reach a private document through a public achievement's URL.
        self.login(self.bob)
        resp = self.client.get(self.download_url(self.public["id"], self.private_doc))
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_download_is_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.download_url(self.public["id"], self.public_doc)).status_code, 401)

    def test_missing_document_is_404(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.download_url(self.public["id"], 999999)).status_code, 404)

    def test_missing_file_in_storage_is_404_without_leaking_paths(self):
        doc = AchievementDocument.objects.get(pk=self.public_doc)
        os.remove(doc.file.path)
        self.login(self.alice)
        resp = self.client.get(self.download_url(self.public["id"], self.public_doc))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(TMP_ROOT, resp.content.decode())

    def test_api_responses_never_expose_storage_paths(self):
        self.login(self.alice)
        for url in (reverse("achievement-my-list"),
                    reverse("achievement-detail", kwargs={"pk": self.public["id"]}),
                    reverse("user-achievements", kwargs={"user_id": self.alice.id})):
            text = self.client.get(url).content.decode()
            self.assertNotIn(TMP_ROOT, text)
            self.assertNotIn("private_media", text)
            self.assertNotIn('"file"', text)  # no raw FileField value is ever serialised
            self.assertNotIn("achievements/" + str(self.alice.id) + "/" + "0" * 4, text)


class AuthenticationTests(AchievementBase):
    def test_every_endpoint_requires_authentication(self):
        item = self.create_via_api(self.alice, "public")
        doc_id = self.doc_ids(item["id"])[0]
        self.client.force_authenticate(None)
        calls = [
            ("post", reverse("achievement-create")),
            ("get", reverse("achievement-categories")),
            ("get", reverse("achievement-my-list")),
            ("get", reverse("achievement-my-detail", kwargs={"pk": item["id"]})),
            ("get", reverse("achievement-detail", kwargs={"pk": item["id"]})),
            ("patch", reverse("achievement-detail", kwargs={"pk": item["id"]})),
            ("put", reverse("achievement-detail", kwargs={"pk": item["id"]})),
            ("delete", reverse("achievement-detail", kwargs={"pk": item["id"]})),
            ("get", reverse("user-achievements", kwargs={"user_id": self.alice.id})),
            ("get", self.download_url(item["id"], doc_id)),
        ]
        for method, url in calls:
            resp = getattr(self.client, method)(url)
            self.assertEqual(resp.status_code, 401, f"{method.upper()} {url}")
        self.assertTrue(Achievement.objects.filter(pk=item["id"]).exists())


class ModelTests(AchievementBase):
    def test_only_one_certificate_per_achievement(self):
        item = self.create_via_api(self.alice, "public")
        achievement = Achievement.objects.get(pk=item["id"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            AchievementDocument.objects.create(
                achievement=achievement, document_type=DocumentType.CERTIFICATE,
                file=SimpleUploadedFile("again.pdf", b"%PDF-1.4"), original_filename="again.pdf")

    def test_invalid_visibility_is_blocked_by_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Achievement.objects.create(
                user=self.alice, category=self.category, title="t", issuing_organization="o",
                achievement_date=date.today(), visibility="friends")

    def test_category_slug_is_generated_and_unique(self):
        a = AchievementCategory.objects.create(name="Arts & Culture")
        b = AchievementCategory.objects.create(name="Arts   Culture")
        self.assertEqual(a.slug, "arts-culture")
        self.assertEqual(b.slug, "arts-culture-2")
