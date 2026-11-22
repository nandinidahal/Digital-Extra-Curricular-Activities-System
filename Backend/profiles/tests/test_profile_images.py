import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from .base import ProfileTestCase


class ImageTestMixin:
    """Same behaviour for the profile picture and the cover photo."""

    endpoint = None  # "me-picture" / "me-cover"
    field = None  # "profile_picture" / "cover_photo"

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def current_file(self):
        return getattr(self.profile_of(self.user), self.field)

    # ----- valid uploads ----------------------------------------------------
    def test_valid_upload_for_each_allowed_format(self):
        for fmt in ("JPEG", "PNG", "WEBP"):
            response = self.upload(self.endpoint, self.image_file(fmt))
            self.assertEqual(response.status_code, 200, (fmt, response.content))
            url = response.json()["data"]["profile"][self.field]
            self.assertTrue(url.startswith("http://testserver/media/profiles/"), url)
            self.assertTrue(self.current_file().name.endswith({"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[fmt]))

    def test_url_is_absolute_and_file_exists_on_disk(self):
        response = self.upload(self.endpoint, self.image_file("PNG"))
        self.assertTrue(response.json()["data"]["profile"][self.field].startswith("http"))
        self.assertTrue(os.path.exists(self.current_file().path))

    def test_stored_name_is_random_and_ignores_client_filename(self):
        file = self.image_file("PNG", name="../../../evil name.png")
        self.upload(self.endpoint, file)
        name = self.current_file().name
        self.assertNotIn("evil", name)
        self.assertNotIn("..", name)
        self.assertIn(f"profiles/{self.user.pk}/", name)

    def test_extension_comes_from_real_content_not_filename(self):
        self.upload(self.endpoint, self.image_file("PNG", name="really_a_png.jpg"))
        self.assertTrue(self.current_file().name.endswith(".png"))

    def test_upload_keeps_other_profile_fields(self):
        self.client.patch(self.url("me"), {"headline": "Keep me"}, format="json")
        response = self.upload(self.endpoint, self.image_file())
        profile = response.json()["data"]["profile"]
        self.assertEqual(profile["headline"], "Keep me")

    def test_image_is_reencoded_and_metadata_stripped(self):
        source = Image.new("RGB", (30, 30), (10, 20, 30))
        exif = Image.Exif()
        exif[0x010E] = "SECRET DESCRIPTION"
        buffer = BytesIO()
        source.save(buffer, "JPEG", exif=exif)
        self.upload(self.endpoint, SimpleUploadedFile("a.jpg", buffer.getvalue(), "image/jpeg"))
        with Image.open(self.current_file().path) as stored:
            self.assertNotIn(0x010E, stored.getexif())

    def test_large_images_are_downscaled(self):
        self.upload(self.endpoint, self.image_file("PNG", size=(3000, 3000)))
        with Image.open(self.current_file().path) as stored:
            self.assertLessEqual(max(stored.size), 2400)

    # ----- invalid uploads --------------------------------------------------
    def test_text_file_pretending_to_be_image_is_rejected(self):
        fake = SimpleUploadedFile("photo.png", b"this is not an image", "image/png")
        body = self.assertError(self.upload(self.endpoint, fake), 400, "validation_error")
        self.assertIn("image", body["errors"])
        self.assertFalse(self.current_file())

    def test_executable_content_is_rejected(self):
        for name, content, ctype in [
            ("run.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream"),
            ("shell.php.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg"),
            ("script.html", b"<script>alert(1)</script>", "text/html"),
        ]:
            self.assertError(self.upload(self.endpoint, SimpleUploadedFile(name, content, ctype)),
                             400, "validation_error")
        self.assertEqual(self.stored_files(), [])

    def test_svg_is_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        self.assertError(self.upload(self.endpoint, SimpleUploadedFile("a.svg", svg, "image/svg+xml")),
                         400, "validation_error")

    def test_unsupported_but_real_image_format_is_rejected(self):
        body = self.assertError(self.upload(self.endpoint, self.image_file("GIF")), 400, "validation_error")
        self.assertIn("Unsupported", body["errors"]["image"][0])

    def test_truncated_image_is_rejected(self):
        good = self.image_file("PNG", size=(200, 200), noisy=True).read()
        broken = SimpleUploadedFile("cut.png", good[: len(good) // 2], "image/png")
        self.assertError(self.upload(self.endpoint, broken), 400, "validation_error")
        self.assertFalse(self.current_file())

    def test_empty_file_is_rejected(self):
        self.assertError(self.upload(self.endpoint, SimpleUploadedFile("e.png", b"", "image/png")),
                         400, "validation_error")

    def test_missing_file_is_rejected(self):
        response = self.client.post(self.url(self.endpoint), {}, format="multipart")
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("image", body["errors"])

    def test_oversized_file_is_rejected(self):
        with override_settings(PROFILE_PICTURE_MAX_BYTES=2000, PROFILE_COVER_MAX_BYTES=2000):
            big = self.image_file("PNG", size=(120, 120), noisy=True)
            self.assertGreater(big.size, 2000)
            body = self.assertError(self.upload(self.endpoint, big), 400, "validation_error")
        self.assertIn("too large", body["errors"]["image"][0])
        self.assertFalse(self.current_file())

    def test_too_many_pixels_is_rejected(self):
        with override_settings(PROFILE_IMAGE_MAX_PIXELS=1000):
            self.assertError(self.upload(self.endpoint, self.image_file("PNG", size=(100, 100))),
                             400, "validation_error")

    def test_json_body_is_rejected(self):
        response = self.client.post(self.url(self.endpoint), {"image": "abc"}, format="json")
        self.assertEqual(response.status_code, 415)

    def test_non_file_value_is_rejected(self):
        response = self.client.post(self.url(self.endpoint), {"image": "just text"}, format="multipart")
        self.assertError(response, 400, "validation_error")

    # ----- replace / remove / cleanup ----------------------------------------------
    def test_replacing_image_deletes_the_old_file(self):
        self.upload(self.endpoint, self.image_file("PNG"))
        old_path = self.current_file().path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.upload(self.endpoint, self.image_file("JPEG"))
        self.assertEqual(response.status_code, 200, response.content)
        new_path = self.current_file().path
        self.assertNotEqual(old_path, new_path)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))
        self.assertEqual(len(self.stored_files()), 1)

    def test_failed_validation_keeps_the_existing_image(self):
        self.upload(self.endpoint, self.image_file("PNG"))
        path = self.current_file().path
        self.upload(self.endpoint, SimpleUploadedFile("x.png", b"garbage", "image/png"))
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.current_file().path, path)

    def test_removing_image_deletes_the_file(self):
        self.upload(self.endpoint, self.image_file("PNG"))
        path = self.current_file().path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url(self.endpoint))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["data"]["profile"][self.field])
        self.assertFalse(self.current_file())
        self.assertFalse(os.path.exists(path))

    def test_removing_when_nothing_is_set_is_harmless(self):
        response = self.client.delete(self.url(self.endpoint))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["data"]["profile"][self.field])

    def test_deleting_the_profile_deletes_the_files(self):
        self.upload(self.endpoint, self.image_file("PNG"))
        path = self.current_file().path
        self.profile_of(self.user).delete()
        self.assertFalse(os.path.exists(path))

    # ----- auth / isolation ---------------------------------------------------------
    def test_requires_authentication(self):
        self.logout()
        self.assertEqual(self.upload(self.endpoint, self.image_file()).status_code, 401)
        self.assertEqual(self.client.delete(self.url(self.endpoint)).status_code, 401)

    def test_users_cannot_touch_each_others_images(self):
        other = self.make_user("other1", "other1@example.com")
        self.upload(self.endpoint, self.image_file())
        self.login(other)
        self.client.delete(self.url(self.endpoint))  # deletes the OTHER user's (empty) image only
        self.assertTrue(getattr(self.profile_of(self.user), self.field))

    def test_other_users_see_the_image_url_on_a_public_profile(self):
        self.upload(self.endpoint, self.image_file())
        self.logout()
        profile = self.client.get(self.detail_url(self.user)).json()["data"]["profile"]
        self.assertTrue(profile[self.field].startswith("http"))


class ProfilePictureTests(ImageTestMixin, ProfileTestCase):
    endpoint = "me-picture"
    field = "profile_picture"

    def test_picture_is_capped_to_1024px(self):
        self.upload(self.endpoint, self.image_file("PNG", size=(2000, 1500)))
        with Image.open(self.current_file().path) as stored:
            self.assertLessEqual(max(stored.size), 1024)

    def test_picture_upload_raises_completion(self):
        response = self.upload(self.endpoint, self.image_file())
        completion = response.json()["data"]["profile"]["profile_completion"]
        self.assertIn("profile_picture", completion["completed_fields"])


class CoverPhotoTests(ImageTestMixin, ProfileTestCase):
    endpoint = "me-cover"
    field = "cover_photo"

    def test_cover_does_not_touch_profile_picture(self):
        self.upload("me-picture", self.image_file())
        self.upload(self.endpoint, self.image_file())
        profile = self.profile_of(self.user)
        self.assertTrue(profile.profile_picture)
        self.assertTrue(profile.cover_photo)
        self.assertNotEqual(profile.profile_picture.name, profile.cover_photo.name)

    def test_cover_does_not_count_for_completion(self):
        response = self.upload(self.endpoint, self.image_file())
        self.assertEqual(response.json()["data"]["profile"]["profile_completion"]["percentage"], 0)
