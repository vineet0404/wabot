import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

PREFIX = "enc::"


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


class EncryptedTextField(models.TextField):
    """Database me encrypted (Fernet) text. Code me normal text jaisa dikhta hai.

    DB leak ya backup chori ho jaye, tab bhi bina FIELD_ENCRYPTION_KEY ke token nahi padhega.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value or value.startswith(PREFIX):
            return value
        return PREFIX + _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        if not value.startswith(PREFIX):
            return value  # purana plain text, agle save par encrypt ho jayega
        try:
            return _fernet().decrypt(value.removeprefix(PREFIX).encode()).decode()
        except InvalidToken:
            logger.error("Token decrypt nahi hua: FIELD_ENCRYPTION_KEY badli hui lagti hai")
            return ""
