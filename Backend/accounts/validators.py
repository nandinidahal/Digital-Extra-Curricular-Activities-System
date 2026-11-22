"""Reusable field validators for the accounts module."""
import re
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
# International format: optional "+", first digit 1-9, 8 to 15 digits in total.
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")
MAX_AGE_YEARS = 120


def validate_username(value):
    if not USERNAME_REGEX.match(value or ""):
        raise ValidationError(
            "Username must be 3-30 characters and may contain only letters, "
            "numbers, underscores and dots."
        )


def normalize_phone_number(value):
    """Strip spaces, dashes, dots and brackets so '+977 98-1234-5678' becomes '+9779812345678'."""
    return re.sub(r"[\s\-().]", "", value or "")


def validate_phone_number(value):
    if not PHONE_REGEX.match(normalize_phone_number(value)):
        raise ValidationError(
            "Enter a valid phone number in international format, e.g. +9779812345678."
        )


def _years_between(born, today):
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def validate_date_of_birth(value):
    today = date.today()
    if value > today:
        raise ValidationError("Date of birth cannot be in the future.")
    age = _years_between(value, today)
    minimum = getattr(settings, "MINIMUM_USER_AGE", 13)
    if age < minimum:
        raise ValidationError(f"You must be at least {minimum} years old to register.")
    if age > MAX_AGE_YEARS:
        raise ValidationError("Enter a valid date of birth.")
