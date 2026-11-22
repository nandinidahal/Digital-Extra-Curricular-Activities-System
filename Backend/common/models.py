"""
Reusable abstract base models. They create NO tables of their own.

New DEAS models (announcements, achievements, notifications) inherit from `BaseModel`
(UUID primary key + timestamps), which matches the UUID keys already used by Accounts,
Profiles, Friends, Social and Messaging. Existing models are deliberately NOT changed.
"""
import uuid

from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimeStampedModel):
    class Meta:
        abstract = True
