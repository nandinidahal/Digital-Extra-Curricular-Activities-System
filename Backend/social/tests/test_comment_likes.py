from django.db import IntegrityError, transaction

from social.models import Comment, CommentLike

from .base import SocialTestCase


class CommentLikeTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.alice)
        self.comment = self.make_comment(self.post, self.alice)
        self.url_ = self.url("comment-like", comment_id=self.comment.pk)

    def test_like_and_unlike(self):
        self.login(self.bob)
        response = self.client.post(self.url_)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.data(response), {"like_count": 1, "is_liked": True})
        response = self.client.delete(self.url_)
        self.assertEqual(self.data(response), {"like_count": 0, "is_liked": False})

    def test_duplicate_like_prevented(self):
        self.login(self.bob)
        self.client.post(self.url_)
        second = self.client.post(self.url_)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CommentLike.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CommentLike.objects.create(comment=self.comment, user=self.bob)

    def test_counts_visible_in_comment_list(self):
        for user in (self.alice, self.bob):
            self.login(user)
            self.client.post(self.url_)
        results = self.data(self.client.get(self.url("post-comments", post_id=self.post.pk)))["results"]
        self.assertEqual(results[0]["like_count"], 2)
        self.assertTrue(results[0]["is_liked"])
        self.logout()
        results = self.data(self.client.get(self.url("post-comments", post_id=self.post.pk)))["results"]
        self.assertFalse(results[0]["is_liked"])

    def test_requires_login(self):
        self.assertEqual(self.client.post(self.url_).status_code, 401)
        self.assertEqual(self.client.delete(self.url_).status_code, 401)

    def test_cannot_like_deleted_or_inaccessible_comment(self):
        self.login(self.bob)
        Comment.objects.filter(pk=self.comment.pk).update(is_deleted=True)
        self.assertError(self.client.post(self.url_), 404, "comment_not_found")
        Comment.objects.filter(pk=self.comment.pk).update(is_deleted=False)
        self.post.visibility = "private"
        self.post.save()
        self.assertError(self.client.post(self.url_), 404, "comment_not_found")
        self.assertEqual(CommentLike.objects.count(), 0)
