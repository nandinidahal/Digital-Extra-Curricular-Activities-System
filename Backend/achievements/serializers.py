from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import Achievement, AchievementCategory, AchievementDocument, DocumentType
from .validators import inspect_upload, safe_original_name, validate_achievement_file

MIN_ACHIEVEMENT_DATE = date(1900, 1, 1)


# --------------------------------------------------------------------------- read side
class AchievementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AchievementCategory
        fields = ("id", "name", "slug", "description")
        read_only_fields = fields


class AchievementDocumentSerializer(serializers.ModelSerializer):
    """Never exposes the stored file name, path or any storage URL, only the secure endpoint."""

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = AchievementDocument
        fields = (
            "id", "document_type", "document_name", "original_filename",
            "content_type", "size", "uploaded_at", "download_url",
        )
        read_only_fields = fields

    def get_download_url(self, obj):
        return reverse(
            "achievement-document-download",
            kwargs={"pk": obj.achievement_id, "document_id": obj.pk},
            request=self.context.get("request"),
        )


class _AchievementReadSerializer(serializers.ModelSerializer):
    category = AchievementCategorySerializer(read_only=True)
    documents = AchievementDocumentSerializer(many=True, read_only=True)
    owner = serializers.SerializerMethodField()

    def get_owner(self, obj):
        u = obj.user
        return {"id": u.id, "full_name": u.full_name, "username": u.username}


class OwnerAchievementSerializer(_AchievementReadSerializer):
    """What the owner sees: everything, including visibility and certificate number."""

    class Meta:
        model = Achievement
        fields = (
            "id", "title", "category", "description", "issuing_organization", "achievement_date",
            "certificate_number", "location", "visibility", "documents", "owner",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class PublicAchievementSerializer(_AchievementReadSerializer):
    """What other users see. Deliberately omits visibility and the certificate number."""

    class Meta:
        model = Achievement
        fields = (
            "id", "title", "category", "description", "issuing_organization", "achievement_date",
            "location", "documents", "owner", "created_at",
        )
        read_only_fields = fields


# --------------------------------------------------------------------------- write side
class AchievementWriteSerializer(serializers.ModelSerializer):
    """Create / update.

    `user` is not a field, so the owner always comes from the request and cannot be set
    through the payload. Documents are sent as multipart/form-data:
      certificate            single file (replaces the existing certificate on update)
      supporting_documents   one or more files (always appended)
      remove_document_ids    ids of existing documents to delete (update only)
    Documents that are not mentioned are never touched.
    """

    category = serializers.PrimaryKeyRelatedField(queryset=AchievementCategory.objects.filter(is_active=True))
    certificate = serializers.FileField(
        write_only=True, required=False, allow_empty_file=False, validators=[validate_achievement_file]
    )
    supporting_documents = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, validators=[validate_achievement_file]),
        write_only=True, required=False, allow_empty=True,
    )
    remove_document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), write_only=True, required=False, allow_empty=True,
    )

    class Meta:
        model = Achievement
        fields = (
            "id", "title", "category", "description", "issuing_organization", "achievement_date",
            "certificate_number", "location", "visibility",
            "certificate", "supporting_documents", "remove_document_ids",
        )
        read_only_fields = ("id",)

    # ---- field validation
    def validate_achievement_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Achievement date cannot be in the future.")
        if value < MIN_ACHIEVEMENT_DATE:
            raise serializers.ValidationError("Achievement date is too far in the past.")
        return value

    def validate(self, attrs):
        certificate = attrs.get("certificate")
        supporting = attrs.get("supporting_documents", [])
        remove_ids = set(attrs.get("remove_document_ids", []))

        existing = list(self.instance.documents.all()) if self.instance else []
        unknown = remove_ids - {d.id for d in existing}
        if unknown:
            raise serializers.ValidationError(
                {"remove_document_ids": [f"Document(s) not found on this achievement: {sorted(unknown)}."]}
            )

        remaining = [d for d in existing if d.id not in remove_ids]
        replaces_certificate = certificate is not None and any(
            d.document_type == DocumentType.CERTIFICATE for d in remaining
        )
        total = len(remaining) - int(replaces_certificate) + int(certificate is not None) + len(supporting)

        max_documents = getattr(settings, "ACHIEVEMENT_MAX_DOCUMENTS", 6)
        if total > max_documents:
            raise serializers.ValidationError(
                {"supporting_documents": [f"An achievement can have at most {max_documents} documents."]}
            )

        touches_documents = bool(certificate is not None or supporting or remove_ids)
        if getattr(settings, "ACHIEVEMENT_REQUIRE_DOCUMENT", True) and (self.instance is None or touches_documents):
            if total < 1:
                raise serializers.ValidationError(
                    {"certificate": ["Upload a certificate or at least one supporting document."]}
                )
        return attrs

    # ---- persistence
    def _store_documents(self, achievement, certificate, supporting):
        """Save the uploaded files; if anything fails, remove files already written."""
        uploads = ([(certificate, DocumentType.CERTIFICATE)] if certificate is not None else []) + [
            (f, DocumentType.SUPPORTING) for f in supporting
        ]
        created = []
        try:
            for upload, doc_type in uploads:
                ext, content_type = inspect_upload(upload)
                original = safe_original_name(upload.name, ext)
                doc = AchievementDocument(
                    achievement=achievement,
                    document_type=doc_type,
                    document_name=original.rsplit(".", 1)[0][:150],
                    original_filename=original,
                    content_type=content_type,
                    size=upload.size,
                    file=upload,
                )
                created.append(doc)
                doc.save()
        except Exception:
            for doc in created:
                if doc.file and getattr(doc.file, "_committed", False):
                    doc.file.storage.delete(doc.file.name)
            raise

    @transaction.atomic
    def create(self, validated_data):
        certificate = validated_data.pop("certificate", None)
        supporting = validated_data.pop("supporting_documents", [])
        validated_data.pop("remove_document_ids", None)
        achievement = Achievement.objects.create(user=self.context["request"].user, **validated_data)
        self._store_documents(achievement, certificate, supporting)
        return achievement

    @transaction.atomic
    def update(self, instance, validated_data):
        certificate = validated_data.pop("certificate", None)
        supporting = validated_data.pop("supporting_documents", [])
        remove_ids = validated_data.pop("remove_document_ids", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Row deletions fire post_delete, which removes the files after commit.
        if remove_ids:
            instance.documents.filter(id__in=remove_ids).delete()
        if certificate is not None:
            instance.documents.filter(document_type=DocumentType.CERTIFICATE).delete()
        self._store_documents(instance, certificate, supporting)
        return instance

    def to_representation(self, instance):
        return OwnerAchievementSerializer(instance, context=self.context).data
