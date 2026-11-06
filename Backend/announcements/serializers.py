from datetime import date, datetime

from django.utils import timezone
from rest_framework import serializers

from .models import Announcement, AnnouncementStatus, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "is_active")
        read_only_fields = ("id", "slug")

    def validate_name(self, value):
        value = value.strip()
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


def _organizer(obj):
    u = obj.published_by
    return {"id": u.id, "full_name": u.full_name, "username": u.username}


class AnnouncementListSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    location = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    organizer = serializers.SerializerMethodField()
    activity_type_display = serializers.CharField(source="get_activity_type_display", read_only=True)

    class Meta:
        model = Announcement
        fields = (
            "id", "title", "short_description", "activity_name", "category",
            "activity_type", "activity_type_display", "banner", "location", "schedule",
            "is_free", "fee_amount", "registration_link", "organizer", "status", "published_at",
        )

    def get_location(self, o):
        return {"country": o.country, "province": o.province, "city": o.city, "venue": o.venue}

    def get_schedule(self, o):
        return {
            "start_date": o.start_date, "end_date": o.end_date,
            "start_time": o.start_time, "end_time": o.end_time,
            "registration_deadline": o.registration_deadline,
        }

    def get_organizer(self, o):
        return _organizer(o)


class AnnouncementDetailSerializer(AnnouncementListSerializer):
    contact = serializers.SerializerMethodField()
    registration_open = serializers.SerializerMethodField()

    class Meta(AnnouncementListSerializer.Meta):
        fields = AnnouncementListSerializer.Meta.fields + (
            "full_description", "keywords", "external_link", "contact",
            "registration_open", "created_at", "updated_at",
        )

    def get_contact(self, o):
        return {"email": o.contact_email, "phone": o.contact_phone}

    def get_registration_open(self, o):
        if o.status != AnnouncementStatus.PUBLISHED:
            return False
        return o.registration_deadline is None or o.registration_deadline > timezone.now()


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True))

    class Meta:
        model = Announcement
        fields = (
            "id", "title", "short_description", "full_description", "activity_name", "category",
            "activity_type", "keywords", "country", "province", "city", "venue",
            "start_date", "end_date", "start_time", "end_time", "registration_deadline",
            "is_free", "fee_amount", "registration_link", "external_link",
            "contact_email", "contact_phone", "banner", "status",
        )
        read_only_fields = ("id",)

    def _val(self, attrs, name):
        if name in attrs:
            return attrs[name]
        return getattr(self.instance, name, None) if self.instance else None

    def validate(self, attrs):
        v = lambda n: self._val(attrs, n)  # noqa: E731
        errors = {}
        start, end = v("start_date"), v("end_date")

        if self.instance is None and start and start < date.today():
            errors["start_date"] = "Start date cannot be in the past."
        if start and end and end < start:
            errors["end_date"] = "End date cannot be before the start date."
        if start and end and start == end and v("start_time") and v("end_time"):
            if v("end_time") <= v("start_time"):
                errors["end_time"] = "End time must be after start time on a single-day event."

        deadline = v("registration_deadline")
        if deadline and start and timezone.localtime(deadline).date() > start:
            errors["registration_deadline"] = "Registration deadline must be on or before the start date."

        if v("activity_type") in ("physical", "hybrid"):
            if not v("city"):
                errors["city"] = "City is required for physical and hybrid activities."
            if not v("venue"):
                errors["venue"] = "Venue is required for physical and hybrid activities."

        if v("is_free") is True and v("fee_amount") not in (None, 0):
            errors["fee_amount"] = "A free activity cannot have a fee."
        if v("fee_amount") is not None and v("fee_amount") < 0:
            errors["fee_amount"] = "Fee cannot be negative."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        return AnnouncementDetailSerializer(instance, context=self.context).data
