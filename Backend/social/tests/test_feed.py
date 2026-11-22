from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext

from social.models import Comment, CommentLike, PostLike, PostShare

from .base import SocialTestCase


class FeedTests(SocialTestCase):
    feed = property(lambda self: self.url("post-list"))

    def results(self, response):
        return self.data(response)["results"]

    def test_visitor_sees_only_public_posts(self):
        public = self.make_post(self.alice, "public", "public")
        self.make_post(self.alice, "members", "members_only")
        self.make_post(self.alice, "private", "private")
        response = self.client.get(self.feed)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in self.results(response)], [str(public.pk)])

    def test_authenticated_user_sees_public_and_members_only_but_not_others_private(self):
        self.make_post(self.alice, "public", "public")
        self.make_post(self.alice, "members", "members_only")
        self.make_post(self.alice, "alice private", "private")
        mine = self.make_post(self.bob, "bob private", "private")
        self.login(self.bob)
        contents = {p["content"] for p in self.results(self.client.get(self.feed))}
        self.assertEqual(contents, {"public", "members", "bob private"})
        self.assertNotIn("alice private", contents)
        self.assertIn(str(mine.pk), {p["id"] for p in self.results(self.client.get(self.feed))})

    def test_admin_does_not_see_others_private_posts_in_the_feed(self):
        self.make_post(self.alice, "alice private", "private")
        self.login(self.admin)
        self.assertEqual(self.results(self.client.get(self.feed)), [])

    def test_deleted_posts_and_inactive_authors_are_excluded(self):
        self.make_post(self.alice, "gone", is_deleted=True)
        ghost = self.make_user("ghost", "ghost@example.com")
        self.make_post(ghost, "from inactive user")
        ghost.is_active = False
        ghost.save()
        keep = self.make_post(self.bob, "kept")
        self.assertEqual([p["id"] for p in self.results(self.client.get(self.feed))], [str(keep.pk)])

    def test_ordering_is_newest_first(self):
        now = self.now()
        oldest = self.make_post(self.alice, "oldest")
        middle = self.make_post(self.alice, "middle")
        newest = self.make_post(self.alice, "newest")
        self.set_created(oldest, now - timedelta(days=2))
        self.set_created(middle, now - timedelta(days=1))
        self.set_created(newest, now)
        ids = [p["id"] for p in self.results(self.client.get(self.feed))]
        self.assertEqual(ids, [str(newest.pk), str(middle.pk), str(oldest.pk)])

    def test_pagination_shape_and_pages(self):
        now = self.now()
        for i in range(12):
            post = self.make_post(self.alice, f"post {i}")
            self.set_created(post, now - timedelta(minutes=i))
        first = self.data(self.client.get(self.feed))
        self.assertEqual(len(first["results"]), 10)
        pagination = first["pagination"]
        self.assertEqual(pagination["count"], 12)
        self.assertEqual(pagination["page"], 1)
        self.assertEqual(pagination["page_size"], 10)
        self.assertEqual(pagination["total_pages"], 2)
        self.assertIsNotNone(pagination["next"])
        self.assertIsNone(pagination["previous"])
        second = self.data(self.client.get(self.feed, {"page": 2}))
        self.assertEqual(len(second["results"]), 2)
        self.assertIsNone(second["pagination"]["next"])
        small = self.data(self.client.get(self.feed, {"page_size": 5}))
        self.assertEqual(len(small["results"]), 5)
        capped = self.data(self.client.get(self.feed, {"page_size": 1000}))
        self.assertEqual(capped["pagination"]["page_size"], 50)
        self.assertEqual(self.client.get(self.feed, {"page": 99}).status_code, 404)

    def test_feed_alias_endpoint(self):
        self.make_post(self.alice)
        self.assertEqual(len(self.results(self.client.get(self.url("feed")))), 1)

    def test_post_type_filter(self):
        self.make_post(self.alice, "a", post_type="activity")
        self.make_post(self.alice, "b", post_type="general")
        results = self.results(self.client.get(self.feed, {"post_type": "activity"}))
        self.assertEqual([p["content"] for p in results], ["a"])

    def test_counts_and_is_liked_are_computed_from_real_data(self):
        post = self.make_post(self.alice)
        PostLike.objects.create(post=post, user=self.alice)
        PostLike.objects.create(post=post, user=self.bob)
        self.make_comment(post, self.bob)
        gone = self.make_comment(post, self.bob, "deleted")
        Comment.objects.filter(pk=gone.pk).update(is_deleted=True)
        PostShare.objects.create(original_post=post, user=self.bob)
        self.login(self.bob)
        item = self.results(self.client.get(self.feed))[0]
        self.assertEqual((item["like_count"], item["comment_count"], item["share_count"]), (2, 1, 1))
        self.assertTrue(item["is_liked"])
        self.logout()
        item = self.results(self.client.get(self.feed))[0]
        self.assertFalse(item["is_liked"])

    def test_author_info_and_profile_picture_field_present(self):
        self.make_post(self.alice)
        author = self.results(self.client.get(self.feed))[0]["author"]
        self.assertEqual(set(author), {"id", "username", "full_name", "profile_picture"})
        self.assertEqual(author["full_name"], "Alice Student")

    def test_my_posts_includes_all_visibilities_but_not_deleted(self):
        self.make_post(self.alice, "p", "public")
        self.make_post(self.alice, "m", "members_only")
        self.make_post(self.alice, "x", "private")
        self.make_post(self.alice, "d", is_deleted=True)
        self.make_post(self.bob, "bob")
        self.login(self.alice)
        contents = {p["content"] for p in self.results(self.client.get(self.url("my-posts")))}
        self.assertEqual(contents, {"p", "m", "x"})

    def test_my_posts_requires_login(self):
        self.assertEqual(self.client.get(self.url("my-posts")).status_code, 401)

    def test_user_posts_respect_visibility(self):
        self.make_post(self.alice, "p", "public")
        self.make_post(self.alice, "m", "members_only")
        self.make_post(self.alice, "x", "private")
        url = self.url("user-posts", user_id=self.alice.pk)
        self.assertEqual({p["content"] for p in self.results(self.client.get(url))}, {"p"})
        self.login(self.bob)
        self.assertEqual({p["content"] for p in self.results(self.client.get(url))}, {"p", "m"})
        self.login(self.alice)
        self.assertEqual({p["content"] for p in self.results(self.client.get(url))}, {"p", "m", "x"})
        self.login(self.admin)
        self.assertEqual({p["content"] for p in self.results(self.client.get(url))}, {"p", "m", "x"})

    def test_user_posts_unknown_user_is_404(self):
        import uuid
        self.assertError(self.client.get(self.url("user-posts", user_id=uuid.uuid4())), 404, "user_not_found")

    def test_feed_query_count_does_not_grow_with_page_size(self):
        """No N+1: 3 posts and 9 posts (with media-less rows, comments and likes) cost the same."""
        def seed(n):
            for i in range(n):
                post = self.make_post(self.alice, f"p{i}")
                PostLike.objects.create(post=post, user=self.bob)
                comment = self.make_comment(post, self.bob)
                CommentLike.objects.create(comment=comment, user=self.alice)

        def count_queries():
            self.login(self.bob)
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(self.feed)
            self.assertEqual(response.status_code, 200)
            return len(ctx), len(self.results(response))

        seed(3)
        small_queries, small_n = count_queries()
        seed(6)
        big_queries, big_n = count_queries()
        self.assertEqual((small_n, big_n), (3, 9))
        self.assertEqual(small_queries, big_queries)

    def test_comment_list_query_count_is_constant(self):
        post = self.make_post(self.alice)

        def count_queries():
            self.login(self.bob)
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(self.url("post-comments", post_id=post.pk))
            self.assertEqual(response.status_code, 200)
            return len(ctx)

        for _ in range(2):
            self.make_comment(post, self.alice)
        few = count_queries()
        for _ in range(6):
            self.make_comment(post, self.bob)
        self.assertEqual(few, count_queries())
