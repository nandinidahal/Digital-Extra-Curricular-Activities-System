import uuid

from django.test import override_settings

from social.models import Comment, Post

from .base import SocialTestCase


class SecurityTests(SocialTestCase):
    def test_unauthenticated_write_requests_are_rejected(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.alice)
        pid, cid = post.pk, comment.pk
        requests = [
            ("post", self.url("post-list"), {"content": "x"}),
            ("patch", self.url("post-detail", post_id=pid), {"content": "x"}),
            ("delete", self.url("post-detail", post_id=pid), None),
            ("post", self.url("post-like", post_id=pid), None),
            ("delete", self.url("post-like", post_id=pid), None),
            ("post", self.url("post-comments", post_id=pid), {"content": "x"}),
            ("patch", self.url("comment-detail", comment_id=cid), {"content": "x"}),
            ("delete", self.url("comment-detail", comment_id=cid), None),
            ("post", self.url("comment-reply", comment_id=cid), {"content": "x"}),
            ("post", self.url("comment-like", comment_id=cid), None),
            ("delete", self.url("comment-like", comment_id=cid), None),
            ("post", self.url("post-share", post_id=pid), {}),
            ("delete", self.url("share-detail", share_id=uuid.uuid4()), None),
            ("post", self.url("post-report", post_id=pid), {"reason": "spam"}),
            ("post", self.url("comment-report", comment_id=cid), {"reason": "spam"}),
            ("get", self.url("my-posts"), None),
            ("get", self.url("my-shares"), None),
        ]
        for method, url, payload in requests:
            kwargs = {"format": "json"} if payload is not None else {}
            args = (url, payload) if payload is not None else (url,)
            response = getattr(self.client, method)(*args, **kwargs)
            self.assertEqual(response.status_code, 401, f"{method.upper()} {url} -> {response.status_code}")
            self.assertFalse(response.json()["success"])
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 1)

    def test_author_cannot_be_impersonated_on_create(self):
        self.login(self.alice)
        for key in ("author", "author_id", "user", "user_id"):
            response = self.create_post_api(content="forged", **{key: str(self.bob.pk)})
            self.assertError(response, 400, "validation_error")
        self.assertEqual(Post.objects.count(), 0)
        post = self.data(self.create_post_api(content="real"))["post"]
        self.assertEqual(Post.objects.get(pk=post["id"]).author, self.alice)

    def test_author_cannot_be_changed_on_edit(self):
        post = self.make_post(self.alice)
        self.login(self.alice)
        response = self.client.patch(self.url("post-detail", post_id=post.pk), {"author": str(self.bob.pk)}, format="json")
        self.assertError(response, 400, "validation_error")
        post.refresh_from_db()
        self.assertEqual(post.author, self.alice)

    def test_read_only_and_counter_fields_cannot_be_written(self):
        self.login(self.alice)
        for key, value in (("like_count", 999), ("is_deleted", True), ("is_edited", True), ("id", str(uuid.uuid4())),
                           ("created_at", "2000-01-01T00:00:00Z"), ("media", [])):
            self.assertError(self.create_post_api(content="x", **{key: value}), 400, "validation_error")

    def test_comment_author_cannot_be_forged(self):
        post = self.make_post(self.alice)
        self.login(self.alice)
        response = self.client.post(self.url("post-comments", post_id=post.pk), {"content": "x", "author": str(self.bob.pk)}, format="json")
        self.assertError(response, 400, "validation_error")

    def test_ownership_is_enforced_for_every_modification(self):
        post = self.make_post(self.bob, "bob post")
        comment = self.make_comment(post, self.bob, "bob comment")
        self.login(self.alice)
        self.assertEqual(self.client.patch(self.url("post-detail", post_id=post.pk), {"content": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(self.url("post-detail", post_id=post.pk)).status_code, 403)
        self.assertEqual(self.client.patch(self.url("comment-detail", comment_id=comment.pk), {"content": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(self.url("comment-detail", comment_id=comment.pk)).status_code, 403)

    def test_admin_role_gets_no_write_override_on_other_users_content(self):
        post = self.make_post(self.bob)
        self.login(self.admin)
        self.assertEqual(self.client.patch(self.url("post-detail", post_id=post.pk), {"content": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(self.url("post-detail", post_id=post.pk)).status_code, 403)

    def test_error_responses_use_the_project_error_shape(self):
        body = self.client.post(self.url("post-list"), {"content": "x"}, format="json").json()
        self.assertEqual(set(body), {"success", "message", "code", "errors"})
        self.login(self.alice)
        body = self.create_post_api(content="").json()
        self.assertEqual(body["code"], "validation_error")
        self.assertIn("content", body["errors"])

    def test_non_json_garbage_body_is_a_400_not_a_500(self):
        self.login(self.alice)
        response = self.client.post(self.url("post-list"), data="[1, 2]", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_sql_like_and_unicode_content_is_stored_safely(self):
        self.login(self.alice)
        text = "Robert'); DROP TABLE social_post;-- \u2603 \U0001F600 \u0928\u092e\u0938\u094d\u0924\u0947"
        response = self.create_post_api(content=text)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.data(response)["post"]["content"], text)


class ThrottleTests(SocialTestCase):
    @override_settings(SOCIAL_THROTTLE_RATES={"social_post": "2/min", "social_comment": "2/min",
                                              "social_interaction": "2/min", "social_report": "1/min"})
    def test_content_creation_and_reporting_are_rate_limited(self):
        self.login(self.alice)
        self.assertEqual(self.create_post_api(content="1").status_code, 201)
        self.assertEqual(self.create_post_api(content="2").status_code, 201)
        body = self.assertError(self.create_post_api(content="3"), 429, "throttled")
        self.assertIn("retry_after", body)
        # reading is never throttled
        for _ in range(5):
            self.assertEqual(self.client.get(self.url("post-list")).status_code, 200)
        # deleting is never throttled
        post = self.make_post(self.alice)
        self.assertEqual(self.client.delete(self.url("post-detail", post_id=post.pk)).status_code, 200)

        self.login(self.bob)
        target = self.make_post(self.alice)
        self.assertEqual(self.client.post(self.url("post-report", post_id=target.pk), {"reason": "spam"}, format="json").status_code, 201)
        other = self.make_post(self.alice)
        self.assertEqual(self.client.post(self.url("post-report", post_id=other.pk), {"reason": "spam"}, format="json").status_code, 429)
