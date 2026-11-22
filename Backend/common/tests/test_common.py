"""Tests for the shared Common module: file validation, names, permissions, health check."""
from io import BytesIO
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIRequestFactory

from accounts.models import User
from common import files, permissions, signing, validators
from common.validators import KIND_IMAGE, KIND_PDF, validate_upload

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
    b"trailer << /Root 1 0 R >>\n%%EOF\n"
)


def image_upload(fmt="PNG", name=None, content_type=None, size=(40, 30)):
    buffer = BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buffer, fmt)
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "BMP": "bmp"}[fmt]
    mime = content_type or f"image/{'jpeg' if ext == 'jpg' else ext}"
    return SimpleUploadedFile(name or f"photo.{ext}", buffer.getvalue(), mime)


def pdf_upload(content=MINIMAL_PDF, name="certificate.pdf", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type)


class ImageValidationTests(SimpleTestCase):
    def test_valid_formats_are_detected_from_content(self):
        for fmt, ext, mime in (("JPEG", "jpg", "image/jpeg"), ("PNG", "png", "image/png"), ("WEBP", "webp", "image/webp")):
            with self.subTest(fmt=fmt):
                detected = validate_upload(image_upload(fmt))
                self.assertEqual((detected.kind, detected.format, detected.extension, detected.mime), (KIND_IMAGE, fmt, ext, mime))
                self.assertEqual((detected.width, detected.height), (40, 30))

    def test_jpeg_alias_extension_and_mime_accepted(self):
        detected = validate_upload(image_upload("JPEG", name="a.jpeg", content_type="image/jpg"))
        self.assertEqual(detected.format, "JPEG")

    def test_generic_content_type_is_accepted(self):
        self.assertEqual(validate_upload(image_upload("PNG", content_type="application/octet-stream")).format, "PNG")

    def test_gif_and_bmp_rejected(self):
        for fmt in ("GIF", "BMP"):
            with self.subTest(fmt=fmt), self.assertRaises(ValidationError) as ctx:
                validate_upload(image_upload(fmt))
            self.assertEqual(ctx.exception.code, "unsupported_format")

    def test_extension_must_match_content(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(image_upload("PNG", name="photo.jpg", content_type="application/octet-stream"))
        self.assertEqual(ctx.exception.code, "extension_mismatch")

    def test_declared_mime_must_match_content(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(image_upload("PNG", content_type="image/jpeg"))
        self.assertEqual(ctx.exception.code, "mime_mismatch")

    def test_fake_image_rejected(self):
        upload = SimpleUploadedFile("photo.png", b"\x89PNG\r\n\x1a\n" + b"garbage" * 20, "image/png")
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(upload)
        self.assertEqual(ctx.exception.code, "invalid_image")

    def test_text_renamed_to_png_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(SimpleUploadedFile("photo.png", b"just some text", "image/png"))
        self.assertEqual(ctx.exception.code, "unsupported_format")

    def test_size_limit_enforced(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(image_upload("PNG", size=(200, 200)), max_image_bytes=100)
        self.assertEqual(ctx.exception.code, "file_too_large")

    def test_empty_file_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(SimpleUploadedFile("a.png", b"", "image/png"))
        self.assertEqual(ctx.exception.code, "empty_file")

    def test_image_not_allowed_when_only_pdf(self):
        with self.assertRaises(ValidationError):
            validate_upload(image_upload("PNG"), allowed_kinds=(KIND_PDF,))

    @override_settings(PROFILE_IMAGE_MAX_PIXELS=100)
    def test_decompression_bomb_guard(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(image_upload("PNG", size=(20, 20)))
        self.assertEqual(ctx.exception.code, "image_too_large")


class ForbiddenContentTests(SimpleTestCase):
    def test_executables_scripts_archives_rejected(self):
        samples = {
            "evil.exe": b"MZ\x90\x00" + b"\x00" * 64,
            "evil.png": b"\x7fELF\x02\x01\x01" + b"\x00" * 64,
            "run.pdf": b"#!/bin/sh\nrm -rf /\n",
            "doc.pdf": b"PK\x03\x04" + b"\x00" * 64,
        }
        for name, content in samples.items():
            with self.subTest(name=name), self.assertRaises(ValidationError) as ctx:
                validate_upload(SimpleUploadedFile(name, content, "application/octet-stream"))
            self.assertEqual(ctx.exception.code, "forbidden_file_type")

    def test_svg_rejected(self):
        svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        for name in ("logo.svg", "logo.png"):
            with self.subTest(name=name), self.assertRaises(ValidationError) as ctx:
                validate_upload(SimpleUploadedFile(name, svg, "image/svg+xml"))
            self.assertEqual(ctx.exception.code, "forbidden_file_type")

    def test_html_rejected(self):
        with self.assertRaises(ValidationError):
            validate_upload(SimpleUploadedFile("x.pdf", b"  <html><body>hi</body></html>", "text/html"))

    def test_null_byte_in_name_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(image_upload("PNG", name="photo.png\x00.exe"))
        self.assertEqual(ctx.exception.code, "invalid_filename")


class PdfValidationTests(SimpleTestCase):
    def test_valid_pdf(self):
        detected = validate_upload(pdf_upload())
        self.assertEqual((detected.kind, detected.mime, detected.extension), (KIND_PDF, "application/pdf", "pdf"))

    def test_pdf_without_eof_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(pdf_upload(MINIMAL_PDF.replace(b"%%EOF", b"")))
        self.assertEqual(ctx.exception.code, "invalid_pdf")

    def test_pdf_with_javascript_rejected(self):
        evil = MINIMAL_PDF.replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >>")
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(pdf_upload(evil))
        self.assertEqual(ctx.exception.code, "pdf_active_content")

    def test_hex_escaped_javascript_name_rejected(self):
        evil = MINIMAL_PDF.replace(b"/Type /Catalog", b"/Type /Catalog /AA << /O << /S /J#61vaScript >> >>")
        with self.assertRaises(ValidationError):
            validate_upload(pdf_upload(evil))

    def test_pdf_size_limit(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(pdf_upload(), max_pdf_bytes=10)
        self.assertEqual(ctx.exception.code, "file_too_large")

    def test_pdf_with_wrong_extension_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(pdf_upload(name="certificate.png", content_type="application/octet-stream"))
        self.assertEqual(ctx.exception.code, "extension_mismatch")

    def test_pdf_not_allowed_when_only_images(self):
        with self.assertRaises(ValidationError):
            validate_upload(pdf_upload(), allowed_kinds=(KIND_IMAGE,))


class FileNameTests(SimpleTestCase):
    def test_display_name_is_sanitised(self):
        self.assertEqual(files.safe_display_name("../../etc/passwd"), "passwd")
        self.assertEqual(files.safe_display_name("C:\\Users\\me\\Cert (final).pdf"), "Cert final.pdf")
        self.assertEqual(files.safe_display_name("<script>.pdf"), "script.pdf")
        self.assertEqual(files.safe_display_name(""), "file")
        self.assertEqual(files.safe_display_name("...."), "file")
        self.assertLessEqual(len(files.safe_display_name("a" * 300 + ".pdf")), 100)
        self.assertTrue(files.safe_display_name("a" * 300 + ".pdf").endswith(".pdf"))

    def test_storage_name_is_random_and_safe(self):
        first = files.build_storage_name("achievements", "abc-123", "evidence", extension="pdf")
        second = files.build_storage_name("achievements", "abc-123", "evidence", extension="pdf")
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^achievements/abc-123/evidence/[0-9a-f]{32}\.pdf$")

    def test_path_traversal_segments_rejected(self):
        for bad in ("..", "a/b", "a\\b", "", "x y"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                files.build_storage_name("achievements", bad, extension="pdf")
        with self.assertRaises(ValueError):
            files.build_storage_name("a", extension="../pdf")

    def test_reencode_strips_metadata(self):
        buffer = BytesIO()
        image = Image.new("RGB", (3000, 1000))
        exif = image.getexif()
        exif[0x010E] = "secret description"
        image.save(buffer, "JPEG", exif=exif)
        upload = SimpleUploadedFile("a.jpg", buffer.getvalue(), "image/jpeg")
        content, width, height, ext = files.reencode_image(upload, "JPEG")
        self.assertEqual((width, height, ext), (2048, 683, "jpg"))
        with Image.open(BytesIO(content.read())) as result:
            self.assertEqual(dict(result.getexif()), {})


class TextValidatorTests(SimpleTestCase):
    def test_plain_text(self):
        validators.validate_plain_text("Line one\nLine two <3")
        for bad in ("<b>bold</b>", "click javascript:alert(1)", "a\x00b", "data:text/html,hi"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validators.validate_plain_text(bad)

    def test_single_line(self):
        with self.assertRaises(ValidationError):
            validators.validate_single_line("two\nlines")

    def test_http_url(self):
        validators.validate_http_url("https://example.com/register?x=1")
        for bad in ("javascript:alert(1)", "ftp://example.com", "file:///etc/passwd", "data:text/html,x", "example.com"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validators.validate_http_url(bad)

    def test_phone(self):
        validators.validate_phone("+977 (1) 555-1234")
        for bad in ("12", "call me", "+1234567890123456789"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validators.validate_phone(bad)

    def test_tag_list(self):
        validators.validate_tag_list(["Python", "Public speaking"])
        for bad in ("python", [""], ["x" * 41], ["a", "A"], ["<b>x</b>"], ["t"] * 21):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validators.validate_tag_list(bad)


class PermissionHelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u1", email="u1@example.com", password="x-Pass-123!", full_name="U")
        cls.coord = User.objects.create_user(username="c1", email="c1@example.com", password="x-Pass-123!", full_name="C", role="coordinator")
        cls.admin = User.objects.create_user(username="a1", email="a1@example.com", password="x-Pass-123!", full_name="A", role="admin")

    def test_role_helpers(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(permissions.is_authenticated(AnonymousUser()))
        self.assertFalse(permissions.is_moderator(self.user))
        self.assertTrue(permissions.is_moderator(self.coord))
        self.assertTrue(permissions.is_moderator(self.admin))
        self.assertFalse(permissions.is_admin(self.coord))
        self.assertTrue(permissions.is_admin(self.admin))

    def test_is_owner_permission(self):
        request = APIRequestFactory().get("/")
        request.user = self.user
        obj = mock.Mock(user_id=self.user.pk)
        view = mock.Mock(owner_field="user")
        self.assertTrue(permissions.IsOwner().has_object_permission(request, view, obj))
        request.user = self.admin
        self.assertFalse(permissions.IsOwner().has_object_permission(request, view, obj))

    def test_read_any_write_authenticated(self):
        from django.contrib.auth.models import AnonymousUser

        factory = APIRequestFactory()
        perm = permissions.ReadAnyWriteAuthenticated()
        get = factory.get("/")
        get.user = AnonymousUser()
        post = factory.post("/")
        post.user = AnonymousUser()
        self.assertTrue(perm.has_permission(get, None))
        self.assertFalse(perm.has_permission(post, None))
        post.user = self.user
        self.assertTrue(perm.has_permission(post, None))

    def test_relationship_helpers_use_friends_module(self):
        from common import relationships
        from friends.models import Friendship, UserBlock

        self.assertEqual(relationships.hidden_user_ids(self.user), set())
        UserBlock.objects.create(blocker=self.user, blocked=self.coord)
        self.assertEqual(relationships.hidden_user_ids(self.coord), {self.user.pk})
        self.assertTrue(relationships.is_blocked_between(self.coord, self.user))
        Friendship.objects.create(user1=self.user, user2=self.admin)
        self.assertTrue(relationships.are_friends(self.admin, self.user))
        self.assertEqual(relationships.friend_ids(self.user), {self.admin.pk})
        blocks = UserBlock.objects.all()
        self.assertEqual(relationships.exclude_hidden(blocks, self.coord, field="blocker").count(), 0)
        self.assertEqual(relationships.exclude_hidden(blocks, self.admin, field="blocker").count(), 1)


class SigningTests(SimpleTestCase):
    def test_token_bound_to_kind_object_and_expiry(self):
        token = signing.make_download_token("evidence", "obj-1", "user-1")
        self.assertEqual(signing.read_download_token(token, kind="evidence", object_id="obj-1", max_age=60), "user-1")
        self.assertIsNone(signing.read_download_token(token, kind="other", object_id="obj-1", max_age=60))
        self.assertIsNone(signing.read_download_token(token, kind="evidence", object_id="obj-2", max_age=60))
        self.assertIsNone(signing.read_download_token(token + "x", kind="evidence", object_id="obj-1", max_age=60))
        self.assertIsNone(signing.read_download_token("", kind="evidence", object_id="obj-1", max_age=60))
        with mock.patch("django.core.signing.time.time", return_value=10**10):
            self.assertIsNone(signing.read_download_token(token, kind="evidence", object_id="obj-1", max_age=60))


@override_settings(SECURE_SSL_REDIRECT=False)
class HealthCheckTests(TestCase):
    def test_health_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertIn(data["status"], ("ok", "degraded"))
        body = response.content.decode()
        for secret in ("PASSWORD", "SECRET", "postgres", "DB_"):
            self.assertNotIn(secret, body)

    def test_health_database_down(self):
        with mock.patch("common.views._database_ok", return_value=False):
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "service_unavailable")
