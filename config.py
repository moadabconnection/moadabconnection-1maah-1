"""
ماژول تنظیمات (Config)
------------------------
این ماژول مسئول خواندن تمام متغیرهای محیطی مورد نیاز پروژه از فایل .env است.
هیچ مقدار حساسی (مثل توکن گیت‌هاب یا آدرس اشتراک پاسارگاد) به‌صورت مستقیم
در کد نوشته نشده و همه چیز از طریق dotenv بارگذاری می‌شود.

اگر یکی از متغیرهای اجباری در .env موجود نباشد، برنامه با پیام خطای واضح
متوقف می‌شود تا از اجرای ناقص یا ناامن جلوگیری شود.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env در همان مسیر پروژه
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    کلاس نگهدارنده تمام تنظیمات برنامه.

    این کلاس به‌صورت immutable (تغییرناپذیر) طراحی شده تا در طول اجرای
    برنامه هیچ بخشی از کد نتواند مقادیر تنظیمات را به‌اشتباه تغییر دهد.
    """

    passargad_sub_url: str
    github_token: str
    github_owner: str
    github_repository: str
    github_branch: str
    github_file: str
    timeout: int


def _get_required_env(name: str) -> str:
    """
    خواندن یک متغیر محیطی اجباری.

    اگر متغیر خواسته‌شده وجود نداشته باشد یا خالی باشد، برنامه با
    پیام خطای مشخص متوقف می‌شود. توجه: مقدار خود متغیر هرگز در پیام
    خطا چاپ نمی‌شود تا اطلاعات حساس (مثل توکن) فاش نشود.
    """
    value = os.getenv(name)
    if not value or not value.strip():
        sys.stderr.write(
            f"[ERROR] متغیر محیطی اجباری '{name}' در فایل .env تعریف نشده است.\n"
        )
        sys.exit(1)
    return value.strip()


def load_settings() -> Settings:
    """
    بارگذاری و ساخت شیء Settings از متغیرهای محیطی.

    Returns:
        Settings: شیء حاوی تمام مقادیر پیکربندی مورد نیاز.
    """
    timeout_raw = os.getenv("TIMEOUT", "15")
    try:
        timeout = int(timeout_raw)
    except ValueError:
        sys.stderr.write("[ERROR] مقدار TIMEOUT باید یک عدد صحیح باشد.\n")
        sys.exit(1)

    return Settings(
        passargad_sub_url=_get_required_env("PASSARGAD_SUB_URL"),
        github_token=_get_required_env("GITHUB_TOKEN"),
        github_owner=_get_required_env("GITHUB_OWNER"),
        github_repository=_get_required_env("GITHUB_REPOSITORY"),
        github_branch=os.getenv("GITHUB_BRANCH", "main").strip() or "main",
        github_file=os.getenv("GITHUB_FILE", "unlimited.txt").strip() or "unlimited.txt",
        timeout=timeout,
    )
