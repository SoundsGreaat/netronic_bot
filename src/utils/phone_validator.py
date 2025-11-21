import re


def normalize_phone_number(phone_text: str) -> str | None:
    if not phone_text:
        return None

    phone = phone_text.strip()

    if phone.startswith('+'):
        clear_number = re.sub(r'[^\d+]', '', phone)
        return clear_number if len(clear_number) > 1 else None

    digits_only = re.sub(r'\D', '', phone)

    ua_match = re.match(r'^3?8?(0\d{9})$', digits_only)
    if ua_match:
        return '+380' + ua_match.group(1)[1:]

    if len(digits_only) >= 10:
        return '+' + digits_only

    return None
