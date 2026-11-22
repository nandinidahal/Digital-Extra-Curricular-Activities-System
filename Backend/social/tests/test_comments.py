import uuid

from social.models import MAX_COMMENT_DEPTH, Comment

from .base import SocialTestCase


class CommentTests(SocialTestCase):
    def comments_url(self, post):
        return self.url("post-comments", post_id=post.pk)

    def detail_url(self, comment):
        return self.url("comment-detail", comment_id=comment.pk)

    def reply_url(self, comment):
        return self.url("comment-reply", comment_id=comment.pk)

    def test_create_comment(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        response = self.client.post(self.comments_url(post), {"content": "Great job!"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        comment = self.data(response)["comment"]
        self.assertEqual(comment["content"], "Great job!")
        self.assertEqual(comment["author"]["username"], "bob")
        self.assertEqual(comment["depth"], 0)
        self.assertIsNone(comment["parent_comment_id"])
        self.assertEqual((comment["like_count"], comment["reply_count"]), (0, 0))
        self.assertTrue(comment["created_at"])

    def test_reject_empty_and_invalid_comments(self):
        post = self.make_post(self.alice)
        self.login(self.bob)
        for payload in ({}, {"content": ""}, {"content": "   "}, {"content": "a" * 2001},
                        {"content": "<script>x</script>"}, {"content": None}):
            self.assertError(self.client.post(self.comments_url(post), payload, format="json"), 400, "validation_error")
        self.assertEqual(Comment.objects.count(), 0)

    def test_edit_own_comment(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob, "old")
        self.login(self.bob)
        response = self.client.patch(self.detail_url(comment), {"content": "new"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        data = self.data(response)["comment"]
        self.assertEqual(data["content"], "new")
        self.assertTrue(data["is_edited"])

    def test_reject_editing_another_users_comment(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob, "bob's")
        self.login(self.alice)  # even the post owner may not edit it
        self.assertError(self.client.patch(self.detail_url(comment), {"content": "x"}, format="json"), 403, "not_owner")
        comment.refresh_from_db()
        self.assertEqual(comment.content, "bob's")

    def test_delete_own_comment_is_soft(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob)
        self.login(self.bob)
        self.assertEqual(self.client.delete(self.detail_url(comment)).status_code, 200)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
        self.assertEqual(self.data(self.client.get(self.comments_url(post)))["results"], [])

    def test_reject_deleting_another_users_comment(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob)
        self.login(self.alice)
        self.assertError(self.client.delete(self.detail_url(comment)), 403, "not_owner")
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)

    def test_deleted_comment_cannot_be_edited_deleted_again_or_replied_to(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob)
        Comment.objects.filter(pk=comment.pk).update(is_deleted=True)
        self.login(self.bob)
        self.assertEqual(self.client.patch(self.detail_url(comment), {"content": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(self.detail_url(comment)).status_code, 404)
        self.assertEqual(self.client.post(self.reply_url(comment), {"content": "x"}, format="json").status_code, 404)

    def test_reply_to_comment(self):
        post = self.make_post(self.alice)
        parent = self.make_comment(post, self.alice, "question?")
        self.login(self.bob)
        response = self.client.post(self.reply_url(parent), {"content": "answer"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        reply = self.data(response)["comment"]
        self.assertEqual(reply["parent_comment_id"], str(parent.pk))
        self.assertEqual(reply["depth"], 1)
        self.assertEqual(reply["post_id"], str(post.pk))

    def test_nesting_depth_is_enforced(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.alice)
        self.login(self.bob)
        for level in range(1, MAX_COMMENT_DEPTH + 1):
            response = self.client.post(self.reply_url(comment), {"content": f"level {level}"}, format="json")
            self.assertEqual(response.status_code, 201, response.content)
            comment = Comment.objects.get(pk=self.data(response)["comment"]["id"])
            self.assertEqual(comment.depth, level)
        too_deep = self.client.post(self.reply_url(comment), {"content": "too deep"}, format="json")
        self.assertError(too_deep, 400, "max_depth_reached")

    def test_list_returns_top_level_only_with_reply_counts_oldest_first(self):
        post = self.make_post(self.alice)
        first = self.make_comment(post, self.alice, "first")
        second = self.make_comment(post, self.bob, "second")
        self.make_comment(post, self.bob, "reply 1", parent=first)
        self.make_comment(post, self.alice, "reply 2", parent=first)
        gone = self.make_comment(post, self.alice, "deleted reply", parent=first)
        Comment.objects.filter(pk=gone.pk).update(is_deleted=True)
        results = self.data(self.client.get(self.comments_url(post)))["results"]
        self.assertEqual([c["content"] for c in results], ["first", "second"])
        self.assertEqual([c["reply_count"] for c in results], [2, 0])
        self.assertEqual(results[0]["author"]["username"], "alice")
        self.assertIn("profile_picture", results[0]["author"])

    def test_replies_endpoint_is_paginated_and_ordered(self):
        post = self.make_post(self.alice)
        parent = self.make_comment(post, self.alice)
        for i in range(12):
            self.make_comment(post, self.bob, f"r{i}", parent=parent)
        data = self.data(self.client.get(self.url("comment-replies", comment_id=parent.pk)))
        self.assertEqual(len(data["results"]), 10)
        self.assertEqual(data["pagination"]["count"], 12)
        self.assertEqual(data["results"][0]["content"], "r0")

    def test_comment_list_pagination(self):
        post = self.make_post(self.alice)
        for i in range(11):
            self.make_comment(post, self.bob, f"c{i}")
        data = self.data(self.client.get(self.comments_url(post)))
        self.assertEqual((len(data["results"]), data["pagination"]["total_pages"]), (10, 2))

    def test_deleted_parent_with_replies_stays_as_placeholder(self):
        post = self.make_post(self.alice)
        parent = self.make_comment(post, self.bob, "secret text")
        self.make_comment(post, self.alice, "still here", parent=parent)
        self.login(self.bob)
        self.client.delete(self.detail_url(parent))
        results = self.data(self.client.get(self.comments_url(post)))["results"]
        self.assertEqual(len(results), 1)
        placeholder = results[0]
        self.assertTrue(placeholder["is_deleted"])
        self.assertEqual(placeholder["content"], "")
        self.assertIsNone(placeholder["author"])
        self.assertEqual(placeholder["reply_count"], 1)
        replies = self.data(self.client.get(self.url("comment-replies", comment_id=parent.pk)))["results"]
        self.assertEqual([r["content"] for r in replies], ["still here"])

    def test_comment_count_on_post(self):
        post = self.make_post(self.alice)
        top = self.make_comment(post, self.bob)
        self.make_comment(post, self.alice, parent=top)
        gone = self.make_comment(post, self.bob, "gone")
        Comment.objects.filter(pk=gone.pk).update(is_deleted=True)
        detail = self.data(self.client.get(self.url("post-detail", post_id=post.pk)))["post"]
        self.assertEqual(detail["comment_count"], 2)

    def test_comment_requires_login(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.alice)
        self.assertEqual(self.client.post(self.comments_url(post), {"content": "x"}, format="json").status_code, 401)
        self.assertEqual(self.client.patch(self.detail_url(comment), {"content": "x"}, format="json").status_code, 401)
        self.assertEqual(self.client.delete(self.detail_url(comment)).status_code, 401)
        self.assertEqual(self.client.post(self.reply_url(comment), {"content": "x"}, format="json").status_code, 401)

    def test_cannot_comment_on_inaccessible_or_missing_posts(self):
        private = self.make_post(self.alice, visibility="private")
        self.login(self.bob)
        self.assertEqual(self.client.post(self.comments_url(private), {"content": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.get(self.comments_url(private)).status_code, 404)
        missing = self.url("post-comments", post_id=uuid.uuid4())
        self.assertEqual(self.client.post(missing, {"content": "x"}, format="json").status_code, 404)

    def test_comments_of_private_post_hidden_after_post_becomes_private(self):
        post = self.make_post(self.alice)
        comment = self.make_comment(post, self.bob)
        post.visibility = "private"
        post.save()
        self.login(self.bob)
        self.assertEqual(self.client.patch(self.detail_url(comment), {"content": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.get(self.url("comment-replies", comment_id=comment.pk)).status_code, 404)

    def test_members_only_comments_need_login(self):
        post = self.make_post(self.alice, visibility="members_only")
        self.assertError(self.client.get(self.comments_url(post)), 401, "authentication_required")
        self.login(self.bob)
        self.assertEqual(self.client.get(self.comments_url(post)).status_code, 200)

    def test_public_comments_readable_by_visitors(self):
        post = self.make_post(self.alice)
        self.make_comment(post, self.bob)
        self.assertEqual(len(self.data(self.client.get(self.comments_url(post)))["results"]), 1)
