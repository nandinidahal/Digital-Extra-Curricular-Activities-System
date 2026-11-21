from django.utils import timezone

from accounts.models import User
from friends.models import Block
from achievements.models import Achievement, AchievementCategory
from social.models import Notification, Post

from .helpers import ApiTestCase, make_friends, make_user, png


class PostPrivacyTests(ApiTestCase):
    def test_create_text_post_and_default_visibility_is_friends(self):
        r = self.a.post("/api/social/posts/", {"caption": "My first post"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["visibility"], "friends")
        self.assertEqual(r.data["kind"], "text")
        self.assertEqual(r.data["author"]["username"], "alice")

    def test_empty_post_rejected(self):
        r = self.a.post("/api/social/posts/", {"caption": "  "}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_multiple_images(self):
        r = self.a.post("/api/social/posts/", {"caption": "pics", "visibility": "public",
                                               "images": [png("1.png"), png("2.png"), png("3.png")]},
                        format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.data["images"]), 3)
        self.assertEqual(r.data["kind"], "image")

    def test_fake_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        r = self.a.post("/api/social/posts/", {"caption": "x", "images": [bad]}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_private_post_not_accessible_by_direct_id(self):
        pid = self.new_post(self.a, visibility="private")
        make_friends(self.alice, self.bob)
        for client in (self.b, self.c):
            self.assertEqual(client.get(f"/api/social/posts/{pid}/").status_code, 404)
            self.assertEqual(client.post(f"/api/social/posts/{pid}/like/").status_code, 404)
            self.assertEqual(client.post(f"/api/social/posts/{pid}/comments/", {"body": "hi"}).status_code, 404)
            self.assertEqual(client.get(f"/api/social/posts/{pid}/comments/").status_code, 404)
            self.assertEqual(client.get(f"/api/social/posts/{pid}/likes/").status_code, 404)
            self.assertEqual(client.post(f"/api/social/posts/{pid}/share/", {}).status_code, 404)
        self.assertEqual(self.a.get(f"/api/social/posts/{pid}/").status_code, 200)

    def test_friends_post_only_visible_to_friends(self):
        pid = self.new_post(self.a, visibility="friends")
        make_friends(self.alice, self.bob)
        self.assertEqual(self.b.get(f"/api/social/posts/{pid}/").status_code, 200)
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 404)

    def test_public_post_visible_to_everyone(self):
        pid = self.new_post(self.a, visibility="public")
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 200)

    def test_change_privacy(self):
        pid = self.new_post(self.a, visibility="public")
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 200)
        r = self.a.patch(f"/api/social/posts/{pid}/", {"visibility": "private"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_edited"])
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 404)

    def test_only_author_can_edit_or_delete(self):
        pid = self.new_post(self.a)
        self.assertEqual(self.b.patch(f"/api/social/posts/{pid}/", {"caption": "hacked"}, format="json").status_code, 404)
        self.assertEqual(self.b.delete(f"/api/social/posts/{pid}/").status_code, 404)
        self.assertEqual(self.a.delete(f"/api/social/posts/{pid}/").status_code, 204)
        self.assertFalse(Post.objects.filter(pk=pid).exists())

    def test_edit_images(self):
        r = self.a.post("/api/social/posts/", {"caption": "p", "visibility": "public", "images": [png("1.png"), png("2.png")]},
                        format="multipart")
        pid, first = r.data["id"], r.data["images"][0]["id"]
        r = self.a.patch(f"/api/social/posts/{pid}/", {"remove_image_ids": [first], "images": [png("3.png")]},
                         format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data["images"]), 2)
        self.assertNotIn(first, [i["id"] for i in r.data["images"]])


class FeedTests(ApiTestCase):
    def results(self, client, url="/api/social/feed/"):
        r = client.get(url)
        self.assertEqual(r.status_code, 200, r.content)
        return r.data["results"]

    def test_feed_contents_follow_privacy(self):
        make_friends(self.alice, self.bob)
        pub = self.new_post(self.bob, "bob public", "public")
        fr = self.new_post(self.bob, "bob friends", "friends")
        pr = self.new_post(self.bob, "bob private", "private")
        cpub = self.new_post(self.carol, "carol public", "public")
        cfr = self.new_post(self.carol, "carol friends", "friends")
        ids = {p["id"] for p in self.results(self.a)}
        self.assertEqual(ids, {pub, fr, cpub})
        self.assertNotIn(pr, ids)
        self.assertNotIn(cfr, ids)

    def test_feed_includes_own_posts_of_every_visibility(self):
        ids = [self.new_post(self.a, visibility=v) for v in ("public", "friends", "private")]
        self.assertEqual({p["id"] for p in self.results(self.a)}, set(ids))

    def test_blocked_users_never_appear_either_way(self):
        self.new_post(self.bob, "from bob", "public")
        self.new_post(self.alice, "from alice", "public")
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.assertEqual({p["author"]["username"] for p in self.results(self.a)}, {"alice"})
        self.assertEqual({p["author"]["username"] for p in self.results(self.b)}, {"bob"})

    def test_inactive_authors_hidden(self):
        self.new_post(self.bob, "x", "public")
        User.objects.filter(pk=self.bob.pk).update(is_active=False)
        self.assertEqual(self.results(self.a), [])

    def test_cursor_pagination_no_duplicates_no_gaps(self):
        ids = [self.new_post(self.b, f"p{i}", "public") for i in range(25)]
        seen, url = [], "/api/social/feed/?page_size=10"
        while url:
            r = self.a.get(url)
            self.assertEqual(r.status_code, 200)
            seen += [p["id"] for p in r.data["results"]]
            url = r.data["next"]
        self.assertEqual(seen, sorted(ids, reverse=True))
        self.assertEqual(len(seen), len(set(seen)))

    def test_friends_scope(self):
        make_friends(self.alice, self.bob)
        self.new_post(self.bob, "friend post", "public")
        self.new_post(self.carol, "stranger post", "public")
        self.new_post(self.alice, "mine", "public")
        names = {p["author"]["username"] for p in self.results(self.a, "/api/social/feed/?scope=friends")}
        self.assertEqual(names, {"bob"})

    def test_ranked_mode_boosts_friends_and_engagement(self):
        make_friends(self.alice, self.bob)
        stranger = self.new_post(self.carol, "stranger", "public")
        friend = self.new_post(self.bob, "friend", "public")
        r = self.a.get("/api/social/feed/?mode=ranked")
        self.assertEqual(r.status_code, 200)
        order = [p["id"] for p in r.data["results"]]
        self.assertEqual(order[0], friend)
        self.assertIn(stranger, order)

    def test_query_count_does_not_grow_with_posts(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        make_friends(self.alice, self.bob)
        for i in range(3):
            self.new_post(self.b, f"a{i}", "public")
        with CaptureQueriesContext(connection) as small:
            self.a.get("/api/social/feed/")
        for i in range(15):
            self.new_post(self.b, f"b{i}", "public")
        with CaptureQueriesContext(connection) as big:
            self.a.get("/api/social/feed/")
        self.assertEqual(len(small), len(big))  # no N+1


class LikeCommentTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.pid = self.new_post(self.a, "likeable", "public")

    def test_like_unlike_and_no_duplicates(self):
        r = self.b.post(f"/api/social/posts/{self.pid}/like/")
        self.assertEqual((r.status_code, r.data["like_count"]), (200, 1))
        self.assertEqual(self.b.post(f"/api/social/posts/{self.pid}/like/").status_code, 409)
        self.assertEqual(Post.objects.get(pk=self.pid).like_count, 1)
        r = self.b.delete(f"/api/social/posts/{self.pid}/like/")
        self.assertEqual(r.data["like_count"], 0)
        self.assertEqual(self.b.delete(f"/api/social/posts/{self.pid}/like/").status_code, 409)

    def test_liked_by_me_and_likes_list(self):
        self.b.post(f"/api/social/posts/{self.pid}/like/")
        self.c.post(f"/api/social/posts/{self.pid}/like/")
        self.assertTrue(self.b.get(f"/api/social/posts/{self.pid}/").data["liked_by_me"])
        self.assertFalse(self.a.get(f"/api/social/posts/{self.pid}/").data["liked_by_me"])
        r = self.a.get(f"/api/social/posts/{self.pid}/likes/")
        self.assertEqual({u["username"] for u in r.data["results"]}, {"bob", "carol"})

    def test_like_notifies_author_once_and_not_self(self):
        self.b.post(f"/api/social/posts/{self.pid}/like/")
        self.a.post(f"/api/social/posts/{self.pid}/like/")
        self.assertEqual(Notification.objects.filter(recipient=self.alice, type="post_like").count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.bob).count(), 0)

    def test_comment_reply_edit_delete(self):
        r = self.b.post(f"/api/social/posts/{self.pid}/comments/", {"body": "nice"}, format="json")
        self.assertEqual(r.status_code, 201)
        cid = r.data["id"]
        r = self.c.post(f"/api/social/posts/{self.pid}/comments/", {"body": "reply", "parent": cid}, format="json")
        self.assertEqual(r.status_code, 201)
        rid = r.data["id"]
        # replies are one level deep
        r = self.a.post(f"/api/social/posts/{self.pid}/comments/", {"body": "deep", "parent": rid}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Post.objects.get(pk=self.pid).comment_count, 2)
        # listing
        r = self.a.get(f"/api/social/posts/{self.pid}/comments/")
        self.assertEqual(len(r.data["results"]), 1)
        self.assertEqual(r.data["results"][0]["replies_count"], 1)
        r = self.a.get(f"/api/social/comments/{cid}/replies/")
        self.assertEqual([c["body"] for c in r.data["results"]], ["reply"])
        # edit: only own
        self.assertEqual(self.c.patch(f"/api/social/comments/{cid}/", {"body": "x"}, format="json").status_code, 403)
        r = self.b.patch(f"/api/social/comments/{cid}/", {"body": "edited"}, format="json")
        self.assertEqual((r.status_code, r.data["is_edited"]), (200, True))
        # delete: stranger forbidden; owner removes comment + its reply from the count
        self.assertEqual(self.c.delete(f"/api/social/comments/{cid}/").status_code, 403)
        self.assertEqual(self.b.delete(f"/api/social/comments/{cid}/").status_code, 204)
        self.assertEqual(Post.objects.get(pk=self.pid).comment_count, 0)

    def test_post_owner_can_remove_comments_on_their_post(self):
        cid = self.b.post(f"/api/social/posts/{self.pid}/comments/", {"body": "spam"}, format="json").data["id"]
        self.assertEqual(self.a.delete(f"/api/social/comments/{cid}/").status_code, 204)

    def test_comment_like_unique(self):
        cid = self.b.post(f"/api/social/posts/{self.pid}/comments/", {"body": "c"}, format="json").data["id"]
        self.assertEqual(self.c.post(f"/api/social/comments/{cid}/like/").data["like_count"], 1)
        self.assertEqual(self.c.post(f"/api/social/comments/{cid}/like/").status_code, 409)
        self.assertEqual(self.c.delete(f"/api/social/comments/{cid}/like/").data["like_count"], 0)

    def test_comment_actions_blocked_once_post_becomes_private(self):
        cid = self.b.post(f"/api/social/posts/{self.pid}/comments/", {"body": "c"}, format="json").data["id"]
        self.a.patch(f"/api/social/posts/{self.pid}/", {"visibility": "private"}, format="json")
        self.assertEqual(self.b.patch(f"/api/social/comments/{cid}/", {"body": "y"}, format="json").status_code, 404)
        self.assertEqual(self.c.post(f"/api/social/comments/{cid}/like/").status_code, 404)

    def test_blocked_users_comments_hidden(self):
        self.b.post(f"/api/social/posts/{self.pid}/comments/", {"body": "from bob"}, format="json")
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.assertEqual(self.a.get(f"/api/social/posts/{self.pid}/comments/").data["results"], [])


class ShareTests(ApiTestCase):
    def test_share_public_post(self):
        pid = self.new_post(self.a, "original", "public")
        r = self.b.post(f"/api/social/posts/{pid}/share/", {"caption": "look", "visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["kind"], "share")
        self.assertEqual(r.data["shared_from"]["id"], pid)
        self.assertEqual(r.data["shared_from"]["author"]["username"], "alice")
        self.assertEqual(Post.objects.get(pk=pid).share_count, 1)
        # no copy of the original was created
        self.assertEqual(Post.objects.filter(caption="original").count(), 1)

    def test_cannot_share_twice(self):
        pid = self.new_post(self.a, "original", "public")
        self.assertEqual(self.b.post(f"/api/social/posts/{pid}/share/", {}).status_code, 201)
        self.assertEqual(self.b.post(f"/api/social/posts/{pid}/share/", {}).status_code, 409)
        self.assertEqual(Post.objects.get(pk=pid).share_count, 1)

    def test_cannot_share_friends_only_post_even_as_friend(self):
        make_friends(self.alice, self.bob)
        pid = self.new_post(self.a, "friends only", "friends")
        self.assertEqual(self.b.post(f"/api/social/posts/{pid}/share/", {}).status_code, 403)

    def test_share_of_share_points_at_root(self):
        pid = self.new_post(self.a, "root", "public")
        sid = self.b.post(f"/api/social/posts/{pid}/share/", {"visibility": "public"}, format="json").data["id"]
        r = self.c.post(f"/api/social/posts/{sid}/share/", {"visibility": "public"}, format="json")
        self.assertEqual(r.data["shared_from"]["id"], pid)
        self.assertEqual(Post.objects.get(pk=pid).share_count, 2)

    def test_deleting_share_decrements_count(self):
        pid = self.new_post(self.a, "root", "public")
        sid = self.b.post(f"/api/social/posts/{pid}/share/", {}, format="json").data["id"]
        self.assertEqual(self.b.delete(f"/api/social/posts/{sid}/").status_code, 204)
        self.assertEqual(Post.objects.get(pk=pid).share_count, 0)

    def test_original_hidden_when_it_becomes_private(self):
        pid = self.new_post(self.a, "root", "public")
        sid = self.b.post(f"/api/social/posts/{pid}/share/", {"caption": "c", "visibility": "public"}, format="json").data["id"]
        self.a.patch(f"/api/social/posts/{pid}/", {"visibility": "private"}, format="json")
        r = self.c.get(f"/api/social/posts/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["shared_from"])
        self.assertTrue(r.data["original_unavailable"])
        self.assertNotIn(sid, [p["id"] for p in self.c.get("/api/social/feed/").data["results"]])

    def test_feed_collapses_repeated_shares_of_same_original(self):
        pid = self.new_post(self.a, "root", "public")
        self.b.post(f"/api/social/posts/{pid}/share/", {"visibility": "public"}, format="json")
        last = self.c.post(f"/api/social/posts/{pid}/share/", {"visibility": "public"}, format="json").data["id"]
        viewer = self.as_user(make_user("dave"))
        shares = [p for p in viewer.get("/api/social/feed/").data["results"] if p["kind"] == "share"]
        self.assertEqual([p["id"] for p in shares], [last])


class AchievementTests(ApiTestCase):
    """Social uses the single achievements.Achievement model; these tests create rows directly."""

    def make(self, owner=None, is_public=False, **extra):
        a = Achievement.objects.create(
            user=owner or self.alice, category=AchievementCategory.objects.first(), title="Won debate",
            issuing_organization="KU", achievement_date="2026-03-01",
            visibility="public" if is_public else "private", **extra)
        return a.pk

    def test_private_by_default_and_hidden_from_others(self):
        self.make()
        self.assertEqual(self.b.get("/api/social/profiles/alice/achievements/").data["results"], [])
        self.assertEqual(len(self.a.get("/api/social/profiles/alice/achievements/").data["results"]), 1)

    def test_private_achievement_cannot_be_posted_publicly(self):
        aid = self.make()
        r = self.a.post("/api/social/posts/", {"achievement_id": aid, "visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.a.post("/api/social/posts/", {"achievement_id": aid, "visibility": "private"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_public_achievement_post_and_no_duplicate_post(self):
        aid = self.make(is_public=True)
        r = self.a.post("/api/social/posts/", {"achievement_id": aid, "visibility": "public", "caption": "Proud!"},
                        format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["kind"], "achievement")
        self.assertEqual(r.data["achievement"]["title"], "Won debate")
        r = self.a.post("/api/social/posts/", {"achievement_id": aid, "visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Post.objects.filter(achievement_id=aid).count(), 1)

    def test_cannot_post_someone_elses_achievement(self):
        aid = self.make(is_public=True)
        r = self.b.post("/api/social/posts/", {"achievement_id": aid, "visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_making_achievement_private_downgrades_its_post(self):
        aid = self.make(is_public=True)
        pid = self.a.post("/api/social/posts/", {"achievement_id": aid, "visibility": "public"}, format="json").data["id"]
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 200)
        ach = Achievement.objects.get(pk=aid)
        ach.visibility = "private"
        ach.save()
        self.assertEqual(self.c.get(f"/api/social/posts/{pid}/").status_code, 404)
        self.assertEqual(Post.objects.get(pk=pid).visibility, "private")
        # and it can't be re-published while private
        r = self.a.patch(f"/api/social/posts/{pid}/", {"visibility": "public"}, format="json")
        self.assertEqual(r.status_code, 400)


class ProfileTests(ApiTestCase):
    def test_update_my_profile(self):
        r = self.a.patch("/api/social/profiles/me/", {
            "bio": "Robotics club", "institution": "KU", "department": "CS",
            "interests": ["Chess", " chess ", "Robotics"], "skills": ["Python"], "full_name": "Alice A"},
            format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["interests"], ["chess", "robotics"])
        self.assertEqual(r.data["full_name"], "Alice A")
        self.assertTrue(r.data["is_self"])

    def test_avatar_upload(self):
        r = self.a.patch("/api/social/profiles/me/", {"avatar": png("me.png")}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(f"/media/profiles/{self.alice.pk}/", r.data["avatar"])  # stored as UserProfile.profile_picture

    def test_other_profile_stats_and_relationship_states(self):
        self.new_post(self.b, "pub", "public")
        self.new_post(self.b, "priv", "private")
        self.new_post(self.b, "fr", "friends")
        r = self.a.get("/api/social/profiles/bob/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["posts_count"], 1)                       # only what alice may see
        self.assertEqual(r.data["relationship"]["state"], "NOT_FRIENDS")
        self.assertTrue(r.data["can_message"])
        self.assertNotIn("email", r.data)
        make_friends(self.alice, self.bob)
        r = self.a.get("/api/social/profiles/bob/")
        self.assertEqual((r.data["posts_count"], r.data["is_friend"], r.data["friends_count"]), (2, True, 1))

    def test_mutual_friends_on_profile(self):
        make_friends(self.alice, self.carol)
        make_friends(self.bob, self.carol)
        r = self.a.get("/api/social/profiles/bob/")
        self.assertEqual(r.data["mutual_friends_count"], 1)

    def test_blocked_profile_is_404_both_ways(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.assertEqual(self.a.get("/api/social/profiles/bob/").status_code, 404)
        self.assertEqual(self.b.get("/api/social/profiles/alice/").status_code, 404)

    def test_profile_posts_respect_privacy(self):
        self.new_post(self.b, "pub", "public")
        self.new_post(self.b, "priv", "private")
        r = self.a.get("/api/social/profiles/bob/posts/")
        self.assertEqual([p["caption"] for p in r.data["results"]], ["pub"])

    def test_existing_users_get_profiles_automatically(self):
        self.assertTrue(hasattr(make_user("zed"), "user_profile"))

    def test_requires_authentication(self):
        from rest_framework.test import APIClient
        anon = APIClient()
        for url in ("/api/social/feed/", "/api/social/home/", "/api/social/profiles/alice/", "/api/social/notifications/"):
            self.assertEqual(anon.get(url).status_code, 401, url)


class NotificationAndHomeTests(ApiTestCase):
    def test_notifications_flow(self):
        pid = self.new_post(self.a, "x", "public")
        self.b.post(f"/api/social/posts/{pid}/like/")
        self.b.post(f"/api/social/posts/{pid}/comments/", {"body": "c"}, format="json")
        self.assertEqual(self.a.get("/api/social/notifications/unread-count/").data["unread"], 2)
        r = self.a.get("/api/social/notifications/")
        self.assertEqual(len(r.data["results"]), 2)
        self.assertIn("Bob", r.data["results"][0]["text"])
        nid = r.data["results"][0]["id"]
        self.assertEqual(self.b.post(f"/api/social/notifications/{nid}/read/").status_code, 404)  # not bob's
        self.assertEqual(self.a.post(f"/api/social/notifications/{nid}/read/").status_code, 200)
        self.assertEqual(self.a.post("/api/social/notifications/read-all/").data["marked_read"], 1)

    def test_home_summary(self):
        make_friends(self.alice, self.bob)
        make_friends(self.bob, self.carol)
        self.b.post("/api/friends/requests/", {"user_id": self.alice.pk}, format="json")  # no-op: already friends
        r = self.a.get("/api/social/home/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["me"]["username"], "alice")
        self.assertEqual([s["user"]["username"] for s in r.data["suggested_friends"]][:1], ["carol"])
        self.assertEqual(r.data["suggested_friends"][0]["reasons"]["mutual_friends"], 1)
