"""
ماژول لاگ‌گیری (Logger)
-------------------------
این ماژول یک logger استاندارد برای کل پروژه فراهم می‌کند که هم در
کنسول و هم در فایل logs/sync.log خروجی می‌نویسد.

نکته امنیتی مهم: این ماژول هرگز نباید مقادیر حساس (توکن گیت‌هاب،
آدرس اشتراک پاسارگاد و ...) را لاگ کند. مسئولیت رعایت این نکته
در تمام فراخوانی‌های logger در سراسر پروژه رعایت شده است.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "sync.log")


def get_logger(name: str = "subsync") -> logging.Logger:
    """
    ساخت و پیکربندی یک logger با خروجی همزمان به کنسول و فایل.

    Args:
        name: نام logger (پیش‌فرض: "subsync").

    Returns:
        logging.Logger: نمونه آماده برای استفاده در سایر ماژول‌ها.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)

    # جلوگیری از اضافه شدن چندباره‌ی handler در صورت فراخوانی مکرر این تابع
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # خروجی به کنسول
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # خروجی به فایل با چرخش خودکار (حداکثر ۵ فایل، هر کدام ۲ مگابایت)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    return logger
