import re
from config import Config


def validate_isik_email(email):
    if not email:
        return False

    if email.endswith('@isik.edu.tr'):
        return True

    if email.endswith('@isikun.edu.tr'):
        return True

    return False


def is_admin_email(email):
    return email == Config.ADMIN_EMAIL