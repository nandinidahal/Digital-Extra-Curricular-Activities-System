from social.models import ContentReport

from .base import SocialTestCase


class ReportTests(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.alice, "questionable")
        self.comment = self.make_comment(self.post, self.alice, "rude comment")

    def report_post(self, **extra):
        return self.client.post(self.url("post-report", post_id=self.post.pk), {"reason": "spam", **extra}, format="json")

    def report_comment(self, **extra):
        return self.client.post(self.url("comment-report", comment_id=self.comment.pk), {"reason": "harassment", **extra}, format="json")

    def test_report_a_post(self):
        self.login(self.bob)
        response = self.report_post(description="Looks like an advert")
        self.assertEqual(response.status_code, 201, response.content)
        report = ContentReport.objects.get()
        self.assertEqual((report.reporter, report.post, report.comment), (self.bob, self.post, None))
        self.assertEqual((report.content_type, report.reason, report.status), ("post", "spam", "pending"))
        self.assertEqual(report.description, "Looks like an advert")

    def test_report_a_comment(self):
        self.login(self.bob)
        self.assertEqual(self.report_comment().status_code, 201)
        report = ContentReport.objects.get()
        self.assertEqual((report.content_type, report.comment, report.post), ("comment", self.comment, None))

    def test_every_reason_is_accepted(self):
        self.login(self.bob)
        for index, reason in enumerate(("spam", "harassment", "inappropriate", "false_information", "bullying", "other")):
            post = self.make_post(self.alice, f"p{index}")
            response = self.client.post(self.url("post-report", post_id=post.pk), {"reason": reason}, format="json")
            self.assertEqual(response.status_code, 201, (reason, response.content))

    def test_reject_invalid_reports(self):
        self.login(self.bob)
        for payload in ({}, {"reason": "because"}, {"reason": "spam", "description": "x" * 1001},
                        {"reason": "spam", "reporter": str(self.alice.pk)}, {"reason": "spam", "status": "resolved"}):
            response = self.client.post(self.url("post-report", post_id=self.post.pk), payload, format="json")
            self.assertError(response, 400, "validation_error")
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_cannot_report_missing_deleted_or_inaccessible_content(self):
        import uuid
        private = self.make_post(self.alice, visibility="private")
        deleted = self.make_post(self.alice, is_deleted=True)
        self.login(self.bob)
        for pid in (private.pk, deleted.pk, uuid.uuid4()):
            response = self.client.post(self.url("post-report", post_id=pid), {"reason": "spam"}, format="json")
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post(self.url("comment-report", comment_id=uuid.uuid4()), {"reason": "spam"}, format="json").status_code, 404)
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_duplicate_active_report_blocked_but_allowed_after_review(self):
        self.login(self.bob)
        self.assertEqual(self.report_post().status_code, 201)
        self.assertError(self.report_post(), 409, "already_reported")
        self.assertEqual(ContentReport.objects.count(), 1)
        ContentReport.objects.update(status="dismissed")
        self.assertEqual(self.report_post().status_code, 201)
        self.assertEqual(ContentReport.objects.count(), 2)

    def test_duplicate_comment_report_blocked(self):
        self.login(self.bob)
        self.assertEqual(self.report_comment().status_code, 201)
        self.assertError(self.report_comment(), 409, "already_reported")

    def test_different_users_may_report_the_same_content(self):
        self.login(self.bob)
        self.report_post()
        self.login(self.admin)
        self.assertEqual(self.report_post().status_code, 201)
        self.assertEqual(ContentReport.objects.count(), 2)

    def test_cannot_report_own_content(self):
        self.login(self.alice)
        self.assertError(self.report_post(), 400, "cannot_report_own_content")
        self.assertError(self.report_comment(), 400, "cannot_report_own_content")

    def test_report_requires_login(self):
        self.assertEqual(self.report_post().status_code, 401)
        self.assertEqual(self.report_comment().status_code, 401)

    def test_response_never_reveals_reporter_or_reviewer(self):
        self.login(self.bob)
        body = self.report_post(description="private note").json()
        raw = str(body)
        self.assertNotIn("bob", raw)
        self.assertNotIn(str(self.bob.pk), raw)
        self.assertNotIn("private note", raw)
        self.assertEqual(set(body["data"]["report"]), {"id", "content_type", "reason", "status", "created_at"})

    def test_reports_do_not_appear_in_post_or_comment_payloads(self):
        self.login(self.bob)
        self.report_post()
        self.login(self.alice)
        post_body = self.client.get(self.url("post-detail", post_id=self.post.pk)).content.decode()
        comments_body = self.client.get(self.url("post-comments", post_id=self.post.pk)).content.decode()
        for body in (post_body, comments_body):
            self.assertNotIn("report", body.lower().replace("success", ""))

    def test_no_public_endpoint_lists_reports(self):
        # Reports are listed only for moderators (admin/coordinator); members get 403.
        self.login(self.bob)
        self.assertEqual(self.client.get("/api/social/reports/").status_code, 403)
        self.assertEqual(self.client.get("/api/social/me/reports/").status_code, 404)
        self.login(self.admin)
        self.assertEqual(self.client.get("/api/social/reports/").status_code, 200)
