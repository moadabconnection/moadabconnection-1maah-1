#!/usr/bin/env python3
"""
sync.py
--------
نقطه ورود اصلی سرویس همگام‌سازی سابسکریپشن پاسارگاد با گیت‌هاب.

جریان کار (Workflow):
    ۱. دانلود محتوای سابسکریپشن از URL ثابت پاسارگاد.
    ۲. اعتبارسنجی محتوای دریافتی.
    ۳. خواندن محتوای فعلی فایل از مخزن گیت‌هاب.
    ۴. مقایسه هش SHA256 محتوای جدید و قدیم.
    ۵. در صورت تغییر، به‌روزرسانی فایل روی گیت‌هاب از طریق REST API.

این اسکریپت برای اجرای دوره‌ای (مثلاً از طریق cron) طراحی شده و
در هیچ شرایطی — حتی در صورت بروز خطای غیرمنتظره — نباید با کرش کامل
(traceback خام) متوقف شود؛ همه‌ی خطاها کنترل‌شده لاگ می‌شوند.
"""

from __future__ import annotations

import sys

import requests

from config import Settings, load_settings
from github_api import GitHubApiError, GitHubClient
from logger import get_logger
from utils import calculate_sha256, is_valid_subscription_content

logger = get_logger()


def download_subscription(url: str, timeout: int) -> bytes:
    """
    دانلود محتوای سابسکریپشن پاسارگاد با قابلیت تلاش مجدد.

    Args:
        url: آدرس اشتراک پاسارگاد (هرگز در لاگ چاپ نمی‌شود).
        timeout: حداکثر زمان انتظار برای هر درخواست (ثانیه).

    Returns:
        bytes: محتوای خام دریافتی از سرور.

    Raises:
        RuntimeError: اگر پس از تمام تلاش‌ها، دانلود ناموفق بماند.
    """
    max_attempts = 3
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.exceptions.Timeout as exc:
            last_error = exc
            logger.error("[ERROR] Timeout در دانلود سابسکریپشن (تلاش %s از %s).", attempt, max_attempts)
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            logger.error("[ERROR] خطای اتصال شبکه هنگام دانلود سابسکریپشن (تلاش %s از %s).", attempt, max_attempts)
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            logger.error(
                "[ERROR] HTTP Error در دانلود سابسکریپشن. کد وضعیت: %s (تلاش %s از %s).",
                response.status_code,
                attempt,
                max_attempts,
            )
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.error("[ERROR] خطای غیرمنتظره در درخواست شبکه (تلاش %s از %s).", attempt, max_attempts)

    raise RuntimeError("دانلود سابسکریپشن پاسارگاد پس از چند تلاش ناموفق بود.") from last_error


def run_sync(settings: Settings) -> int:
    """
    اجرای کامل یک چرخه همگام‌سازی.

    Args:
        settings: تنظیمات بارگذاری‌شده از .env.

    Returns:
        int: کد خروجی مناسب برای استفاده در سیستم (۰ = موفق، ۱ = خطا).
    """
    logger.info("[INFO] شروع فرآیند همگام‌سازی...")

    # مرحله ۱: دانلود سابسکریپشن پاسارگاد
    logger.info("[INFO] در حال دانلود سابسکریپشن پاسارگاد...")
    try:
        new_content = download_subscription(settings.passargad_sub_url, settings.timeout)
    except RuntimeError:
        logger.error("[ERROR] دانلود سابسکریپشن پاسارگاد ناموفق بود. فرآیند متوقف شد.")
        return 1

    logger.info("[INFO] سابسکریپشن با موفقیت دانلود شد.")

    # مرحله ۲: اعتبارسنجی محتوای دریافتی
    if not is_valid_subscription_content(new_content):
        logger.error("[ERROR] محتوای سابسکریپشن نامعتبر یا خالی است. آپلود متوقف شد.")
        return 1

    # مرحله ۳: اتصال به گیت‌هاب و خواندن فایل فعلی
    github_client = GitHubClient(
        token=settings.github_token,
        owner=settings.github_owner,
        repository=settings.github_repository,
        branch=settings.github_branch,
        timeout=settings.timeout,
        logger=logger,
    )

    try:
        remote_file = github_client.get_file(settings.github_file)
    except GitHubApiError:
        logger.error("[ERROR] GitHub API رد کرد / خواندن فایل فعلی ناموفق بود.")
        return 1

    # مرحله ۴: مقایسه هش SHA256
    logger.info("[INFO] در حال بررسی SHA256...")
    new_hash = calculate_sha256(new_content)
    current_hash = calculate_sha256(remote_file.content) if remote_file.exists else None

    if remote_file.exists and new_hash == current_hash:
        logger.info("[INFO] هیچ تغییری یافت نشد.")
        return 0

    logger.info("[INFO] تغییرات شناسایی شد.")

    # مرحله ۵: آپلود محتوای جدید به گیت‌هاب
    logger.info("[INFO] در حال آپلود به GitHub...")
    try:
        github_client.update_file(
            file_path=settings.github_file,
            new_content=new_content,
            current_sha=remote_file.sha,
            commit_message="chore: به‌روزرسانی خودکار سابسکریپشن",
        )
    except GitHubApiError:
        logger.error("[ERROR] GitHub API درخواست به‌روزرسانی را رد کرد.")
        return 1

    logger.info("[SUCCESS] سابسکریپشن گیت‌هاب با موفقیت به‌روزرسانی شد.")
    logger.info("[SUCCESS] همگام‌سازی با موفقیت انجام شد.")
    return 0


def main() -> None:
    """نقطه ورود برنامه هنگام اجرای مستقیم اسکریپت."""
    try:
        settings = load_settings()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - هر خطای غیرمنتظره در پیکربندی باید کنترل‌شده مدیریت شود
        logger.error("[ERROR] بارگذاری تنظیمات از .env ناموفق بود.")
        sys.exit(1)

    try:
        exit_code = run_sync(settings)
    except Exception:  # noqa: BLE001 - برنامه هرگز نباید با traceback خام متوقف شود
        logger.error("[ERROR] یک خطای غیرمنتظره در فرآیند همگام‌سازی رخ داد.", exc_info=True)
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
