import uuid

from .base import SocialTestCase


class VisibilityTests(SocialTestCase):
    """The same rules for detail, comments, likes, shares, reports and feeds."""

    def setUp(self):
        super().setUp()
        self.public = self.make_post(self.alice, "public", "public")
        self.members = self.make_post(self.alice, "members", "members_only")
        self.private = self.make_post(self.alice, "private", "private")

    def detail(self, post):
        return self.client.get(self.url("post-detail", post_id=post.pk))

    def test_visitor(self):
        self.assertEqual(self.detail(self.public).status_code, 200)
        self.assertError(self.detail(self.members), 401, "authentication_required")
        self.assertError(self.detail(self.private), 404, "post_not_found")

    def test_other_member(self):
        self.login(self.bob)
        self.assertEqual(self.detail(self.public).status_code, 200)
        self.assertEqual(self.detail(self.members).status_code, 200)
        self.assertError(self.detail(self.private), 404, "post_not_found")

    def test_owner_sees_everything(self):
        self.login(self.alice)
        for post in (self.public, self.members, self.private):
            self.assertEqual(self.detail(post).status_code, 200)

    def test_admin_can_read_private_posts_for_moderation(self):
        self.login(self.admin)
        self.assertEqual(self.detail(self.private).status_code, 200)

    def test_private_content_never_leaks_in_any_listing(self):
        self.login(self.bob)
        for name, kwargs in (("post-list", {}), ("feed", {}), ("user-posts", {"user_id": self.alice.pk})):
            body = self.client.get(self.url(name, **kwargs)).content.decode()
            self.assertNotIn(str(self.private.pk), body)
            self.assertNotIn('"private"', body)

    def test_private_post_blocks_every_interaction_for_others(self):
        self.login(self.bob)
        pid = self.private.pk
        responses = [
            self.client.post(self.url("post-like", post_id=pid)),
            self.client.delete(self.url("post-like", post_id=pid)),
            self.client.get(self.url("post-comments", post_id=pid)),
            self.client.post(self.url("post-comments", post_id=pid), {"content": "x"}, format="json"),
            self.client.post(self.url("post-share", post_id=pid), {}, format="json"),
            self.client.post(self.url("post-report", post_id=pid), {"reason": "spam"}, format="json"),
            self.client.patch(self.url("post-detail", post_id=pid), {"content": "x"}, format="json"),
            self.client.delete(self.url("post-detail", post_id=pid)),
        ]
        self.assertEqual([r.status_code for r in responses], [404] * len(responses))

    def test_members_only_post_blocks_visitor_interactions(self):
        pid = self.members.pk
        responses = [
            self.client.post(self.url("post-like", post_id=pid)),
            self.client.get(self.url("post-comments", post_id=pid)),
            self.client.post(self.url("post-comments", post_id=pid), {"content": "x"}, format="json"),
        ]
        self.assertEqual([r.status_code for r in responses], [401] * 3)

    def test_changing_visibility_takes_effect_immediately(self):
        self.login(self.alice)
        self.client.patch(self.url("post-detail", post_id=self.public.pk), {"visibility": "private"}, format="json")
        self.logout()
        self.assertEqual(self.detail(self.public).status_code, 404)
        self.assertNotIn(str(self.public.pk), self.client.get(self.url("post-list")).content.decode())

    def test_inactive_author_content_is_unavailable(self):
        self.alice.is_active = False
        self.alice.save()
        self.assertEqual(self.detail(self.public).status_code, 404)

    def test_stale_or_invalid_token_is_treated_as_visitor_on_reads(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(self.detail(self.public).status_code, 200)
        self.assertEqual(self.client.get(self.url("post-list")).status_code, 200)
        self.assertEqual(self.client.post(self.url("post-like", post_id=self.public.pk)).status_code, 401)

    def test_unknown_user_for_visibility_lookups(self):
        self.assertEqual(self.client.get(self.url("user-posts", user_id=uuid.uuid4())).status_code, 404)
