"""
ماژول توابع کمکی (Utils)
--------------------------
این ماژول شامل توابع مشترکی است که در بخش‌های مختلف پروژه
(اعتبارسنجی محتوا، محاسبه هش و ...) استفاده می‌شوند.
"""

from __future__ import annotations

import base64
import hashlib

# حداقل طول قابل قبول برای محتوای اشتراک (بایت).
# هر محتوایی کوچک‌تر از این مقدار، مشکوک به خالی/ناقص بودن است.
MIN_VALID_CONTENT_LENGTH = 20


def calculate_sha256(content: bytes) -> str:
    """
    محاسبه هش SHA256 برای یک محتوای باینری.

    Args:
        content: محتوای ورودی به‌صورت bytes.

    Returns:
        str: رشته هگزادسیمال هش SHA256.
    """
    return hashlib.sha256(content).hexdigest()


def is_valid_subscription_content(content: bytes) -> bool:
    """
    اعتبارسنجی محتوای دریافتی از سابسکریپشن پاسارگاد.

    این تابع بررسی می‌کند که محتوا:
      - خالی نباشد.
      - از حداقل طول مجاز کمتر نباشد.
      - صرفاً شامل فضای خالی (whitespace) نباشد.
      - قابل رمزگشایی به‌صورت متن UTF-8 باشد (بدون کرش کردن برنامه).

    Args:
        content: محتوای دریافتی از درخواست HTTP.

    Returns:
        bool: True اگر محتوا معتبر تشخیص داده شود، در غیر این صورت False.
    """
    if content is None:
        return False

    if len(content) < MIN_VALID_CONTENT_LENGTH:
        return False

    try:
        decoded_text = content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False

    if not decoded_text:
        return False

    return True


def encode_content_to_base64(content: bytes) -> str:
    """
    تبدیل محتوای باینری به رشته base64 (فرمت مورد نیاز GitHub Contents API).

    Args:
        content: محتوای خام به‌صورت bytes.

    Returns:
        str: محتوای رمزگذاری‌شده با base64.
    """
    return base64.b64encode(content).decode("utf-8")


def decode_base64_to_bytes(encoded_content: str) -> bytes:
    """
    تبدیل رشته base64 دریافتی از GitHub به محتوای باینری اصلی.

    Args:
        encoded_content: رشته base64 (ممکن است شامل خطوط جدید باشد).

    Returns:
        bytes: محتوای اصلی پس از رمزگشایی.
    """
    return base64.b64decode(encoded_content)
