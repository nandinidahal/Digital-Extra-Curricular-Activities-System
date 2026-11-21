from django.core.management.base import BaseCommand
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce

from social.models import Comment, CommentLike, Post, PostLike


def _count(model, field, **extra):
    return Coalesce(Subquery(model.objects.filter(**{field: OuterRef("pk")}, **extra).order_by().values(field)
                             .annotate(c=Count("pk")).values("c")[:1]), 0)


class Command(BaseCommand):
    help = "Recompute denormalised like/comment/share counters (use after bulk admin deletes)."

    def handle(self, *args, **opts):
        Post.objects.update(
            like_count=_count(PostLike, "post"),
            comment_count=_count(Comment, "post"),
            share_count=_count(Post, "shared_from"),
        )
        Comment.objects.update(like_count=_count(CommentLike, "comment"))
        self.stdout.write(self.style.SUCCESS("Counters recomputed."))
