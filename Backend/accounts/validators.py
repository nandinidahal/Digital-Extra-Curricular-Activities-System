import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{7,15}$",
    message="Enter a valid phone number (7-15 digits, optional leading +).",
)


class PasswordComplexityValidator:
    """Require upper, lower, digit and special character."""

    def validate(self, password, user=None):
        problems = []
        if not re.search(r"[A-Z]", password):
            problems.append("an uppercase letter")
        if not re.search(r"[a-z]", password):
            problems.append("a lowercase letter")
        if not re.search(r"\d", password):
            problems.append("a digit")
        if not re.search(r"[^\w\s]|_", password):
            problems.append("a special character")
        if problems:
            raise ValidationError(
                "Password must contain " + ", ".join(problems) + ".",
                code="password_too_simple",
            )

    def get_help_text(self):
        return "Your password must contain upper and lower case letters, a digit and a special character."


def validate_date_of_birth(value):
    today = date.today()
    if value >= today:
        raise ValidationError("Date of birth must be in the past.")
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 13:
        raise ValidationError("You must be at least 13 years old to register.")
    if age > 120:
        raise ValidationError("Enter a valid date of birth.")
