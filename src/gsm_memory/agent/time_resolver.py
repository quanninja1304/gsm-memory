"""Relative Date and Time Resolver Tool for GSM Conversational Agent.

Calculates exact ISO date/month/range and human-readable Vietnamese display strings
from natural language relative or absolute time mentions (e.g., 'hôm qua', 'tháng trước',
'tháng vừa rồi', '30 ngày qua', 'tháng 9/2026').
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any


def get_current_ref_datetime(ref: datetime | str | None = None) -> datetime:
    """Return timezone-aware reference datetime (defaults to current system time in GMT+7)."""
    if ref is None:
        # Default to system local time (GMT+7 for Vietnam)
        tz = timezone(timedelta(hours=7))
        return datetime.now(tz)
    if isinstance(ref, str):
        try:
            return datetime.fromisoformat(ref.replace("Z", "+00:00"))
        except Exception:
            tz = timezone(timedelta(hours=7))
            return datetime.now(tz)
    return ref


def resolve_relative_time(
    time_raw: str | None,
    ref_datetime: datetime | str | None = None,
) -> dict[str, Any]:
    """Parse and calculate exact time scope from natural language time string.
    
    Returns a dict with:
        - time_raw: original raw mention
        - time_resolved: standardized ISO key ('2026-09', '2026-10-09', '2026-08', etc.)
        - time_display: human-friendly string ('tháng 09/2026', 'ngày 09/10/2026')
        - date_from: ISO date start ('YYYY-MM-DD')
        - date_to: ISO date end ('YYYY-MM-DD')
        - unit: 'day' | 'month' | 'range' | 'year' | 'unknown'
    """
    if not time_raw or not str(time_raw).strip():
        return {
            "time_raw": None,
            "time_resolved": None,
            "time_display": None,
            "date_from": None,
            "date_to": None,
            "unit": "none",
        }

    raw = str(time_raw).strip()
    q_lower = raw.lower()
    ref = get_current_ref_datetime(ref_datetime)
    curr_year = ref.year
    curr_month = ref.month
    curr_day = ref.day

    # 1. Hôm nay (Today)
    if any(k in q_lower for k in ["hôm nay", "ngày hôm nay", "hôm ni"]):
        d = ref.date()
        iso = d.isoformat()
        return {
            "time_raw": raw,
            "time_resolved": iso,
            "time_display": f"ngày {d.strftime('%d/%m/%Y')}",
            "date_from": iso,
            "date_to": iso,
            "unit": "day",
        }

    # 2. Hôm qua (Yesterday: ref - 1 day -> 09/10/2026)
    if any(k in q_lower for k in ["hôm qua", "ngày hôm qua"]):
        d = (ref - timedelta(days=1)).date()
        iso = d.isoformat()
        return {
            "time_raw": raw,
            "time_resolved": iso,
            "time_display": f"ngày {d.strftime('%d/%m/%Y')}",
            "date_from": iso,
            "date_to": iso,
            "unit": "day",
        }

    # 3. Hôm kia (2 days ago)
    if any(k in q_lower for k in ["hôm kia", "ngày hôm kia"]):
        d = (ref - timedelta(days=2)).date()
        iso = d.isoformat()
        return {
            "time_raw": raw,
            "time_resolved": iso,
            "time_display": f"ngày {d.strftime('%d/%m/%Y')}",
            "date_from": iso,
            "date_to": iso,
            "unit": "day",
        }

    # 4. Tháng trước / Tháng vừa rồi / Tháng rồi (Last month -> 1m offset)
    if any(k in q_lower for k in ["tháng trước", "tháng vừa rồi", "tháng rồi", "tháng vừa qua"]):
        # Calculate prev month
        if curr_month == 1:
            p_year = curr_year - 1
            p_month = 12
        else:
            p_year = curr_year
            p_month = curr_month - 1
        _, last_day = calendar.monthrange(p_year, p_month)
        iso_month = f"{p_year:04d}-{p_month:02d}"
        return {
            "time_raw": raw,
            "time_resolved": iso_month,
            "time_display": f"tháng {p_month:02d}/{p_year:04d}",
            "date_from": f"{iso_month}-01",
            "date_to": f"{iso_month}-{last_day:02d}",
            "unit": "month",
        }

    # 5. Tháng này / Tháng hiện tại
    if any(k in q_lower for k in ["tháng này", "tháng hiện tại", "tháng hiện nay"]):
        _, last_day = calendar.monthrange(curr_year, curr_month)
        iso_month = f"{curr_year:04d}-{curr_month:02d}"
        return {
            "time_raw": raw,
            "time_resolved": iso_month,
            "time_display": f"tháng {curr_month:02d}/{curr_year:04d}",
            "date_from": f"{iso_month}-01",
            "date_to": f"{iso_month}-{last_day:02d}",
            "unit": "month",
        }

    # 6. 30 ngày qua / 30 ngày gần nhất
    if any(k in q_lower for k in ["30 ngày", "30 ngày qua", "30 ngày gần nhất"]):
        d_end = ref.date()
        d_start = (ref - timedelta(days=30)).date()
        return {
            "time_raw": raw,
            "time_resolved": f"{d_start.isoformat()}_to_{d_end.isoformat()}",
            "time_display": f"30 ngày gần nhất ({d_start.strftime('%d/%m/%Y')} - {d_end.strftime('%d/%m/%Y')})",
            "date_from": d_start.isoformat(),
            "date_to": d_end.isoformat(),
            "unit": "range",
        }

    # 7. 7 ngày qua / tuần qua / tuần này
    if any(k in q_lower for k in ["7 ngày", "7 ngày qua", "7 ngày gần nhất"]):
        d_end = ref.date()
        d_start = (ref - timedelta(days=7)).date()
        return {
            "time_raw": raw,
            "time_resolved": f"{d_start.isoformat()}_to_{d_end.isoformat()}",
            "time_display": f"7 ngày gần nhất ({d_start.strftime('%d/%m/%Y')} - {d_end.strftime('%d/%m/%Y')})",
            "date_from": d_start.isoformat(),
            "date_to": d_end.isoformat(),
            "unit": "range",
        }

    # 8. Cụ thể: tháng M/YYYY hoặc tháng M
    m_match = re.search(r"\btháng\s+(\d{1,2})(?:\s*[/-]\s*(\d{4})|\s+năm\s+(\d{4}))?\b", q_lower)
    if m_match:
        m_val = int(m_match.group(1))
        y_val = int(m_match.group(2) or m_match.group(3) or curr_year)
        if 1 <= m_val <= 12:
            _, last_day = calendar.monthrange(y_val, m_val)
            iso_month = f"{y_val:04d}-{m_val:02d}"
            return {
                "time_raw": raw,
                "time_resolved": iso_month,
                "time_display": f"tháng {m_val:02d}/{y_val:04d}",
                "date_from": f"{iso_month}-01",
                "date_to": f"{iso_month}-{last_day:02d}",
                "unit": "month",
            }

    # 9. Cụ thể: ngày DD/MM/YYYY
    d_match = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", raw)
    if d_match:
        day_v = int(d_match.group(1))
        mon_v = int(d_match.group(2))
        yr_v = int(d_match.group(3))
        try:
            d_obj = date(yr_v, mon_v, day_v)
            iso_d = d_obj.isoformat()
            return {
                "time_raw": raw,
                "time_resolved": iso_d,
                "time_display": f"ngày {d_obj.strftime('%d/%m/%Y')}",
                "date_from": iso_d,
                "date_to": iso_d,
                "unit": "day",
            }
        except Exception:
            pass

    # 10. Năm: năm YYYY
    y_match = re.search(r"\bnăm\s+(\d{4})\b", q_lower)
    if y_match:
        yr_v = int(y_match.group(1))
        return {
            "time_raw": raw,
            "time_resolved": f"{yr_v:04d}",
            "time_display": f"năm {yr_v:04d}",
            "date_from": f"{yr_v:04d}-01-01",
            "date_to": f"{yr_v:04d}-12-31",
            "unit": "year",
        }

    # Fallback: keep raw as display
    return {
        "time_raw": raw,
        "time_resolved": None,
        "time_display": raw,
        "date_from": None,
        "date_to": None,
        "unit": "unknown",
    }


def extract_time_from_text(
    text: str | None,
    ref_datetime: datetime | str | None = None,
) -> dict[str, Any]:
    """Scan natural language text to dynamically extract and resolve temporal phrases."""
    if not text or not str(text).strip():
        return {
            "time_raw": None,
            "time_resolved": None,
            "time_display": None,
            "date_from": None,
            "date_to": None,
            "unit": "none",
        }

    t_lower = text.lower()

    # Priority 1: Exact date DD/MM/YYYY or DD-MM-YYYY
    d_match = re.search(r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})\b", text)
    if d_match:
        return resolve_relative_time(d_match.group(1), ref_datetime)

    # Priority 2: Month expressions: tháng M/YYYY, tháng M-YYYY, tháng M
    m_match = re.search(r"\b(tháng\s+\d{1,2}(?:\s*[/-]\s*\d{4}|\s+năm\s+\d{4})?)\b", t_lower)
    if m_match:
        return resolve_relative_time(m_match.group(1), ref_datetime)

    # Priority 3: Common relative time expressions
    for expr in [
        "hôm nay", "ngày hôm nay",
        "hôm qua", "ngày hôm qua",
        "hôm kia",
        "tháng trước", "tháng vừa rồi", "tháng rồi", "tháng vừa qua",
        "tháng này", "tháng hiện tại",
        "30 ngày qua", "30 ngày gần nhất", "30 ngày",
        "7 ngày qua", "7 ngày gần nhất", "tuần này", "tuần qua",
    ]:
        if expr in t_lower:
            return resolve_relative_time(expr, ref_datetime)

    # Priority 4: Year expressions: năm YYYY
    y_match = re.search(r"\b(năm\s+\d{4})\b", t_lower)
    if y_match:
        return resolve_relative_time(y_match.group(1), ref_datetime)

    return {
        "time_raw": None,
        "time_resolved": None,
        "time_display": None,
        "date_from": None,
        "date_to": None,
        "unit": "none",
    }
