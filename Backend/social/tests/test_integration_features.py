"""
Social features added with the Friends / Notifications / Announcements / Achievements integration:
friends-only visibility, blocking, notifications, sharing announcements and achievements,
generic report endpoint and report moderation, privacy of author pictures.
"""
import datetime

from django.utils import timezone

from achievements.models import Achievement
from announcements.models import Announcement, Category
from common.testing import DEASTestCase
from notifications.models import Notification
from profiles.models import Profile
from social.models import Comment, ContentReport, Post, PostShare

S = "/api/social/"


class SocialIntegrationTestCase(DEASTestCase):
    def post(self, author, visibility="public", content="Hello"):
        return Post.objects.create(author=author, content=content, visibility=visibility)

    def comment(self, post, author, parent=None):
        return Comment.objects.create(post=post, author=author, content="Nice", parent_comment=parent, depth=(parent.depth + 1) if parent else 0)

    def announcement(self, author=None, **extra):
        fields = dict(author=author or self.bob, title="Science Fair", slug=f"sf-{timezone.now().timestamp()}",
                      category=Category.objects.get(slug="education"), status="published", published_at=timezone.now(),
                      visibility="public", start_datetime=timezone.now() + datetime.timedelta(days=3), location="Hall")
        fields.update(extra)
        return Announcement.objects.create(**fields)

    def achievement(self, user=None, **extra):
        fields = dict(user=user or self.bob, title="Chess champion", achievement_date=datetime.date(2026, 1, 1),
                      verification_status="verified", verified_at=timezone.now(), submitted_at=timezone.now(), visibility="public")
        fields.update(extra)
        return Achievement.objects.create(**fields)


class FriendsVisibilityTests(SocialIntegrationTestCase):
    def test_friends_only_post(self):
        post = self.post(self.alice, "friends")
        self.befriend(self.alice, self.bob)
        self.assertError(self.client.get(f"{S}posts/{post.pk}/"), 401, "authentication_required")
        self.login(self.carol)
        self.assertError(self.client.get(f"{S}posts/{post.pk}/"), 404)
        self.assertNotIn(str(post.pk), self.ids(self.assertOk(self.client.get(f"{S}feed/"))))
        self.assertError(self.client.post(f"{S}posts/{post.pk}/like/"), 404)
        self.login(self.bob)
        self.assertOk(self.client.get(f"{S}posts/{post.pk}/"))
        self.assertIn(str(post.pk), self.ids(self.assertOk(self.client.get(f"{S}feed/"))))
        self.assertOk(self.client.post(f"{S}posts/{post.pk}/like/"), 201)

    def test_friends_feed_scope(self):
        mine, friend, stranger = self.post(self.alice), self.post(self.bob), self.post(self.carol)
        self.befriend(self.alice, self.bob)
        self.login(self.alice)
        self.assertEqual(set(self.ids(self.assertOk(self.client.get(f"{S}feed/?scope=friends")))), {str(mine.pk), str(friend.pk)})
        self.assertIn(str(stranger.pk), self.ids(self.assertOk(self.client.get(f"{S}feed/"))))

    def test_friends_only_post_cannot_be_reshared(self):
        post = self.post(self.alice, "friends")
        self.befriend(self.alice, self.bob)
        self.login(self.bob)
        self.assertError(self.client.post(f"{S}posts/{post.pk}/share/"), 400, "post_not_shareable")


class BlockingTests(SocialIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.alice_post = self.post(self.alice)
        self.bob_comment = self.comment(self.alice_post, self.bob)
        self.carol_comment = self.comment(self.alice_post, self.carol)
        self.block(self.alice, self.bob)

    def test_blocked_user_cannot_see_or_interact(self):
        self.login(self.bob)
        self.assertError(self.client.get(f"{S}posts/{self.alice_post.pk}/"), 404)
        self.assertNotIn(str(self.alice_post.pk), self.ids(self.assertOk(self.client.get(f"{S}feed/"))))
        self.assertNotIn(str(self.alice_post.pk), self.ids(self.assertOk(self.client.get(f"{S}posts/"))))
        self.assertError(self.client.get(f"{S}users/{self.alice.pk}/posts/"), 404)
        for path, body in ((f"posts/{self.alice_post.pk}/like/", None), (f"posts/{self.alice_post.pk}/comments/", {"content": "hi"}),
                           (f"posts/{self.alice_post.pk}/share/", {}), (f"posts/{self.alice_post.pk}/report/", {"reason": "spam"})):
            with self.subTest(path=path):
                self.assertError(self.client.post(S + path, body or {}, format="json"), 404)

    def test_blocker_does_not_see_blocked_users_comments(self):
        self.login(self.alice)
        ids = self.ids(self.assertOk(self.client.get(f"{S}posts/{self.alice_post.pk}/comments/")))
        self.assertEqual(ids, [str(self.carol_comment.pk)])
        self.assertError(self.client.post(f"{S}comments/{self.bob_comment.pk}/reply/", {"content": "x"}, format="json"), 404)
        self.assertError(self.client.post(f"{S}comments/{self.bob_comment.pk}/like/"), 404)

    def test_bystander_unaffected(self):
        self.login(self.carol)
        self.assertEqual(len(self.ids(self.assertOk(self.client.get(f"{S}posts/{self.alice_post.pk}/comments/")))), 2)

    def test_admin_moderation_read_still_works(self):
        self.block(self.admin, self.alice)
        self.login(self.admin)
        self.assertOk(self.client.get(f"{S}posts/{self.alice_post.pk}/"))


class SocialNotificationTests(SocialIntegrationTestCase):
    def test_like_notifies_author_once(self):
        post = self.post(self.alice)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"{S}posts/{post.pk}/like/")
            self.client.delete(f"{S}posts/{post.pk}/like/")
            self.client.post(f"{S}posts/{post.pk}/like/")
        notes = Notification.objects.filter(notification_type="post.liked")
        self.assertEqual(notes.count(), 1)
        self.assertEqual((notes[0].recipient, notes[0].actor, notes[0].target_id), (self.alice, self.bob, str(post.pk)))

    def test_own_like_not_notified(self):
        post = self.post(self.alice)
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"{S}posts/{post.pk}/like/")
        self.assertFalse(Notification.objects.exists())

    def test_comment_and_reply_notifications(self):
        post = self.post(self.alice)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            comment_id = self.assertOk(self.client.post(f"{S}posts/{post.pk}/comments/", {"content": "Great"}, format="json"), 201)["comment"]["id"]
        self.assertEqual(Notification.objects.get(notification_type="post.commented").recipient, self.alice)
        self.login(self.carol)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"{S}comments/{comment_id}/reply/", {"content": "Agree"}, format="json")
        self.assertEqual(Notification.objects.get(notification_type="comment.replied").recipient, self.bob)

    def test_failed_action_creates_no_notification(self):
        post = self.post(self.alice)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"{S}posts/{post.pk}/comments/", {"content": "<b>x</b>"}, format="json")
        self.assertFalse(Notification.objects.exists())

    def test_share_notifies_author(self):
        post = self.post(self.alice)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post(f"{S}shares/", {"resource_type": "post", "resource_id": str(post.pk)}, format="json"), 201)
        self.assertEqual(Notification.objects.get(notification_type="post.shared").recipient, self.alice)
        self.assertEqual(PostShare.objects.count(), 1)


class ResourceSharingTests(SocialIntegrationTestCase):
    def share(self, resource_type, resource_id, **extra):
        return self.client.post(f"{S}shares/", {"resource_type": resource_type, "resource_id": str(resource_id), **extra}, format="json")

    def test_share_public_announcement_by_reference(self):
        announcement = self.announcement()
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            post = self.assertOk(self.share("announcement", announcement.pk, caption="Join!"), 201)["post"]
        self.assertEqual((post["shared_type"], post["content"]), ("announcement", "Join!"))
        self.assertEqual(post["shared_resource"]["data"]["title"], "Science Fair")
        self.assertTrue(Post.objects.filter(pk=post["id"], shared_announcement=announcement).exists())
        self.assertEqual(Notification.objects.get(notification_type="post.shared").recipient, self.bob)
        self.assertError(self.share("announcement", announcement.pk), 409, "already_shared")
        self.logout()
        self.assertIn(post["id"], self.ids(self.assertOk(self.client.get(f"{S}feed/"))))

    def test_cannot_share_non_public_announcements(self):
        self.login(self.alice)
        self.assertError(self.share("announcement", self.announcement(visibility="members_only").pk), 400, "post_not_shareable")
        self.assertError(self.share("announcement", self.announcement(status="draft", published_at=None).pk), 404)
        self.assertError(self.share("announcement", self.announcement(visibility="private").pk), 404)

    def test_share_verified_public_achievement_only(self):
        self.login(self.alice)
        post = self.assertOk(self.share("achievement", self.achievement().pk), 201)["post"]
        self.assertEqual(post["shared_resource"]["data"]["user"]["username"], "bob")
        self.assertError(self.share("achievement", self.achievement(verification_status="pending", verified_at=None).pk), 404)
        self.assertError(self.share("achievement", self.achievement(visibility="members_only").pk), 400, "post_not_shareable")
        self.assertError(self.share("achievement", self.achievement(visibility="private").pk), 404)

    def test_shared_content_hidden_when_original_becomes_inaccessible(self):
        announcement = self.announcement()
        achievement = self.achievement()
        self.login(self.alice)
        a_post = self.assertOk(self.share("announcement", announcement.pk), 201)["post"]["id"]
        b_post = self.assertOk(self.share("achievement", achievement.pk), 201)["post"]["id"]
        announcement.visibility = "private"
        announcement.save()
        achievement.verification_status = "pending"
        achievement.save()
        self.logout()
        for post_id in (a_post, b_post):
            data = self.assertOk(self.client.get(f"{S}posts/{post_id}/"))["post"]
            self.assertFalse(data["shared_resource"]["available"])
            self.assertIsNone(data["shared_resource"]["data"])
            self.assertNotIn("Science Fair", str(data))
            self.assertNotIn("Chess champion", str(data))
        announcement.delete()
        data = self.assertOk(self.client.get(f"{S}posts/{a_post}/"))["post"]
        self.assertEqual(data["shared_resource"], {"type": "announcement", "id": None, "available": False, "data": None})

    def test_share_cannot_be_private_or_get_images(self):
        self.login(self.alice)
        self.assertError(self.share("announcement", self.announcement().pk, visibility="private"), 400)
        post_id = self.assertOk(self.share("announcement", self.announcement(title="Other", slug="other-1").pk), 201)["post"]["id"]
        self.assertError(self.client.patch(f"{S}posts/{post_id}/", {"images": [self.image_file()]}, format="multipart"), 400)
        self.assertOk(self.client.patch(f"{S}posts/{post_id}/", {"content": ""}, format="json"))

    def test_feed_query_count_constant_with_shares(self):
        for i in range(4):
            self.login(self.alice)
            self.share("announcement", self.announcement(title=f"A{i}", slug=f"a-{i}").pk)
        self.login(self.carol)
        # Constant whatever the page holds: user, friend ids (2), block ids (2, filter), count, page,
        # media prefetch, block ids (2, re-checked once per response for shared originals).
        with self.assertNumQueries(10):
            self.client.get(f"{S}feed/")


class ReportEndpointTests(SocialIntegrationTestCase):
    def test_generic_report_endpoint(self):
        post = self.post(self.alice)
        comment = self.comment(post, self.alice)
        self.login(self.bob)
        self.assertOk(self.client.post(f"{S}reports/", {"content_type": "post", "object_id": str(post.pk), "reason": "spam"}, format="json"), 201)
        self.assertOk(self.client.post(f"{S}reports/", {"content_type": "comment", "object_id": str(comment.pk), "reason": "bullying"}, format="json"), 201)
        self.assertError(self.client.post(f"{S}reports/", {"content_type": "post", "object_id": str(post.pk), "reason": "spam"}, format="json"), 409)

    def test_moderator_review_removes_content(self):
        post = self.post(self.alice)
        report = ContentReport.objects.create(reporter=self.bob, content_type="post", post=post, reason="harassment")
        self.login(self.bob)
        self.assertError(self.client.patch(f"{S}reports/{report.pk}/", {"status": "resolved"}, format="json"), 403)
        self.login(self.coordinator)
        self.assertEqual(self.ids(self.assertOk(self.client.get(f"{S}reports/?status=pending"))), [str(report.pk)])
        data = self.assertOk(self.client.patch(
            f"{S}reports/{report.pk}/", {"status": "resolved", "action": "content_removed", "review_comments": "Abusive"}, format="json"
        ))["report"]
        self.assertEqual((data["status"], data["action_taken"]), ("resolved", "content_removed"))
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)
        self.assertError(self.client.patch(f"{S}reports/{report.pk}/", {"status": "pending"}, format="json"), 400)

    def test_remove_requires_resolve(self):
        post = self.post(self.alice)
        report = ContentReport.objects.create(reporter=self.bob, content_type="post", post=post, reason="spam")
        self.login(self.admin)
        self.assertError(self.client.patch(f"{S}reports/{report.pk}/", {"status": "reviewing", "action": "content_removed"}, format="json"), 400)


class AuthorPrivacyTests(SocialIntegrationTestCase):
    def test_private_profile_picture_hidden_on_posts(self):
        post = self.post(self.alice)
        Profile.objects.filter(user=self.alice).update(profile_picture="profiles/x/pictures/a.jpg", profile_visibility="private")
        self.login(self.bob)
        self.assertIsNone(self.assertOk(self.client.get(f"{S}posts/{post.pk}/"))["post"]["author"]["profile_picture"])
        self.login(self.alice)
        self.assertIsNotNone(self.assertOk(self.client.get(f"{S}posts/{post.pk}/"))["post"]["author"]["profile_picture"])
