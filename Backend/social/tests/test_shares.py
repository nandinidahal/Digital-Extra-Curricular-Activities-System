import uuid

from django.db import IntegrityError, transaction

from social.models import Post, PostShare

from .base import SocialTestCase


class ShareTests(SocialTestCase):
    def share_url(self, post):
        return self.url("post-share", post_id=post.pk)

    def test_share_a_post(self):
        post = self.make_post(self.alice, "original content")
        self.login(self.bob)
        response = self.client.post(self.share_url(post), {}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        share = self.data(response)["share"]
        self.assertEqual(share["caption"], "")
        self.assertEqual(share["share_count"], 1)
        self.assertEqual(share["original_post"]["author"]["username"], "alice")  # attribution kept
        self.assertEqual(Post.objects.count(), 1)  # nothing duplicated
        self.assertEqual(PostShare.objects.get().user, self.bob)

    def test_share_with_caption(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        response = self.client.post(self.share_url(post), {"caption": "Look at this!"}, format="json")
        self.assertEqual(self.data(response)["share"]["caption"], "Look at this!")

    def test_invalid_caption_rejected(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        for caption in ("x" * 501, "<b>hi</b>"):
            self.assertError(self.client.post(self.share_url(post), {"caption": caption}, format="json"), 400, "validation_error")

    def test_cannot_share_twice(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        self.client.post(self.share_url(post), {}, format="json")
        self.assertError(self.client.post(self.share_url(post), {}, format="json"), 409, "already_shared")
        self.assertEqual(PostShare.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PostShare.objects.create(original_post=post, user=self.bob)

    def test_share_count_on_post(self):
        post = self.make_post(self.alice)
        for user in (self.alice, self.bob):
            self.login(user)
            self.client.post(self.share_url(post), {}, format="json")
        detail = self.data(self.client.get(self.url("post-detail", post_id=post.pk)))["post"]
        self.assertEqual(detail["share_count"], 2)

    def test_remove_own_share(self):
        post = self.make_post(self.alice)
        share = PostShare.objects.create(original_post=post, user=self.bob)
        self.login(self.bob)
        self.assertEqual(self.client.delete(self.url("share-detail", share_id=share.pk)).status_code, 200)
        self.assertEqual(PostShare.objects.count(), 0)
        self.assertEqual(self.data(self.client.get(self.url("post-detail", post_id=post.pk)))["post"]["share_count"], 0)

    def test_reject_removing_another_users_share(self):
        post = self.make_post(self.alice)
        share = PostShare.objects.create(original_post=post, user=self.bob)
        self.login(self.alice)
        self.assertError(self.client.delete(self.url("share-detail", share_id=share.pk)), 403, "not_owner")
        self.assertEqual(PostShare.objects.count(), 1)

    def test_remove_missing_share_is_404(self):
        self.login(self.bob)
        self.assertError(self.client.delete(self.url("share-detail", share_id=uuid.uuid4())), 404, "share_not_found")

    def test_reject_sharing_inaccessible_deleted_or_private_posts(self):
        private = self.make_post(self.alice, visibility="private")
        deleted = self.make_post(self.alice, is_deleted=True)
        self.login(self.bob)
        self.assertError(self.client.post(self.share_url(private), {}, format="json"), 404, "post_not_found")
        self.assertError(self.client.post(self.share_url(deleted), {}, format="json"), 404, "post_not_found")
        # even the owner cannot share a private post
        self.login(self.alice)
        self.assertError(self.client.post(self.share_url(private), {}, format="json"), 400, "post_not_shareable")
        self.assertEqual(PostShare.objects.count(), 0)

    def test_members_only_post_can_be_shared_by_members_not_visitors(self):
        post = self.make_post(self.alice, visibility="members_only")
        self.assertEqual(self.client.post(self.share_url(post), {}, format="json").status_code, 401)
        self.login(self.bob)
        self.assertEqual(self.client.post(self.share_url(post), {}, format="json").status_code, 201)

    def test_my_shares_lists_only_own_shares_with_originals(self):
        post = self.make_post(self.alice, "orig")
        other = self.make_post(self.alice, "other")
        PostShare.objects.create(original_post=post, user=self.bob, share_caption="mine")
        PostShare.objects.create(original_post=other, user=self.alice)
        self.login(self.bob)
        results = self.data(self.client.get(self.url("my-shares")))["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["caption"], "mine")
        self.assertTrue(results[0]["original_post_available"])
        self.assertEqual(results[0]["original_post"]["content"], "orig")
        self.assertEqual(results[0]["original_post"]["author"]["username"], "alice")

    def test_my_shares_hides_originals_that_are_gone_or_became_private(self):
        gone = self.make_post(self.alice, "gone")
        hidden = self.make_post(self.alice, "hidden")
        PostShare.objects.create(original_post=gone, user=self.bob)
        PostShare.objects.create(original_post=hidden, user=self.bob)
        Post.objects.filter(pk=gone.pk).update(is_deleted=True)
        Post.objects.filter(pk=hidden.pk).update(visibility="private")
        self.login(self.bob)
        results = self.data(self.client.get(self.url("my-shares")))["results"]
        self.assertEqual(len(results), 2)
        for item in results:
            self.assertFalse(item["original_post_available"])
            self.assertIsNone(item["original_post"])

    def test_my_shares_requires_login_and_is_paginated(self):
        self.assertEqual(self.client.get(self.url("my-shares")).status_code, 401)
        self.login(self.bob)
        for i in range(11):
            PostShare.objects.create(original_post=self.make_post(self.alice, f"p{i}"), user=self.bob)
        data = self.data(self.client.get(self.url("my-shares")))
        self.assertEqual((len(data["results"]), data["pagination"]["count"]), (10, 11))

    def test_shares_cannot_recurse(self):
        """A share is not a post, so there is no endpoint that could share a share."""
        post = self.make_post(self.alice)
        share = PostShare.objects.create(original_post=post, user=self.bob)
        self.login(self.alice)
        self.assertEqual(self.client.post(self.url("post-share", post_id=share.pk), {}, format="json").status_code, 404)
