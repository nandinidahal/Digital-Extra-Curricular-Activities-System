import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from messaging.models import Message, MessageAttachment

from .base import MessagingTestCase


class AttachmentTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)

    def upload(self, user, files, content=""):
        return self.client_for(user).post(
            self.url("conversation-messages", conversation_id=self.cid),
            {"content": content, "attachments": files}, format="multipart",
        )

    def test_upload_valid_images(self):
        for fmt in ("JPEG", "PNG", "WEBP"):
            response = self.upload(self.alice, [self.image_file(fmt)])
            self.assertEqual(response.status_code, 201, response.content)
            message = self.data(response)["message"]
            self.assertEqual(message["message_type"], "image")
            [att] = message["attachments"]
            self.assertEqual(att["kind"], "image")
            self.assertTrue(att["content_type"].startswith("image/"))
            self.assertEqual((att["width"], att["height"]), (60, 40))
            self.assertIn("?sig=", att["url"])

    def test_upload_valid_pdf_with_caption(self):
        response = self.upload(self.alice, [self.pdf_file("../../etc/My Notes.pdf")], content="see attached")
        self.assertEqual(response.status_code, 201, response.content)
        message = self.data(response)["message"]
        self.assertEqual(message["message_type"], "file")
        self.assertEqual(message["content"], "see attached")
        [att] = message["attachments"]
        self.assertEqual(att["content_type"], "application/pdf")
        self.assertEqual(att["name"], "My_Notes.pdf")  # path stripped, name made safe
        stored = MessageAttachment.objects.get(pk=att["id"])
        self.assertNotIn("Notes", stored.file.name)  # random storage name

    def test_reject_invalid_and_unsupported_files(self):
        bad = [
            SimpleUploadedFile("run.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream"),
            SimpleUploadedFile("shell.php.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg"),
            SimpleUploadedFile("page.html", b"<script>alert(1)</script>", "text/html"),
            SimpleUploadedFile("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
            SimpleUploadedFile("a.zip", b"PK\x03\x04rest", "application/zip"),
            self.image_file("GIF"),
            self.pdf_file(body=b"<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>"),
            self.pdf_file(body=b"<< /Launch /F (cmd.exe) >>"),
            SimpleUploadedFile("cut.pdf", b"%PDF-1.4 no trailer", "application/pdf"),
            SimpleUploadedFile("empty.png", b"", "image/png"),
        ]
        for upload in bad:
            response = self.upload(self.alice, [upload])
            self.assertError(response, 400, "validation_error")
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_reject_oversized(self):
        with override_settings(MESSAGING_IMAGE_MAX_BYTES=100, MESSAGING_FILE_MAX_BYTES=50):
            body = self.assertError(self.upload(self.alice, [self.image_file("PNG")]), 400, "validation_error")
            self.assertIn("too large", body["errors"]["attachments"][0])
            self.assertError(self.upload(self.alice, [self.pdf_file()]), 400, "validation_error")

    def test_too_many_attachments(self):
        with override_settings(MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE=2):
            files = [self.image_file("PNG", name=f"{i}.png") for i in range(3)]
            self.assertError(self.upload(self.alice, files), 400, "validation_error")

    def test_one_bad_file_rejects_whole_message_and_leaves_no_files(self):
        files = [self.image_file("PNG"), SimpleUploadedFile("x.exe", b"MZ....", "application/octet-stream")]
        self.assertError(self.upload(self.alice, files), 400, "validation_error")
        self.assertEqual(self.stored_files(), [])

    def test_exif_metadata_is_stripped(self):
        image = Image.new("RGB", (30, 30))
        exif = image.getexif()
        exif[0x010E] = "GPS SECRET"
        buffer = BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        response = self.upload(self.alice, [SimpleUploadedFile("a.jpg", buffer.getvalue(), "image/jpeg")])
        att = MessageAttachment.objects.get(pk=self.data(response)["message"]["attachments"][0]["id"])
        with att.file.open("rb") as handle, Image.open(handle) as stored:
            self.assertNotIn(0x010E, stored.getexif())

    def test_files_are_stored_privately_outside_media_root(self):
        from django.conf import settings
        response = self.upload(self.alice, [self.image_file("PNG")])
        att = MessageAttachment.objects.get(pk=self.data(response)["message"]["attachments"][0]["id"])
        path = att.file.path
        self.assertTrue(path.startswith(self.private_root))
        self.assertFalse(path.startswith(str(settings.MEDIA_ROOT)))
        self.assertTrue(os.path.exists(path))

    def test_participant_can_download_with_signed_url_and_with_jwt(self):
        response = self.upload(self.alice, [self.pdf_file()])
        att = self.data(response)["message"]["attachments"][0]
        # bob's own signed URL (from his history)
        [m] = self.messages(self.bob, self.cid)
        bob_url = m["attachments"][0]["url"]
        self.logout()
        download = self.client.get(bob_url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertTrue(b"".join(download.streaming_content).startswith(b"%PDF-"))
        jwt = self.client_for(self.alice).get(self.url("attachment-download", attachment_id=att["id"]))
        self.assertEqual(jwt.status_code, 200)

    def test_outsiders_cannot_download(self):
        response = self.upload(self.alice, [self.image_file("PNG")])
        att = self.data(response)["message"]["attachments"][0]
        plain = self.url("attachment-download", attachment_id=att["id"])
        self.assertEqual(self.client.get(plain).status_code, 401)  # anonymous, no signature
        self.assertError(self.client_for(self.carol).get(plain), 404, "attachment_not_found")
        self.assertError(self.client.get(plain + "?sig=forged"), 404, "attachment_not_found")
        # a valid signature for another attachment id is useless
        other = self.data(self.upload(self.alice, [self.image_file("PNG")]))["message"]["attachments"][0]
        sig = other["url"].split("?sig=")[1]
        self.assertError(self.client.get(plain + "?sig=" + sig), 404, "attachment_not_found")

    def test_signed_url_expires(self):
        response = self.upload(self.alice, [self.image_file("PNG")])
        url = self.data(response)["message"]["attachments"][0]["url"]
        with override_settings(MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS=-1):
            self.assertError(self.client.get(url), 404, "attachment_not_found")

    def test_delete_for_everyone_removes_files(self):
        response = self.upload(self.alice, [self.image_file("PNG"), self.pdf_file()])
        message = self.data(response)["message"]
        self.assertEqual(len(self.stored_files()), 2)
        url = message["attachments"][0]["url"]
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=message["id"]))
        self.assertEqual(self.stored_files(), [])
        self.assertEqual(MessageAttachment.objects.count(), 0)
        self.assertError(self.client.get(url), 404, "attachment_not_found")

    def test_hidden_message_attachment_not_downloadable_by_that_user(self):
        response = self.upload(self.alice, [self.image_file("PNG")])
        message = self.data(response)["message"]
        [m] = self.messages(self.bob, self.cid)
        self.client_for(self.bob).post(self.url("message-delete-for-me", message_id=message["id"]))
        self.assertError(self.client.get(m["attachments"][0]["url"]), 404, "attachment_not_found")

    def test_json_body_cannot_smuggle_attachments(self):
        response = self.client_for(self.alice).post(
            self.url("conversation-messages", conversation_id=self.cid),
            {"content": "x", "attachments": ["aGVsbG8="]}, format="json",
        )
        self.assertError(response, 400, "validation_error")

    def test_forward_copies_attachment_file(self):
        self.befriend(self.alice, self.carol)
        response = self.upload(self.alice, [self.pdf_file()])
        message = self.data(response)["message"]
        forwarded = self.data(self.client_for(self.alice).post(
            self.url("message-forward", message_id=message["id"]), {"user_id": str(self.carol.pk)}, format="json"
        ))["message"]
        self.assertEqual(len(forwarded["attachments"]), 1)
        self.assertNotEqual(forwarded["attachments"][0]["id"], message["attachments"][0]["id"])
        self.assertEqual(len(self.stored_files()), 2)
