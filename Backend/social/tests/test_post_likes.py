import uuid

from django.db import IntegrityError, transaction

from social.models import PostLike

from .base import SocialTestCase


class PostLikeTests(SocialTestCase):
    def like_url(self, post):
        return self.url("post-like", post_id=post.pk)

    def test_like_and_unlike(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        response = self.client.post(self.like_url(post))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.data(response), {"like_count": 1, "is_liked": True})
        response = self.client.delete(self.like_url(post))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.data(response), {"like_count": 0, "is_liked": False})
        self.assertEqual(PostLike.objects.count(), 0)

    def test_repeated_like_requests_do_not_duplicate(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        self.assertEqual(self.client.post(self.like_url(post)).status_code, 201)
        second = self.client.post(self.like_url(post))
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.data(second)["like_count"], 1)
        self.assertEqual(PostLike.objects.filter(post=post, user=self.bob).count(), 1)

    def test_database_constraint_blocks_duplicate_likes(self):
        post = self.make_post(self.alice)
        PostLike.objects.create(post=post, user=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PostLike.objects.create(post=post, user=self.bob)

    def test_unlike_without_like_is_harmless(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        response = self.client.delete(self.like_url(post))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.data(response)["like_count"], 0)

    def test_counts_are_accurate_with_several_users(self):
        post = self.make_post(self.alice)
        for user in (self.alice, self.bob, self.admin):
            self.login(user)
            self.client.post(self.like_url(post))
        self.login(self.bob)
        self.client.delete(self.like_url(post))
        detail = self.data(self.client.get(self.url("post-detail", post_id=post.pk)))["post"]
        self.assertEqual(detail["like_count"], 2)
        self.assertFalse(detail["is_liked"])

    def test_like_requires_login(self):
        post = self.make_post(self.alice)
        self.assertEqual(self.client.post(self.like_url(post)).status_code, 401)
        self.assertEqual(self.client.delete(self.like_url(post)).status_code, 401)

    def test_cannot_like_inaccessible_deleted_or_missing_posts(self):
        private = self.make_post(self.alice, visibility="private")
        deleted = self.make_post(self.alice, is_deleted=True)
        self.login(self.bob)
        self.assertError(self.client.post(self.like_url(private)), 404, "post_not_found")
        self.assertError(self.client.post(self.like_url(deleted)), 404, "post_not_found")
        self.assertError(self.client.delete(self.like_url(private)), 404, "post_not_found")
        self.assertError(self.client.post(self.url("post-like", post_id=uuid.uuid4())), 404, "post_not_found")
        self.assertEqual(PostLike.objects.count(), 0)

    def test_admin_cannot_like_private_post_of_someone_else(self):
        private = self.make_post(self.alice, visibility="private")
        self.login(self.admin)
        self.assertEqual(self.client.post(self.like_url(private)).status_code, 404)

    def test_owner_can_like_own_private_post(self):
        private = self.make_post(self.alice, visibility="private")
        self.login(self.alice)
        self.assertEqual(self.client.post(self.like_url(private)).status_code, 201)
