from django.test import override_settings

from social.models import Post, PostMedia

from .base import SocialTestCase


class PostManagementTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.login(self.alice)

    def test_create_post_assigns_author_and_returns_real_values(self):
        response = self.create_post_api(content="Joined the robotics club!", post_type="activity")
        self.assertEqual(response.status_code, 201, response.content)
        post = self.data(response)["post"]
        self.assertEqual(post["author"]["username"], "alice")
        self.assertEqual(post["author"]["id"], str(self.alice.pk))
        self.assertEqual(post["post_type"], "activity")
        self.assertEqual(post["visibility"], "public")
        self.assertEqual((post["like_count"], post["comment_count"], post["share_count"]), (0, 0, 0))
        self.assertFalse(post["is_liked"])
        self.assertEqual(post["media"], [])
        self.assertTrue(post["created_at"] and post["updated_at"])
        self.assertEqual(Post.objects.get(pk=post["id"]).author, self.alice)

    def test_all_post_types_accepted(self):
        for kind in ("general", "activity", "achievement", "experience"):
            self.assertEqual(self.create_post_api(content="x", post_type=kind).status_code, 201)

    def test_invalid_post_type_and_visibility_rejected(self):
        self.assertError(self.create_post_api(content="x", post_type="video"), 400, "validation_error")
        self.assertError(self.create_post_api(content="x", visibility="everyone"), 400, "validation_error")
        # "friends" is a valid visibility since the Friends integration (see README §5)
        self.assertEqual(self.create_post_api(content="x", visibility="friends").status_code, 201)

    def test_achievement_post_creates_no_other_records(self):
        self.create_post_api(content="Won the debate!", post_type="achievement")
        self.assertEqual(Post.objects.count(), 1)

    def test_reject_empty_post(self):
        for payload in ({}, {"content": ""}, {"content": "    \n  "}):
            self.assertError(self.create_post_api(**payload), 400, "validation_error")
        self.assertEqual(Post.objects.count(), 0)

    def test_reject_invalid_content(self):
        too_long = "a" * 5001
        self.assertError(self.create_post_api(content=too_long), 400, "validation_error")
        for bad in ("<script>alert(1)</script>", "hi <b>there</b>", "<img src=x onerror=alert(1)>",
                    "click javascript:alert(1)", "null\x00byte"):
            body = self.assertError(self.create_post_api(content=bad), 400, "validation_error")
            self.assertIn("content", body["errors"], bad)

    def test_plain_text_with_newlines_and_symbols_is_accepted(self):
        response = self.create_post_api(content="Line one\nLine two :) 5 < 6 & 7 > 3")
        self.assertEqual(response.status_code, 201, response.content)

    def test_edit_own_post(self):
        post = self.make_post(self.alice, "old")
        response = self.client.patch(self.url("post-detail", post_id=post.pk),
                                     {"content": "new", "visibility": "members_only"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        data = self.data(response)["post"]
        self.assertEqual(data["content"], "new")
        self.assertEqual(data["visibility"], "members_only")
        self.assertTrue(data["is_edited"])

    def test_edit_to_empty_text_without_images_rejected(self):
        post = self.make_post(self.alice, "old")
        response = self.client.patch(self.url("post-detail", post_id=post.pk), {"content": ""}, format="json")
        self.assertError(response, 400, "validation_error")

    def test_reject_editing_another_users_post(self):
        post = self.make_post(self.bob, "bob's")
        response = self.client.patch(self.url("post-detail", post_id=post.pk), {"content": "hacked"}, format="json")
        self.assertError(response, 403, "not_owner")
        post.refresh_from_db()
        self.assertEqual(post.content, "bob's")

    def test_delete_own_post_is_soft_and_hidden(self):
        post = self.make_post(self.alice)
        response = self.client.delete(self.url("post-detail", post_id=post.pk))
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)
        self.assertEqual(self.client.get(self.url("post-detail", post_id=post.pk)).status_code, 404)
        self.assertEqual(self.data(self.client.get(self.url("post-list")))["results"], [])

    def test_reject_deleting_another_users_post(self):
        post = self.make_post(self.bob)
        self.assertError(self.client.delete(self.url("post-detail", post_id=post.pk)), 403, "not_owner")
        post.refresh_from_db()
        self.assertFalse(post.is_deleted)

    def test_retrieve_individual_post(self):
        post = self.make_post(self.bob, "details")
        response = self.client.get(self.url("post-detail", post_id=post.pk))
        self.assertEqual(response.status_code, 200)
        data = self.data(response)["post"]
        self.assertEqual(data["id"], str(post.pk))
        self.assertFalse(data["is_owner"])

    def test_missing_post_is_404(self):
        import uuid
        self.assertError(self.client.get(self.url("post-detail", post_id=uuid.uuid4())), 404, "post_not_found")

    def test_cannot_edit_or_delete_an_already_deleted_post(self):
        post = self.make_post(self.alice, is_deleted=True)
        self.assertEqual(self.client.patch(self.url("post-detail", post_id=post.pk), {"content": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(self.url("post-detail", post_id=post.pk)).status_code, 404)


class PostMediaTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.login(self.alice)

    def upload(self, files, **extra):
        data = {"content": "with pictures", "images": files, **extra}
        return self.client.post(self.url("post-list"), data, format="multipart")

    def test_create_post_with_multiple_valid_images(self):
        response = self.upload([self.image_file("JPEG"), self.image_file("PNG"), self.image_file("WEBP")])
        self.assertEqual(response.status_code, 201, response.content)
        media = self.data(response)["post"]["media"]
        self.assertEqual(len(media), 3)
        for item in media:
            self.assertTrue(item["url"].startswith("http"), item["url"])
            self.assertIn("/media/social/posts/", item["url"])
        self.assertEqual(len(self.stored_files()), 3)

    def test_image_only_post_is_valid(self):
        response = self.client.post(self.url("post-list"), {"images": [self.image_file()]}, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)

    def test_stored_name_is_random_and_not_the_client_name(self):
        self.upload([self.image_file(name="../../evil name.png")])
        for path in self.stored_files():
            self.assertNotIn("evil", path)
            self.assertNotIn("..", path)

    def test_reject_invalid_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile("photo.png", b"definitely not an image", "image/png")
        response = self.upload([fake])
        self.assertError(response, 400, "validation_error")
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_reject_unsupported_format(self):
        response = self.upload([self.image_file("GIF")])
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("images", body["errors"])

    def test_script_disguised_as_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile("x.jpg", b"<?php echo 1; ?>", "image/jpeg")
        self.assertError(self.upload([fake]), 400, "validation_error")

    @override_settings(SOCIAL_IMAGE_MAX_BYTES=2000)
    def test_reject_oversized_image(self):
        response = self.upload([self.image_file("PNG", size=(80, 80), noisy=True)])
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("too large", " ".join(body["errors"]["images"]).lower())
        self.assertEqual(self.stored_files(), [])

    @override_settings(SOCIAL_MAX_IMAGES_PER_POST=2)
    def test_reject_too_many_images(self):
        response = self.upload([self.image_file(), self.image_file(), self.image_file()])
        self.assertError(response, 400, "validation_error")
        self.assertEqual(Post.objects.count(), 0)

    def test_one_bad_image_rejects_whole_post_and_leaves_no_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile("b.png", b"nope", "image/png")
        self.assertError(self.upload([self.image_file(), fake]), 400, "validation_error")
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(PostMedia.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_add_images_when_editing_respects_the_limit(self):
        with override_settings(SOCIAL_MAX_IMAGES_PER_POST=2):
            post_id = self.data(self.upload([self.image_file()]))["post"]["id"]
            ok = self.client.patch(self.url("post-detail", post_id=post_id), {"images": [self.image_file()]}, format="multipart")
            self.assertEqual(ok.status_code, 200, ok.content)
            self.assertEqual(len(self.data(ok)["post"]["media"]), 2)
            too_many = self.client.patch(self.url("post-detail", post_id=post_id), {"images": [self.image_file()]}, format="multipart")
            self.assertError(too_many, 400, "validation_error")

    def test_remove_attachment_deletes_file(self):
        post_id = self.data(self.upload([self.image_file(), self.image_file()]))["post"]["id"]
        media = PostMedia.objects.filter(post_id=post_id).first()
        self.assertEqual(len(self.stored_files()), 2)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url("post-media", post_id=post_id, media_id=media.pk))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(self.data(response)["post"]["media"]), 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_cannot_remove_attachment_of_another_users_post(self):
        post_id = self.data(self.upload([self.image_file()]))["post"]["id"]
        media = PostMedia.objects.get(post_id=post_id)
        self.login(self.bob)
        self.assertError(self.client.delete(self.url("post-media", post_id=post_id, media_id=media.pk)), 403, "not_owner")

    def test_cannot_remove_last_image_of_a_post_without_text(self):
        response = self.client.post(self.url("post-list"), {"images": [self.image_file()]}, format="multipart")
        post_id = self.data(response)["post"]["id"]
        media = PostMedia.objects.get(post_id=post_id)
        self.assertError(self.client.delete(self.url("post-media", post_id=post_id, media_id=media.pk)), 400, "validation_error")

    def test_deleting_post_cleans_up_files(self):
        post_id = self.data(self.upload([self.image_file(), self.image_file()]))["post"]["id"]
        self.assertEqual(len(self.stored_files()), 2)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(self.url("post-detail", post_id=post_id)).status_code, 200)
        self.assertEqual(self.stored_files(), [])
        self.assertEqual(PostMedia.objects.count(), 0)

    def test_deleting_user_cleans_up_files(self):
        self.upload([self.image_file()])
        self.assertEqual(len(self.stored_files()), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.alice.delete()
        self.assertEqual(self.stored_files(), [])

    def test_oversized_request_body_is_refused_early(self):
        with override_settings(SOCIAL_IMAGE_MAX_BYTES=1000, SOCIAL_MAX_IMAGES_PER_POST=1):
            response = self.client.post(
                self.url("post-list"), {"content": "x"}, format="multipart", CONTENT_LENGTH=str(10 * 1024 * 1024)
            )
        self.assertError(response, 413, "file_too_large")
