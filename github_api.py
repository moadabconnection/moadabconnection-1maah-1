"""
ماژول ارتباط با GitHub REST API
----------------------------------
این ماژول تمام تعامل‌های لازم با گیت‌هاب را از طریق GitHub REST API
(Contents API) انجام می‌دهد.

طبق الزامات پروژه:
  - هیچ‌گاه از git clone استفاده نمی‌شود.
  - هیچ‌گاه از git commit استفاده نمی‌شود.
  - هیچ‌گاه از subprocess استفاده نمی‌شود.
  - تمام عملیات صرفاً از طریق درخواست‌های HTTP به GitHub REST API انجام می‌شود.

احراز هویت با استفاده از هدر:
    Authorization: Bearer <TOKEN>
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from utils import decode_base64_to_bytes, encode_content_to_base64

GITHUB_API_BASE_URL = "https://api.github.com"

# تعداد تلاش مجدد در صورت بروز خطای شبکه‌ای موقت
MAX_RETRIES = 3

# فاصله زمانی (ثانیه) بین تلاش‌های مجدد
RETRY_BACKOFF_SECONDS = 2


@dataclass
class RemoteFile:
    """نگهدارنده اطلاعات فایل خوانده‌شده از گیت‌هاب."""

    sha: Optional[str]
    content: bytes
    exists: bool


class GitHubApiError(Exception):
    """خطای عمومی مربوط به تعامل با GitHub REST API."""


class GitHubClient:
    """
    کلاینت سبک برای تعامل با GitHub Contents API.

    این کلاس فقط دو عملیات اصلی را انجام می‌دهد: خواندن فایل فعلی
    و به‌روزرسانی (یا ایجاد) فایل در مخزن گیت‌هاب.
    """

    def __init__(
        self,
        token: str,
        owner: str,
        repository: str,
        branch: str,
        timeout: int,
        logger: logging.Logger,
    ) -> None:
        self._owner = owner
        self._repository = repository
        self._branch = branch
        self._timeout = timeout
        self._logger = logger
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _build_contents_url(self, file_path: str) -> str:
        """ساخت آدرس کامل Contents API برای یک فایل مشخص."""
        return (
            f"{GITHUB_API_BASE_URL}/repos/{self._owner}/"
            f"{self._repository}/contents/{file_path}"
        )

    def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> requests.Response:
        """
        اجرای یک درخواست HTTP با قابلیت تلاش مجدد در برابر خطاهای موقت
        (Timeout و خطاهای اتصال شبکه).

        توجه: این تابع توکن یا محتوای درخواست را در لاگ چاپ نمی‌کند.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self._headers,
                    timeout=self._timeout,
                    **kwargs,
                )
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                self._logger.warning(
                    "[WARN] تلاش شماره %s برای ارتباط با GitHub ناموفق بود. "
                    "دلیل: %s",
                    attempt,
                    type(exc).__name__,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise GitHubApiError(
            f"عدم موفقیت در ارتباط با GitHub پس از {MAX_RETRIES} تلاش."
        ) from last_error

    def get_file(self, file_path: str) -> RemoteFile:
        """
        خواندن محتوای فعلی فایل از مخزن گیت‌هاب.

        اگر فایل هنوز وجود نداشته باشد (HTTP 404)، به‌جای خطا،
        یک RemoteFile با exists=False برگردانده می‌شود تا بار اول
        اجرای برنامه بتواند فایل را ایجاد کند.

        Args:
            file_path: مسیر فایل داخل مخزن (مثلاً "unlimited.txt").

        Returns:
            RemoteFile: اطلاعات فایل فعلی (sha و محتوا).

        Raises:
            GitHubApiError: در صورت خطای غیرمنتظره از سمت GitHub API.
        """
        url = self._build_contents_url(file_path)
        params = {"ref": self._branch}

        response = self._request_with_retry("GET", url, params=params)

        if response.status_code == 404:
            self._logger.info("[INFO] فایل مقصد هنوز در مخزن وجود ندارد؛ برای اولین‌بار ایجاد می‌شود.")
            return RemoteFile(sha=None, content=b"", exists=False)

        if response.status_code != 200:
            raise GitHubApiError(
                f"دریافت فایل از GitHub ناموفق بود. کد وضعیت: {response.status_code}"
            )

        payload = response.json()
        encoded_content = payload.get("content", "")
        sha = payload.get("sha")

        try:
            content = decode_base64_to_bytes(encoded_content)
        except Exception as exc:  # noqa: BLE001 - محتوای نامعتبر باید کنترل‌شده مدیریت شود
            raise GitHubApiError("رمزگشایی محتوای فایل فعلی گیت‌هاب ناموفق بود.") from exc

        return RemoteFile(sha=sha, content=content, exists=True)

    def update_file(
        self,
        file_path: str,
        new_content: bytes,
        current_sha: Optional[str],
        commit_message: str,
    ) -> None:
        """
        به‌روزرسانی (یا ایجاد در صورت نبود) فایل در مخزن گیت‌هاب
        از طریق GitHub Contents API.

        Args:
            file_path: مسیر فایل داخل مخزن.
            new_content: محتوای جدیدی که باید جای‌گزین شود.
            current_sha: هش SHA فایل فعلی (برای فایل جدید باید None باشد).
            commit_message: پیام کامیت مربوط به این تغییر.

        Raises:
            GitHubApiError: اگر GitHub درخواست به‌روزرسانی را رد کند.
        """
        url = self._build_contents_url(file_path)

        body = {
            "message": commit_message,
            "content": encode_content_to_base64(new_content),
            "branch": self._branch,
        }
        if current_sha:
            body["sha"] = current_sha

        response = self._request_with_retry("PUT", url, json=body)

        if response.status_code not in (200, 201):
            raise GitHubApiError(
                f"درخواست به‌روزرسانی توسط GitHub رد شد. کد وضعیت: {response.status_code}"
            )
