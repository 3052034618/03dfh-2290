"""工具函数模块"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def parse_date(date_str: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def parse_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip()
        s = s.replace(",", "").replace("¥", "").replace("￥", "")
        s = s.replace(" ", "")
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def parse_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    try:
        s = str(value).strip()
        s = s.replace(",", "").replace(" ", "")
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def format_amount(amount: float) -> str:
    return f"¥{amount:,.2f}"


def format_date(date: datetime, fmt: str = "%Y-%m-%d") -> str:
    return date.strftime(fmt)


def get_month_range(year: int, month: int) -> Tuple[datetime, datetime]:
    from calendar import monthrange
    start = datetime(year, month, 1)
    _, last_day = monthrange(year, month)
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def find_files_by_pattern(directory: str, pattern: str) -> list:
    results = []
    if not os.path.exists(directory):
        return results
    for root, _, files in os.walk(directory):
        for file in files:
            if re.match(pattern, file, re.IGNORECASE):
                results.append(os.path.join(root, file))
    return results


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename
