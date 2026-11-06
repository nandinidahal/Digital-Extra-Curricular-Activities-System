import django_filters as df

from .models import ActivityType, Announcement


class AnnouncementFilter(df.FilterSet):
    category = df.NumberFilter(field_name="category_id")
    category_slug = df.CharFilter(field_name="category__slug", lookup_expr="iexact")
    country = df.CharFilter(lookup_expr="iexact")
    province = df.CharFilter(lookup_expr="iexact")
    city = df.CharFilter(lookup_expr="iexact")
    type = df.CharFilter(method="filter_type")  # ?type=Physical (case-insensitive)
    start_date = df.DateFilter()
    start_date_from = df.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = df.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date = df.DateFilter()
    end_date_from = df.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_to = df.DateFilter(field_name="end_date", lookup_expr="lte")
    is_free = df.BooleanFilter()
    status = df.CharFilter(method="filter_status")
    mine = df.BooleanFilter(method="filter_mine")

    class Meta:
        model = Announcement
        fields = []

    def filter_type(self, qs, name, value):
        value = value.strip().lower()
        if value not in ActivityType.values:
            return qs.none()
        return qs.filter(activity_type=value)

    def filter_status(self, qs, name, value):
        # The base queryset is already scoped by permissions in the view,
        # so ordinary users asking for ?status=draft simply get nothing.
        return qs.filter(status=value.strip().lower())

    def filter_mine(self, qs, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return qs.filter(published_by=user)
        return qs.none() if value else qs
