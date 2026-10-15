"""GSM Operations & Policy Evaluation Tools Suite.

Provides deterministic arithmetic (acceptance rate, completion rate, cancellation rate,
revenue charge), operational metrics retrieval, database queries, knowledge graph
traversal, and GSM policy search.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable


# =============================================================================
# 1. DETERMINISTIC COMPUTATION TOOLS (Based on GSM Work Standards & Schema)
# =============================================================================


def calculate_acceptance_rate(
    offered_trips: int,
    accepted_trips: int,
    threshold_pct: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính tỷ lệ nhận cuốc (Acceptance Rate - AR) chuẩn xác số học (AR = accepted / offered).

    Trả về tỷ lệ dưới dạng phân số và phần trăm chuẩn xác.
    Việc so sánh đối chiếu với quy chế do Agent thực hiện dựa trên quy định từ search_gsm_policies.
    """
    if offered_trips <= 0:
        return {
            "tool": "calculate_acceptance_rate",
            "error": "Số cuốc phát (offered_trips) phải lớn hơn 0.",
            "metric_status": "undefined",
            "rate_fraction": "0/0",
            "rate_pct": 0.0,
            "passed": False,
        }

    accepted = max(0, min(int(accepted_trips), int(offered_trips)))
    frac = Fraction(accepted, int(offered_trips))
    rate_pct = round(float(frac) * 100.0, 2)

    passed = None
    if threshold_pct is not None:
        thresh_frac = Fraction(str(threshold_pct)) / 100
        passed = frac >= thresh_frac
        thresh_val = float(threshold_pct)
        summary = (
            f"Tỷ lệ nhận cuốc (AR): {rate_pct}% ({accepted}/{offered_trips} cuốc = {frac.numerator}/{frac.denominator}). "
            f"Ngưỡng đối chiếu: >= {thresh_val}%. "
            f"Kết quả: {'ĐẠT' if passed else f'KHÔNG ĐẠT (thiếu {round(thresh_val - rate_pct, 2)}%)'}."
        )
    else:
        summary = f"Tỷ lệ nhận cuốc (AR): {rate_pct}% ({accepted}/{offered_trips} cuốc = {frac.numerator}/{frac.denominator})."

    return {
        "tool": "calculate_acceptance_rate",
        "offered_trips": int(offered_trips),
        "accepted_trips": accepted,
        "rate_fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_pct": rate_pct,
        "threshold_pct": threshold_pct,
        "passed": passed,
        "summary": summary,
    }


def calculate_completion_rate(
    accepted_trips: int,
    completed_trips: int,
    threshold_pct: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính tỷ lệ hoàn thành cuốc (Completion Rate - CR) chuẩn xác số học (CR = completed / accepted).

    Trả về tỷ lệ dưới dạng phân số và phần trăm chuẩn xác.
    Việc so sánh đối chiếu với quy chế do Agent thực hiện dựa trên quy định từ search_gsm_policies.
    """
    if accepted_trips <= 0:
        return {
            "tool": "calculate_completion_rate",
            "error": "Số cuốc nhận (accepted_trips) phải lớn hơn 0.",
            "metric_status": "undefined",
            "rate_fraction": "0/0",
            "rate_pct": 0.0,
            "passed": False,
        }

    completed = max(0, min(int(completed_trips), int(accepted_trips)))
    frac = Fraction(completed, int(accepted_trips))
    rate_pct = round(float(frac) * 100.0, 2)

    passed = None
    if threshold_pct is not None:
        thresh_frac = Fraction(str(threshold_pct)) / 100
        passed = frac >= thresh_frac
        thresh_val = float(threshold_pct)
        summary = (
            f"Tỷ lệ hoàn thành cuốc (CR): {rate_pct}% ({completed}/{accepted_trips} cuốc = {frac.numerator}/{frac.denominator}). "
            f"Ngưỡng đối chiếu: >= {thresh_val}%. "
            f"Kết quả: {'ĐẠT' if passed else f'KHÔNG ĐẠT (thiếu {round(thresh_val - rate_pct, 2)}%)'}."
        )
    else:
        summary = f"Tỷ lệ hoàn thành cuốc (CR): {rate_pct}% ({completed}/{accepted_trips} cuốc = {frac.numerator}/{frac.denominator})."

    return {
        "tool": "calculate_completion_rate",
        "accepted_trips": int(accepted_trips),
        "completed_trips": completed,
        "rate_fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_pct": rate_pct,
        "threshold_pct": threshold_pct,
        "passed": passed,
        "summary": summary,
    }



def normalize_date_prefix(date: Any) -> tuple[str, str]:
    """Normalize arbitrary date or month string (e.g. '2026-08', '08/2026', 'tháng 08/2026', '15/08/2026')
    to (date_prefix, period_label).
    date_prefix is an ISO prefix ('YYYY-MM-DD', 'YYYY-MM', or 'YYYY') suitable for string matching with ISO timestamps.
    """
    if not date:
        return "", ""
    s = str(date).strip()
    if not s or "snapshot" in s.lower() or "toàn kỳ" in s.lower() or s.lower() in ("none", "null"):
        return "", s

    # 1. Matches DD/MM/YYYY or DD-MM-YYYY
    m_dmy = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", s)
    if m_dmy:
        d, m, y = m_dmy.groups()
        iso = f"{y}-{int(m):02d}-{int(d):02d}"
        return iso, f"Ngày {iso}"

    # 2. Matches YYYY-MM-DD or YYYY/MM/DD
    m_ymd = re.search(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b", s)
    if m_ymd:
        y, m, d = m_ymd.groups()
        iso = f"{y}-{int(m):02d}-{int(d):02d}"
        return iso, f"Ngày {iso}"

    # 3. Matches MM/YYYY or tháng MM/YYYY or MM-YYYY
    m_my = re.search(r"(?:tháng\s*)?(\d{1,2})[/-](\d{4})\b", s, re.IGNORECASE)
    if m_my:
        m, y = m_my.groups()
        iso = f"{y}-{int(m):02d}"
        return iso, f"Tháng {iso}"

    # 4. Matches YYYY-MM or YYYY/MM
    m_ym = re.search(r"\b(\d{4})[/-](\d{1,2})\b", s)
    if m_ym:
        y, m = m_ym.groups()
        iso = f"{y}-{int(m):02d}"
        return iso, f"Tháng {iso}"

    # 5. Matches 4-digit year like 2026
    m_y = re.search(r"\b(20\d{2})\b", s)
    if m_y:
        y = m_y.group(1)
        return y, f"Năm {y}"

    return s[:10], f"Thời gian {s[:10]}"


def evaluate_daily_revenue(
    revenue_vnd: int | None = None,
    threshold_vnd: int | None = None,
    date: str | None = None,
    driver_id: str | None = None,
    snapshot_id: str | None = None,
    db_repo: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Kiểm tra và đánh giá doanh số (doanh thu) của tài xế theo ngày (YYYY-MM-DD), tháng (YYYY-MM) và snapshot so với định mức (threshold_vnd) từ quy chế.

    Nếu không truyền revenue_vnd (hoặc <= 0), hệ thống sẽ tự động tra cứu doanh thu thực tế từ CSDL
    theo driver_id, date và snapshot_id. Nếu có threshold_vnd, đối chiếu đạt/không đạt chuẩn xác.
    """
    rev = 0
    driver = None
    date_prefix, period_label = normalize_date_prefix(date)

    if revenue_vnd is not None and int(revenue_vnd) > 0:
        rev = int(revenue_vnd)
        source = "input"
    elif db_repo and driver_id:
        driver = db_repo.get_driver(driver_id) or db_repo.find_driver_in_text(driver_id)
        if driver:
            try:
                trips = []
                if hasattr(db_repo, "get_trips"):
                    try:
                        trips = db_repo.get_trips(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=2000)
                    except TypeError:
                        trips = db_repo.get_trips(driver_id=driver.driver_id, limit=2000)
                if isinstance(trips, list):
                    if date_prefix:
                        trips = [t for t in trips if (getattr(t, "start_time", "") or "").startswith(date_prefix)]
                    rev = sum(getattr(t, "fare_amount", 0) for t in trips if getattr(t, "outcome", "") == "completed")
                source = "db_trips"
            except Exception:
                rev = 0
                source = "default"
        else:
            rev = 0
            source = "not_found"
    else:
        rev = int(revenue_vnd or 0)
        source = "default"

    diff_vnd = None
    passed = None
    driver_str = f" của tài xế {driver.full_name} ({driver.driver_code})" if driver else (f" của tài xế {driver_id}" if driver_id else "")
    date_str = f" ({period_label})" if period_label else (f" ngày {date}" if date else "")
    snap_str = f" [Snapshot: {snapshot_id[:8]}...]" if snapshot_id else ""

    if threshold_vnd is not None:
        thresh_val = int(threshold_vnd)
        passed = rev >= thresh_val
        diff_vnd = rev - thresh_val
        summary = (
            f"Doanh số ghi nhận{driver_str}{date_str}{snap_str}: {rev:,.0f} VNĐ. "
            f"Định mức quy chế yêu cầu: {thresh_val:,.0f} VNĐ. "
            f"Kết quả: {'ĐẠT ĐỊNH MỨC' if passed else f'KHÔNG ĐẠT (thiếu {abs(diff_vnd):,.0f} VNĐ)'}."
        )
    else:
        summary = f"Doanh số ghi nhận{driver_str}{date_str}{snap_str}: {rev:,.0f} VNĐ."

    return {
        "tool": "evaluate_daily_revenue",
        "driver_id": driver.driver_id if driver else driver_id,
        "date": date_prefix if date else None,
        "snapshot_id": snapshot_id,
        "revenue_vnd": rev,
        "threshold_vnd": threshold_vnd,
        "diff_vnd": diff_vnd,
        "passed": passed,
        "source": source,
        "summary": summary,
    }



def calculate_cancel_rate(
    cancelled_trips: int | None = None,
    total_trips: int | None = None,
    completed_trips: int | None = None,
    threshold_pct: float | None = None,
    driver_identifier: str | None = None,
    snapshot_id: str | None = None,
    date: str | None = None,
    db_repo: Any = None,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính tỷ lệ hủy chuyến chuẩn xác số học theo definition M01 (cancel_rate_30d).

    Hỗ trợ tự động đối soát và đồng bộ số liệu thực tế từ CSDL theo driver_identifier và snapshot_id nếu có.
    Hỗ trợ tự động tính total_trips = cancelled_trips + completed_trips nếu total_trips không được truyền hoặc <= 0.
    Hỗ trợ đối chiếu ngưỡng tối đa cho phép theo quy chế (threshold_pct) nếu có.
    """
    verified_from_db = False
    driver_ident = driver_identifier or kwargs.get("driver_id")
    if db_repo and driver_ident:
        try:
            summary_data = get_driver_trip_summary(
                db_repo=db_repo,
                driver_identifier=driver_ident,
                snapshot_id=snapshot_id or kwargs.get("target_snap"),
                date=date,
                pipeline=pipeline,
            )
            if summary_data.get("found"):
                db_total = summary_data.get("total_trips_count", 0)
                db_canc = summary_data.get("cancelled_trips_count", 0)
                if db_total == 0 and summary_data.get("snapshot_total_trips", 0) > 0:
                    db_total = summary_data.get("snapshot_total_trips", 0)
                    db_canc = summary_data.get("snapshot_cancelled_trips", 0)
                if db_total > 0:
                    # If caller didn't pass valid numbers or passed numbers differing from DB, use DB authoritative numbers
                    if total_trips is None or int(total_trips) <= 0 or (cancelled_trips is not None and int(cancelled_trips) != db_canc):
                        cancelled_trips = db_canc
                        total_trips = db_total
                        completed_trips = db_total - db_canc
                        verified_from_db = True
        except Exception:
            pass

    c_trips = max(0, int(cancelled_trips or 0))
    if (total_trips is None or int(total_trips) <= 0) and completed_trips is not None:
        tot_trips = c_trips + max(0, int(completed_trips))
    else:
        tot_trips = int(total_trips or 0)

    if tot_trips <= 0:
        return {
            "tool": "calculate_cancel_rate",
            "metric_status": "undefined",
            "cancel_rate": None,
            "cancelled_trips": c_trips,
            "completed_trips": 0,
            "total_trips": 0,
            "fraction": "0/0",
            "rate_fraction": "0/0",
            "rate_pct": 0.0,
            "threshold_pct": threshold_pct,
            "passed": False,
            "summary": "Tỷ lệ hủy chuyến (cancel_rate_30d): undefined (mẫu số bằng 0 do không có chuyến đi nào được ghi nhận trong kỳ).",
        }

    cancelled = max(0, min(c_trips, tot_trips))
    frac = Fraction(cancelled, tot_trips)
    pct = round(float(frac) * 100.0, 2)

    passed = None
    db_note = " (Số liệu được xác thực trực tiếp từ CSDL hệ thống)" if verified_from_db else ""
    if threshold_pct is not None:
        thresh_frac = Fraction(str(threshold_pct)) / 100
        passed = frac <= thresh_frac
        thresh_val = float(threshold_pct)
        res_text = "ĐẠT QUY CHẾ (không vượt mức trần cho phép)" if passed else f"VƯỢT TRẦN QUY CHẾ (vượt mức trần {round(pct - thresh_val, 2)}%)"
        summary = (
            f"Tỷ lệ hủy chuyến (cancel_rate_30d): {pct}% ({cancelled}/{tot_trips} chuyến = {frac.numerator}/{frac.denominator}){db_note}. "
            f"Ngưỡng trần quy chế: <= {thresh_val}%. "
            f"Kết quả: {res_text}."
        )
    else:
        summary = f"Tỷ lệ hủy chuyến (cancel_rate_30d) = {frac.numerator}/{frac.denominator} ({cancelled}/{tot_trips} chuyến) = {pct}%{db_note}."

    return {
        "tool": "calculate_cancel_rate",
        "metric_status": "valid",
        "cancelled_trips": cancelled,
        "completed_trips": tot_trips - cancelled,
        "total_trips": tot_trips,
        "fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_pct": pct,
        "threshold_pct": threshold_pct,
        "passed": passed,
        "verified_from_db": verified_from_db,
        "summary": summary,
    }


def evaluate_rating_condition(
    rating_stars: float,
    threshold: float | None = None,
    operator: str = ">=",
    **kwargs: Any,
) -> dict[str, Any]:
    """Kiểm tra điều kiện đánh giá sao của tài xế.

    Nếu có ngưỡng threshold (tra cứu từ văn bản quy chế), hàm sẽ đối chiếu chính xác
    với toán tử mong muốn (mặc định '>='). Nếu không truyền threshold, hàm trả về
    số liệu rating chuẩn hóa mà không tự so sánh với bất kỳ ngưỡng nào.
    Bảo toàn chuẩn so sánh exact rational (ví dụ 4.85 tương đương 97/20).
    """
    rating_clean = round(float(rating_stars), 2)
    passed = None
    if threshold is not None:
        thresh_val = float(threshold)
        r_frac = Fraction(str(round(float(rating_stars), 4)))
        t_frac = Fraction(str(threshold))
        if operator == ">":
            passed = r_frac > t_frac
        elif operator == "<":
            passed = r_frac < t_frac
        elif operator == "<=":
            passed = r_frac <= t_frac
        else:
            passed = r_frac >= t_frac

        summary = f"Đánh giá sao: {rating_clean:.2f}/5.0 (Ngưỡng quy chế: {operator} {thresh_val}) -> {'ĐẠT ĐIỀU KIỆN' if passed else 'KHÔNG ĐẠT'}."
    else:
        summary = f"Đánh giá sao ghi nhận: {rating_clean:.2f}/5.0★. (Chưa cung cấp ngưỡng quy chế để đối chiếu)."

    return {
        "tool": "evaluate_rating_condition",
        "rating_stars": rating_clean,
        "threshold": threshold,
        "operator": operator if threshold is not None else None,
        "passed": passed,
        "summary": summary,
    }


def calculate_revenue_charge(
    revenue_vnd: int,
    program: str | None = None,
    operating_region: str | None = None,
    is_operating_day: bool | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính khoản giảm trừ/phí bù doanh thu theo công thức chuẩn P154 / Task T02: max(280_000 - revenue_vnd, 0) // 5.

    Hỗ trợ kiểm tra các điều kiện tiên quyết của quy chế P154:
    - Chương trình: Đối tác xe máy (bike_partner / GSM Bike).
    - Vùng hoạt động: Hà Nội.
    - Ngày vận doanh: RM_OPDAY = True.
    """
    rev = max(0, int(revenue_vnd))

    # Check prerequisites if provided
    applicable = True
    inapplicable_reasons = []
    if program is not None and str(program).lower() not in ("bike_partner", "bike", "xanh bike", "xe máy"):
        applicable = False
        inapplicable_reasons.append(f"chương trình '{program}' không thuộc diện áp dụng (chỉ áp dụng bike_partner)")
    if operating_region is not None and "hà nội" not in str(operating_region).lower() and "hn" not in str(operating_region).lower():
        applicable = False
        inapplicable_reasons.append(f"khu vực '{operating_region}' ngoài địa bàn Hà Nội")
    if is_operating_day is not None and not is_operating_day:
        applicable = False
        inapplicable_reasons.append("không phải ngày vận doanh tiêu chuẩn (RM_OPDAY=False)")

    if not applicable:
        return {
            "tool": "calculate_revenue_charge",
            "revenue_vnd": rev,
            "charge_vnd": 0,
            "applicable": False,
            "verdict": "not_applicable",
            "reasons": inapplicable_reasons,
            "summary": f"Không áp dụng thu giảm trừ bù doanh thu ({'; '.join(inapplicable_reasons)}).",
        }

    charge = max(280_000 - rev, 0) // 5
    if charge == 0:
        summary = f"Doanh số {rev:,.0f} VNĐ đạt/vượt mức chuẩn 280,000 VNĐ. Mức giảm trừ bảo lưu doanh thu: 0 VNĐ."
    else:
        summary = f"Mức giảm trừ bảo lưu doanh thu: {charge:,.0f} VNĐ (từ doanh thu {rev:,.0f} VNĐ, thiếu {280_000 - rev:,.0f} VNĐ so với định mức 280,000 VNĐ, trích 20%)."

    return {
        "tool": "calculate_revenue_charge",
        "revenue_vnd": rev,
        "charge_vnd": charge,
        "applicable": True,
        "verdict": "applied",
        "summary": summary,
    }


def calculate_violation_penalty_points(
    points: int | list[int] = 0,
    violation_count: int | None = None,
    rule_codes: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính tổng điểm phạt tích lũy từ các vi phạm và xác định biện pháp chế tài theo quy chế GSM.

    Thang chế tài chuẩn:
    - 0 điểm: Hoạt động bình thường.
    - 1 - 9 điểm: Nhắc nhở nghiệp vụ (Reminder).
    - 10 - 19 điểm: Cảnh cáo & trừ điểm thi đua (Formal Warning).
    - 20 - 29 điểm: Tạm đình chỉ hoạt động / Đào tạo lại nghiệp vụ 3-7 ngày (Temporary Suspension / Retraining).
    - >= 30 điểm: Chế tài mức cao nhất / Xem xét chấm dứt hợp đồng hợp tác (Contract Termination Review).
    """
    total_pts = 0
    if isinstance(points, list):
        total_pts = sum(int(p) for p in points)
    else:
        total_pts = max(0, int(points or 0))

    if total_pts == 0:
        tier = "Bình thường"
        action = "Không áp dụng chế tài, tài xế đủ điều kiện vận hành tiêu chuẩn"
        status_code = "NORMAL"
    elif total_pts < 10:
        tier = "Mức 1 (1 - 9 điểm)"
        action = "Nhắc nhở nghiệp vụ và yêu cầu tài xế chấn chỉnh quy trình"
        status_code = "REMINDER"
    elif total_pts < 20:
        tier = "Mức 2 (10 - 19 điểm)"
        action = "Cảnh cáo bằng văn bản, trừ thi đua khen thưởng tháng và thông báo Quản lý đội xe"
        status_code = "WARNING"
    elif total_pts < 30:
        tier = "Mức 3 (20 - 29 điểm)"
        action = "Tạm đình chỉ tài khoản từ 3 đến 7 ngày, yêu cầu tham gia khóa đào tạo lại nghiệp vụ và quy chế dịch vụ"
        status_code = "SUSPENSION"
    else:
        tier = "Mức 4 (Từ 30 điểm trở lên)"
        action = "Chế tài mức cao nhất: Khóa tài khoản vĩnh viễn và tiến hành thủ tục chấm dứt hợp đồng hợp tác"
        status_code = "TERMINATION_REVIEW"

    rules_str = f" liên quan đến các điều khoản [{', '.join(rule_codes)}]" if rule_codes else ""
    summary = (
        f"Tổng điểm phạt tích lũy: {total_pts} điểm{rules_str}. "
        f"Phân loại chế tài: {tier}. "
        f"Biện pháp xử lý: {action}."
    )

    return {
        "tool": "calculate_violation_penalty_points",
        "total_penalty_points": total_pts,
        "violation_count": violation_count or (len(points) if isinstance(points, list) else 1 if total_pts > 0 else 0),
        "tier": tier,
        "status_code": status_code,
        "recommended_action": action,
        "summary": summary,
    }


def calculate_attendance_hours(
    hours_worked: float | list[float],
    standard_hours_per_day: float = 8.0,
    required_days: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tính tổng giờ làm việc / ca trực của tài xế và đối chiếu với định mức ngày công tiêu chuẩn (P172)."""
    total_hours = 0.0
    shift_count = 0
    if isinstance(hours_worked, list):
        total_hours = sum(float(h) for h in hours_worked)
        shift_count = len(hours_worked)
    else:
        total_hours = max(0.0, float(hours_worked or 0.0))
        shift_count = 1 if total_hours > 0 else 0

    std_hours = max(1.0, float(standard_hours_per_day))
    equivalent_days = round(total_hours / std_hours, 2)

    passed = None
    diff_hours = None
    if required_days is not None:
        target_hours = float(required_days) * std_hours
        passed = total_hours >= target_hours
        diff_hours = round(total_hours - target_hours, 2)
        summary = (
            f"Tổng thời gian làm việc: {round(total_hours, 2)} giờ ({shift_count} ca/ngày, tương đương {equivalent_days} ngày công tiêu chuẩn). "
            f"Định mức yêu cầu: {target_hours} giờ ({required_days} ngày công). "
            f"Kết quả: {'ĐẠT TIÊU CHUẨN' if passed else f'CHƯA ĐẠT (thiếu {abs(diff_hours)} giờ)'}."
        )
    else:
        summary = f"Tổng thời gian làm việc ghi nhận: {round(total_hours, 2)} giờ ({shift_count} ca/ngày, quy đổi {equivalent_days} ngày công chuẩn {std_hours}h)."

    return {
        "tool": "calculate_attendance_hours",
        "total_hours": round(total_hours, 2),
        "shift_count": shift_count,
        "standard_hours_per_day": std_hours,
        "equivalent_standard_days": equivalent_days,
        "required_days": required_days,
        "passed": passed,
        "diff_hours": diff_hours,
        "summary": summary,
    }


# =============================================================================
# 2. DATA RETRIEVAL & KNOWLEDGE GRAPH TOOLS
# =============================================================================


def get_driver_profile(
    db_repo: Any,
    driver_identifier: str,
) -> dict[str, Any]:
    """Tra cứu thông tin hồ sơ nhân sự cơ bản của tài xế từ CSDL."""
    if not db_repo:
        return {"tool": "get_driver_profile", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier)
    if not driver:
        # Try search by name or text
        driver = db_repo.find_driver_in_text(driver_identifier)

    if not driver:
        return {
            "tool": "get_driver_profile",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy hồ sơ cho tài xế '{driver_identifier}' trong CSDL.",
        }

    summary_text = (
        f"Hồ sơ tài xế: {driver.full_name} ({driver.driver_code}), Chương trình: {driver.program or 'Xanh Limo'}, "
        f"Đội xe: {driver.depot_name}, Xe: {driver.vehicle_model} (Biển số: {driver.license_plate or 'Chưa cập nhật'}), "
        f"Khu vực: {driver.region or 'N/A'}, Trạng thái: {driver.status}, Đánh giá trung bình: {driver.rating_avg}★."
    )

    return {
        "tool": "get_driver_profile",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "phone": driver.phone,
        "email": driver.email,
        "depot_name": driver.depot_name,
        "region": driver.region,
        "service_type": driver.service_type,
        "program": driver.program or "Xanh Limo",
        "status": driver.status,
        "vehicle_model": driver.vehicle_model,
        "license_plate": driver.license_plate,
        "rating_avg": driver.rating_avg,
        "acceptance_rate": driver.acceptance_rate,
        "summary": summary_text,
    }


def get_driver_trip_summary(
    db_repo: Any,
    driver_identifier: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    pipeline: Any = None,
) -> dict[str, Any]:
    """Tra cứu tổng hợp số liệu chuyến đi (tổng số chuyến, hoàn thành, hủy, tỷ lệ hủy cancel_rate_30d) theo ngày/tháng/năm hoặc snapshot."""
    if not db_repo:
        return {"tool": "get_driver_trip_summary", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_driver_trip_summary",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu số liệu chuyến đi.",
        }

    date_prefix, period_label = normalize_date_prefix(date)

    completed_trips = driver.completed_trips_count
    cancelled_trips = driver.cancelled_trips_count
    cancel_rate_30d = driver.cancellation_rate_30d
    total_trips = completed_trips + cancelled_trips
    snapshot_total_trips = total_trips
    snapshot_completed_trips = completed_trips
    snapshot_cancelled_trips = cancelled_trips
    snapshot_cancel_rate_30d = cancel_rate_30d
    source_kind = "db_baseline"

    # Priority A: Query snapshot/date-specific metrics from authoritative SQLite DB
    if db_repo and hasattr(db_repo, "get_driver_snapshot_metrics"):
        snap_metrics = db_repo.get_driver_snapshot_metrics(driver.driver_id, snapshot_id=snapshot_id, date=date_prefix or None)
        if snap_metrics is not None and (snap_metrics.get("snapshot_total_trips", 0) > 0 or snap_metrics.get("total_trips", 0) > 0):
            completed_trips = snap_metrics["completed_trips"]
            cancelled_trips = snap_metrics["cancelled_trips"]
            total_trips = snap_metrics["total_trips"]
            cancel_rate_30d = snap_metrics["cancel_rate"]
            snapshot_total_trips = snap_metrics.get("snapshot_total_trips", snapshot_total_trips)
            snapshot_completed_trips = snap_metrics.get("snapshot_completed_trips", snapshot_completed_trips)
            snapshot_cancelled_trips = snap_metrics.get("snapshot_cancelled_trips", snapshot_cancelled_trips)
            snapshot_cancel_rate_30d = snap_metrics.get("snapshot_cancel_rate", snapshot_cancel_rate_30d)
            source_kind = "db_filtered" if (date_prefix or snapshot_id) else "db_snapshot"

    # Priority B: Check if pipeline has Knowledge Graph subgraph if DB was empty or unavailable
    if source_kind == "db_baseline" and pipeline and hasattr(pipeline, "expand_subgraph_bfs"):
        try:
            subgraph = pipeline.expand_subgraph_bfs(driver_id=driver.driver_id, snapshot_id=snapshot_id)
            if subgraph and subgraph.nodes:
                trips = [n for n in subgraph.nodes if n.label == "Trip"]
                all_snap_trips = list(trips)
                if all_snap_trips:
                    snapshot_completed_trips = sum(1 for t in all_snap_trips if t.props.get("outcome") == "completed")
                    snapshot_cancelled_trips = sum(1 for t in all_snap_trips if t.props.get("outcome") == "cancelled")
                    snapshot_total_trips = len(all_snap_trips)
                    snapshot_cancel_rate_30d = round(snapshot_cancelled_trips / snapshot_total_trips, 4) if snapshot_total_trips > 0 else 0.0

                if date_prefix:
                    trips = [
                        t for t in trips
                        if (t.props.get("event_time") or t.props.get("start_time") or t.props.get("date") or t.props.get("valid_at") or "").startswith(date_prefix)
                    ]
                if trips:
                    completed_trips = sum(1 for t in trips if t.props.get("outcome") == "completed")
                    cancelled_trips = sum(1 for t in trips if t.props.get("outcome") == "cancelled")
                    total_trips = len(trips)
                    cancel_rate_30d = round(cancelled_trips / total_trips, 4) if total_trips > 0 else 0.0
                    source_kind = "kg_snapshot"
                elif all_snap_trips:
                    completed_trips = 0
                    cancelled_trips = 0
                    total_trips = 0
                    cancel_rate_30d = snapshot_cancel_rate_30d
                    source_kind = "kg_snapshot"
        except Exception:
            pass

    time_filter_label = f" ({period_label})" if period_label else ""
    snap_label = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""
    cancel_pct = round(cancel_rate_30d * 100, 2)
    snap_pct = round(snapshot_cancel_rate_30d * 100, 2)

    # Query incidents and complaints counts for complete operational overview
    incidents_count = 0
    complaints_count = 0
    if hasattr(db_repo, "get_incidents"):
        try:
            incs = db_repo.get_incidents(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=200)
            if isinstance(incs, list):
                if date_prefix:
                    incs = [i for i in incs if (getattr(i, "event_time", "") or "").startswith(date_prefix)]
                incidents_count = len(incs)
        except Exception:
            pass
    if hasattr(db_repo, "get_complaints"):
        try:
            comps = db_repo.get_complaints(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=200)
            if isinstance(comps, list):
                if date_prefix:
                    comps = [c for c in comps if (getattr(c, "event_time", "") or "").startswith(date_prefix)]
                complaints_count = len(comps)
        except Exception:
            pass

    extra_ops = f" Ghi nhận {incidents_count} sự cố vi phạm và {complaints_count} khiếu nại khách hàng."

    if total_trips == 0 and (date or snapshot_id):
        if snapshot_total_trips > 0:
            summary_text = (
                f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
                f"Trong {period_label or 'thời gian chỉ định'} không phát sinh chuyến xe mới (0 chuyến). "
                f"Tuy nhiên, trong kỳ đánh giá 30 ngày gần nhất của Snapshot: "
                f"Tài xế có tổng cộng {snapshot_total_trips} chuyến xe ({snapshot_completed_trips} hoàn thành, {snapshot_cancelled_trips} bị hủy), "
                f"tỷ lệ hủy chuyến (cancel_rate_30d) là {snap_pct}% ({snapshot_cancelled_trips}/{snapshot_total_trips} chuyến).{extra_ops}"
            )
        else:
            summary_text = (
                f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
                f"Không ghi nhận chuyến xe nào phát sinh trong khoảng thời gian này (0 cuốc xe).{extra_ops}"
            )
    else:
        summary_text = (
            f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
            f"Tổng cộng {total_trips} chuyến xe ({completed_trips} chuyến hoàn thành, {cancelled_trips} chuyến bị hủy). "
            f"Tỷ lệ hủy chuyến (cancel_rate_30d): {cancel_pct}% ({cancelled_trips}/{total_trips} chuyến).{extra_ops}"
        )

    return {
        "tool": "get_driver_trip_summary",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "snapshot_id": snapshot_id,
        "date": date_prefix if date else None,
        "period": period_label if date else None,
        "source_kind": source_kind,
        "total_trips_count": total_trips,
        "completed_trips_count": completed_trips,
        "cancelled_trips_count": cancelled_trips,
        "cancellation_rate_30d": cancel_rate_30d,
        "cancel_rate_pct": cancel_pct,
        "snapshot_total_trips": snapshot_total_trips,
        "snapshot_completed_trips": snapshot_completed_trips,
        "snapshot_cancelled_trips": snapshot_cancelled_trips,
        "snapshot_cancel_rate_30d": snapshot_cancel_rate_30d,
        "snapshot_cancel_rate_pct": snap_pct,
        "incidents_count": incidents_count,
        "complaints_count": complaints_count,
        "summary": summary_text,
    }


def get_driver_trip_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Deprecated alias for get_driver_trip_summary."""
    res = get_driver_trip_summary(*args, **kwargs)
    res["tool"] = "get_driver_trip_metrics"
    return res


def get_cancelled_trips_detail(
    db_repo: Any,
    driver_identifier: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    pipeline: Any = None,
) -> dict[str, Any]:
    """Tra cứu danh sách chi tiết các chuyến đi bị hủy (mã chuyến, thời gian, lý do hủy reason_code, bên hủy cancel_party)."""
    if not db_repo:
        return {"tool": "get_cancelled_trips_detail", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_cancelled_trips_detail",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu chuyến hủy.",
        }

    date_prefix, period_label = normalize_date_prefix(date)

    cancelled_items: list[dict[str, Any]] = []

    # Priority A: Query SQLite trips table as authoritative ledger
    if db_repo and hasattr(db_repo, "get_trips"):
        try:
            db_trips = db_repo.get_trips(driver_id=driver.driver_id, outcome="cancelled", snapshot_id=snapshot_id, limit=200)
            all_db_cancelled = list(db_trips)
            if date_prefix:
                filtered_date = [t for t in db_trips if (t.start_time or "").startswith(date_prefix)]
                if filtered_date:
                    db_trips = filtered_date
                elif all_db_cancelled:
                    # Provide rolling 30d window cancelled trips if specified date has 0
                    db_trips = all_db_cancelled
            for dt in db_trips:
                party = dt.cancel_party or ("Tài xế yêu cầu" if "driver" in str(dt.reason_code).lower() else "Khách/Hệ thống")
                cancelled_items.append({
                    "trip_id": dt.trip_id,
                    "reason_code": dt.reason_code or "không rõ",
                    "cancel_party": party,
                    "event_time": dt.start_time or "",
                    "pickup_address": dt.pickup_address or "",
                    "dropoff_address": dt.dropoff_address or "",
                })
        except Exception:
            pass

    # Priority B: Check if pipeline has Knowledge Graph subgraph if DB had no trips or to enrich
    if pipeline and hasattr(pipeline, "expand_subgraph_bfs"):
        try:
            subgraph = pipeline.expand_subgraph_bfs(driver_id=driver.driver_id, snapshot_id=snapshot_id)
            if subgraph and subgraph.nodes:
                existing_ids = {c["trip_id"] for c in cancelled_items}
                trips = [n for n in subgraph.nodes if n.label == "Trip" and n.props.get("outcome") == "cancelled"]
                all_snap_canc = list(trips)
                if date_prefix:
                    trips = [
                        t for t in trips
                        if (t.props.get("event_time") or t.props.get("start_time") or t.props.get("date") or t.props.get("valid_at") or "").startswith(date_prefix)
                    ]
                if not trips and all_snap_canc and date_prefix and not cancelled_items:
                    trips = all_snap_canc
                for t in trips:
                    if t.id not in existing_ids:
                        reason = t.props.get("reason_code", "không rõ")
                        party = t.props.get("cancel_party") or ("Tài xế yêu cầu" if "driver" in str(reason).lower() else "Khách/Hệ thống")
                        event_time = t.props.get("event_time") or t.props.get("valid_at") or t.props.get("start_time") or ""
                        cancelled_items.append({
                            "trip_id": t.id,
                            "reason_code": reason,
                            "cancel_party": party,
                            "event_time": event_time,
                            "pickup_address": t.props.get("pickup_address", ""),
                            "dropoff_address": t.props.get("dropoff_address", ""),
                        })
                    else:
                        # Enrich existing item if KG has richer pickup/dropoff address
                        for c in cancelled_items:
                            if c["trip_id"] == t.id:
                                if not c.get("pickup_address") and t.props.get("pickup_address"):
                                    c["pickup_address"] = t.props.get("pickup_address")
                                if not c.get("dropoff_address") and t.props.get("dropoff_address"):
                                    c["dropoff_address"] = t.props.get("dropoff_address")
        except Exception:
            pass

    time_filter_label = f" ({period_label})" if period_label else ""
    snap_label = f" trong snapshot [{snapshot_id[:8]}...]" if snapshot_id else ""
    if cancelled_items:
        detail_lines = []
        for c in cancelled_items:
            time_part = f" lúc {c['event_time'][:19].replace('T', ' ')}" if c.get('event_time') else ""
            party_part = f", bên hủy: {c['cancel_party']}" if c.get('cancel_party') else ""
            detail_lines.append(f"Chuyến {c['trip_id'][:8]} (lý do: {c['reason_code']}{party_part}{time_part})")
        summary_text = (
            f"Tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label} có {len(cancelled_items)} chuyến bị hủy: "
            + "; ".join(detail_lines) + "."
        )
    else:
        summary_text = f"Tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label} không có chuyến xe nào bị hủy."

    return {
        "tool": "get_cancelled_trips_detail",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "snapshot_id": snapshot_id,
        "date": date_prefix if date else None,
        "period": period_label if date else None,
        "cancelled_count": len(cancelled_items),
        "cancelled_trips": cancelled_items,
        "summary": summary_text,
    }


def get_driver_operational_stats(
    db_repo: Any,
    driver_id: str,
    date: str | None = None,
    snapshot_id: str | None = None,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Lấy số liệu vận hành thực tế các cuốc xe (phát, nhận, hoàn thành, hủy) và tổng doanh thu của tài xế theo ngày (YYYY-MM-DD) hoặc tháng/kỳ (YYYY-MM) và snapshot."""
    if not db_repo:
        return {"tool": "get_driver_operational_stats", "error": "Database repository is unavailable."}

    date_prefix, period_label = normalize_date_prefix(date)

    # Resolve driver by identifier/code/name if possible
    driver = None
    if hasattr(db_repo, "get_driver"):
        driver = db_repo.get_driver(driver_id)
    if not driver and hasattr(db_repo, "find_driver_in_text"):
        driver = db_repo.find_driver_in_text(driver_id)
    if not driver and hasattr(db_repo, "get_driver_by_code"):
        driver = db_repo.get_driver_by_code(driver_id)

    target_id = driver.driver_id if driver else driver_id

    # Retrieve trips with snapshot and driver isolation
    trips = []
    if hasattr(db_repo, "get_trips"):
        try:
            trips = db_repo.get_trips(driver_id=target_id, snapshot_id=snapshot_id, limit=500)
        except TypeError:
            trips = db_repo.get_trips(driver_id=target_id, limit=500)

    # Fallback to pipeline's BFS subgraph if DB has no trips for this snapshot but KG does
    if not trips and pipeline and hasattr(pipeline, "expand_subgraph_bfs"):
        try:
            subgraph = pipeline.expand_subgraph_bfs(driver_id=target_id, snapshot_id=snapshot_id)
            if subgraph and subgraph.nodes:
                from types import SimpleNamespace
                for n in subgraph.nodes:
                    if n.label == "Trip":
                        trips.append(SimpleNamespace(
                            trip_id=n.id,
                            outcome=n.props.get("outcome", "completed"),
                            fare_amount=n.props.get("fare") or n.props.get("fare_amount", 0),
                            start_time=n.props.get("event_time") or n.props.get("start_time") or "",
                        ))
        except Exception:
            pass

    # Filter trips matching the target date or month
    if date_prefix:
        period_trips = [t for t in trips if (getattr(t, "start_time", None) or "").startswith(date_prefix)]
    else:
        period_trips = trips

    completed_cnt = sum(1 for t in period_trips if getattr(t, "outcome", "") == "completed")
    cancelled_cnt = sum(1 for t in period_trips if getattr(t, "outcome", "") == "cancelled")
    total_revenue = sum(getattr(t, "fare_amount", 0) for t in period_trips if getattr(t, "outcome", "") == "completed")

    total_trips = len(period_trips)
    accepted_cnt = total_trips
    if driver and getattr(driver, "acceptance_rate", None) and driver.acceptance_rate > 0 and total_trips > 0:
        offered_cnt = int(round(accepted_cnt / driver.acceptance_rate))
    else:
        offered_cnt = max(total_trips, total_trips + (1 if cancelled_cnt > 0 else 0))

    if date_prefix:
        if len(date_prefix) == 4:
            period_label = f"Năm {date_prefix}"
        elif len(date_prefix) == 7:
            period_label = f"Tháng {date_prefix}"
        else:
            period_label = f"Ngày {date_prefix}"
    else:
        period_label = "Toàn kỳ"

    snap_label = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""
    driver_name = driver.full_name if driver else target_id
    driver_code = driver.driver_code if driver else target_id

    summary = (
        f"{period_label}{snap_label}: Tài xế {driver_name} ({driver_code}) ghi nhận {total_trips} cuốc xe "
        f"(phát: {offered_cnt}, nhận: {accepted_cnt}, hoàn thành: {completed_cnt}, hủy: {cancelled_cnt}). "
        f"Tổng doanh thu ghi nhận: {total_revenue:,.0f} VNĐ."
    )

    return {
        "tool": "get_driver_operational_stats",
        "driver_id": target_id,
        "driver_code": driver_code,
        "full_name": driver_name,
        "date": date_prefix or None,
        "snapshot_id": snapshot_id,
        "period": period_label,
        "trips_count": total_trips,
        "completed_trips": completed_cnt,
        "cancelled_trips": cancelled_cnt,
        "total_revenue_vnd": total_revenue,
        "offered_trips": offered_cnt,
        "accepted_trips": accepted_cnt,
        "summary": summary,
    }


def get_driver_daily_stats(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Deprecated alias for get_driver_operational_stats."""
    res = get_driver_operational_stats(*args, **kwargs)
    res["tool"] = "get_driver_daily_stats"
    return res


def get_driver_incidents_and_complaints(
    db_repo: Any,
    driver_identifier: str,
    pipeline: Any = None,
    snapshot_id: str | None = None,
    date: str | None = None,
    limit: int = 20,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tra cứu chi tiết các sự cố vi phạm (incidents) và khiếu nại/phản ánh từ khách hàng (complaints/feedback) của tài xế."""
    if not db_repo:
        return {"tool": "get_driver_incidents_and_complaints", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_driver_incidents_and_complaints",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu sự cố và khiếu nại.",
        }

    target_snap = snapshot_id or kwargs.get("snapshot_id")

    date_prefix, _ = normalize_date_prefix(date)

    complaint_items: list[dict[str, Any]] = []
    incident_items: list[dict[str, Any]] = []

    # 0. Query canonical complaints and incidents tables if available
    db_complaints = []
    db_incidents = []
    if hasattr(db_repo, "get_complaints"):
        try:
            db_complaints = db_repo.get_complaints(driver_id=driver.driver_id, snapshot_id=target_snap, limit=max(limit * 2, 50))
        except Exception:
            pass
    if hasattr(db_repo, "get_incidents"):
        try:
            db_incidents = db_repo.get_incidents(driver_id=driver.driver_id, snapshot_id=target_snap, limit=max(limit * 2, 50))
        except Exception:
            pass

    for comp in db_complaints:
        c_time = getattr(comp, "event_time", "") or ""
        if date_prefix and not c_time.startswith(date_prefix):
            continue
        complaint_items.append({
            "complaint_id": comp.complaint_id,
            "trip_id": comp.trip_id,
            "category": comp.category,
            "feedback": comp.description or comp.name or "",
            "date": c_time[:10],
        })

    for inc in db_incidents:
        i_time = getattr(inc, "event_time", "") or ""
        if date_prefix and not i_time.startswith(date_prefix):
            continue
        incident_items.append({
            "incident_id": inc.incident_id,
            "type": inc.incident_type or inc.name or "Sự cố vận hành",
            "description": inc.description or "",
            "date": i_time[:10],
        })

    # If canonical records were not populated, fall back to trips and v2 catalog
    if not db_complaints and not db_incidents:
        # 1. Query SQLite trips for feedback and low passenger ratings (<= 3 stars) or driver-cancelled trips
        try:
            trips = []
            if hasattr(db_repo, "get_trips"):
                try:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, snapshot_id=target_snap, limit=200)
                except TypeError:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, limit=200)
            for t in trips:
                start_t = getattr(t, "start_time", "") or ""
                if date_prefix and not start_t.startswith(date_prefix):
                    continue

                p_rating = getattr(t, "passenger_rating", None)
                p_feedback = getattr(t, "passenger_feedback", None) or ""
                outcome = getattr(t, "outcome", "")
                reason = getattr(t, "reason_code", "") or ""
                party = getattr(t, "cancel_party", "") or ""

                # Check if this trip had poor rating or negative feedback
                if (p_rating is not None and p_rating <= 3) or p_feedback:
                    complaint_items.append({
                        "trip_id": t.trip_id,
                        "date": start_t[:10],
                        "passenger_rating": p_rating,
                        "feedback": p_feedback or f"Đánh giá thấp {p_rating}★ không kèm nhận xét",
                        "pickup_address": t.pickup_address,
                        "dropoff_address": t.dropoff_address,
                    })

                # Check if trip was cancelled by driver (operational violation)
                if outcome == "cancelled" and party == "driver":
                    incident_items.append({
                        "incident_id": f"inc-{t.trip_id[:8]}",
                        "trip_id": t.trip_id,
                        "date": start_t[:10],
                        "type": "Tài xế tự ý hủy chuyến (driver_cancel)",
                        "reason_code": reason,
                        "severity": "MEDIUM",
                        "penalty_points": 5,
                        "description": f"Tài xế hủy chuyến {t.trip_id[:8]} với lý do '{reason}' tại {t.pickup_address}",
                    })
        except Exception:
            pass

        # 2. Check V2 operational catalog data if applicable
        try:
            from gsm_memory.adapters.v2_operational_catalog import INCIDENTS_DATA
            v2_id = driver.driver_id if str(driver.driver_id).startswith("v2_") else None
            if not v2_id and hasattr(driver, "driver_code"):
                num_match = re.search(r"(\d+)", driver.driver_code)
                if num_match:
                    v2_id = f"v2_drv_{int(num_match.group(1)):03d}"

            if v2_id:
                for inc in INCIDENTS_DATA:
                    if inc.get("driver_id") == v2_id:
                        incident_items.append({
                            "incident_id": inc.get("id"),
                            "type": inc.get("type", "Sự cố vận hành"),
                            "date": (inc.get("timestamp") or "")[:10],
                            "severity": inc.get("severity", "MEDIUM"),
                            "penalty_points": inc.get("penalty_points", 0),
                            "description": inc.get("description", ""),
                        })
        except Exception:
            pass

    # Rank by semantic score if semantic_query is provided and Qdrant is available
    semantic_q = kwargs.get("semantic_query") or kwargs.get("query")
    if semantic_q and pipeline and hasattr(pipeline, "qdrant_retriever") and pipeline.qdrant_retriever and pipeline.qdrant_retriever.is_available():
        try:
            q_comps = pipeline.qdrant_retriever.search_operational_nodes(
                semantic_q,
                driver_id=driver.driver_id,
                kind="complaint",
                top_k=max(limit * 2, 20),
            )
            comp_score_map = {h.node_id: h.score for h in q_comps}
            for ci in complaint_items:
                ci["semantic_score"] = comp_score_map.get(ci.get("complaint_id", ""), 0.0)
            complaint_items.sort(key=lambda x: x.get("semantic_score", 0.0), reverse=True)

            q_incs = pipeline.qdrant_retriever.search_operational_nodes(
                semantic_q,
                driver_id=driver.driver_id,
                kind="incident",
                top_k=max(limit * 2, 20),
            )
            inc_score_map = {h.node_id: h.score for h in q_incs}
            for ii in incident_items:
                ii["semantic_score"] = inc_score_map.get(ii.get("incident_id", ""), 0.0)
            incident_items.sort(key=lambda x: x.get("semantic_score", 0.0), reverse=True)
        except Exception:
            pass

    complaint_items = complaint_items[:limit]
    incident_items = incident_items[:limit]

    total_issues = len(complaint_items) + len(incident_items)
    summary_parts = []
    if incident_items:
        inc_summaries = [f"{inc['type']} ({inc.get('date', '')}: {inc.get('description', '')[:50]})" for inc in incident_items[:3]]
        summary_parts.append(f"{len(incident_items)} sự cố/vi phạm ({'; '.join(inc_summaries)})")
    if complaint_items:
        comp_summaries = [f"Chuyến {c['trip_id'][:8]} ({c.get('passenger_rating', '')}★: '{c.get('feedback', '')[:40]}')" for c in complaint_items[:3]]
        summary_parts.append(f"{len(complaint_items)} phản ánh/khiếu nại từ khách ({'; '.join(comp_summaries)})")

    if total_issues > 0:
        summary_text = (
            f"Tài xế {driver.full_name} ({driver.driver_code}) ghi nhận {total_issues} phản ánh & sự cố: "
            + "; ".join(summary_parts) + "."
        )
    else:
        summary_text = f"Tài xế {driver.full_name} ({driver.driver_code}) không có biên bản sự cố hay khiếu nại tiêu cực nào được ghi nhận."

    return {
        "tool": "get_driver_incidents_and_complaints",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "incidents_count": len(incident_items),
        "complaints_count": len(complaint_items),
        "total_issues": total_issues,
        "incidents": incident_items,
        "complaints": complaint_items,
        "summary": summary_text,
    }


def get_recent_incidents(
    db_repo: Any,
    driver_identifier: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    limit: int = 10,
    include_description: bool = False,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Lấy danh sách top 10 (hoặc theo limit) sự cố gần nhất của tài xế theo snapshot và mốc thời gian.

    Chỉ trả về thông tin tóm tắt gồm: mã sự cố (incident_id), tên sự cố (name),
    loại sự cố (incident_type) và thời gian (event_time). Không trả về description dài trừ khi include_description=True.
    """
    if not db_repo:
        return {"tool": "get_recent_incidents", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_recent_incidents",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu danh sách sự cố.",
            "incidents": [],
        }

    date_prefix, _ = normalize_date_prefix(date)

    incidents_list: list[dict[str, Any]] = []

    # 1. Query canonical incidents table
    db_incidents = []
    if hasattr(db_repo, "get_incidents"):
        try:
            db_incidents = db_repo.get_incidents(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=max(limit * 2, 50))
        except Exception:
            pass

    if isinstance(db_incidents, list):
        for inc in db_incidents:
            i_time = getattr(inc, "event_time", "") or ""
            if date_prefix and not i_time.startswith(date_prefix):
                continue
            i_desc = getattr(inc, "description", "") or getattr(inc, "content", "") or ""
            inc_item = {
                "incident_id": inc.incident_id,
                "name": inc.name or inc.incident_type or "Sự cố vi phạm",
                "incident_type": inc.incident_type or "violation",
                "event_time": i_time,
            }
            if include_description:
                inc_item["description"] = i_desc
            incidents_list.append(inc_item)

    # 2. Fallback to trips / BFS if no canonical incidents found
    if not incidents_list:
        try:
            trips = []
            if hasattr(db_repo, "get_trips"):
                try:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=200)
                except TypeError:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, limit=200)
            if isinstance(trips, list):
                for t in trips:
                    start_t = getattr(t, "start_time", "") or ""
                    if date_prefix and not start_t.startswith(date_prefix):
                        continue
                    reason = getattr(t, "reason_code", "") or ""
                    party = getattr(t, "cancel_party", "") or ""
                    if party in ("Tài xế yêu cầu", "driver") or reason == "driver_request":
                        inc_item = {
                            "incident_id": f"INC-TRIP-{t.trip_id}",
                            "name": f"Hủy chuyến do tài xế ({reason or 'driver_request'})",
                            "incident_type": "driver_cancellation",
                            "event_time": start_t,
                        }
                        if include_description:
                            inc_item["description"] = f"Chuyến đi từ {t.pickup_address} đến {t.dropoff_address} bị hủy bởi tài xế (lý do: {reason})."
                        incidents_list.append(inc_item)
        except Exception:
            pass

    # Sort descending by event_time and limit
    incidents_list.sort(key=lambda x: str(x.get("event_time", "")), reverse=True)
    top_incidents = incidents_list[:limit]

    time_str = f" trong thời gian {date_prefix}" if date_prefix else ""
    snap_str = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""
    total_found = len(incidents_list)
    if not top_incidents:
        summary = f"Tài xế {driver.full_name} ({driver.driver_code}){time_str}{snap_str} không ghi nhận sự cố vi phạm nào."
    else:
        lines = [
            f"Tài xế {driver.full_name} ({driver.driver_code}){time_str}{snap_str} có TỔNG CỘNG {total_found} SỰ CỐ/VI PHẠM được ghi nhận (hiển thị {len(top_incidents)} sự cố):"
        ]
        for idx, inc in enumerate(top_incidents, 1):
            t_str = inc['event_time'][:10] if inc.get('event_time') else "Không rõ"
            desc_val = f"\n      + Nội dung: \"{inc['description']}\"" if (include_description and inc.get("description")) else ""
            lines.append(f"{idx}. [{inc['incident_id'][:8]}] {inc['name']} (Loại: {inc['incident_type']}, Ngày: {t_str}){desc_val}")
        if total_found > len(top_incidents):
            lines.append(f"... và còn {total_found - len(top_incidents)} sự cố khác trong tổng số {total_found} sự cố.")
            lines.append(
                f"-> QUAN TRỌNG: Tổng số sự cố thực tế là {total_found}. "
                f"Khi kết luận, BẮT BUỘC phải khẳng định đúng con số {total_found} sự cố này "
                f"(có thể nêu các vụ trên làm ví dụ minh họa hoặc liệt kê chi tiết, TUYỆT ĐỐI KHÔNG được kết luận sai lệch tổng số lượng)."
            )
        else:
            lines.append(f"-> Ghi nhận đầy đủ {total_found} sự cố/vi phạm trong kỳ.")
        summary = "\n".join(lines)

    return {
        "tool": "get_recent_incidents",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "snapshot_id": snapshot_id,
        "date": date_prefix or None,
        "total_count": len(incidents_list),
        "limit": limit,
        "incidents": top_incidents,
        "summary": summary,
    }


def get_incident_detail(
    incident_id: str,
    db_repo: Any = None,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tra cứu nội dung mô tả chi tiết của một sự cố theo mã sự cố (incident_id)."""
    inc_id = str(incident_id).strip()
    if not inc_id:
        return {"tool": "get_incident_detail", "found": False, "error": "Thiếu mã sự cố (incident_id)."}

    # 1. Query canonical incident
    record = None
    if db_repo and hasattr(db_repo, "get_incident"):
        try:
            record = db_repo.get_incident(inc_id)
        except Exception:
            pass

    if record:
        summary = (
            f"Chi tiết sự cố [{record.incident_id}] {record.name or record.incident_type}:\n"
            f"- Mã sự cố: {record.incident_id}\n"
            f"- Tên sự cố: {record.name or 'Sự cố vi phạm'}\n"
            f"- Phân loại: {record.incident_type}\n"
            f"- Thời gian xảy ra: {record.event_time}\n"
            f"- Mã tài xế liên quan: {record.driver_id}\n"
            f"- Mã chuyến đi: {record.trip_id or 'Không liên kết chuyến cụ thể'}\n"
            f"- Nội dung mô tả chi tiết: {record.description or 'Không có mô tả chi tiết kèm theo.'}"
        )
        return {
            "tool": "get_incident_detail",
            "found": True,
            "incident_id": record.incident_id,
            "name": record.name,
            "incident_type": record.incident_type,
            "event_time": record.event_time,
            "driver_id": record.driver_id,
            "trip_id": record.trip_id,
            "description": record.description,
            "summary": summary,
        }

    # 2. Check if incident_id is a TRIP incident fallback (e.g. INC-TRIP-xxx or trip_id)
    clean_trip_id = inc_id.replace("INC-TRIP-", "")
    if db_repo and hasattr(db_repo, "get_trip"):
        try:
            trip = db_repo.get_trip(clean_trip_id)
            if trip:
                summary = (
                    f"Chi tiết sự cố [{inc_id}] Hủy chuyến:\n"
                    f"- Mã chuyến: {trip.trip_id}\n"
                    f"- Thời gian: {trip.start_time}\n"
                    f"- Lý do hủy: {trip.reason_code}\n"
                    f"- Bên hủy: {trip.cancel_party}\n"
                    f"- Nội dung mô tả chi tiết: Chuyến đi phát sinh từ {trip.pickup_address} đến {trip.dropoff_address} bị hủy bởi {trip.cancel_party} do lý do: {trip.reason_code}."
                )
                return {
                    "tool": "get_incident_detail",
                    "found": True,
                    "incident_id": inc_id,
                    "name": f"Hủy chuyến do {trip.cancel_party}",
                    "incident_type": "driver_cancellation",
                    "event_time": trip.start_time,
                    "driver_id": trip.driver_id,
                    "trip_id": trip.trip_id,
                    "description": f"Chuyến đi từ {trip.pickup_address} đến {trip.dropoff_address} bị hủy bởi {trip.cancel_party} (lý do: {trip.reason_code}).",
                    "summary": summary,
                }
        except Exception:
            pass

    return {
        "tool": "get_incident_detail",
        "found": False,
        "incident_id": inc_id,
        "summary": f"Không tìm thấy thông tin chi tiết cho mã sự cố '{inc_id}'. Vui lòng kiểm tra lại mã sự cố.",
    }


def get_recent_complaints(
    db_repo: Any,
    driver_identifier: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    limit: int = 10,
    include_description: bool = False,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Lấy danh sách top 10 (hoặc theo limit) khiếu nại gần nhất của tài xế theo snapshot và mốc thời gian.

    Chỉ trả về thông tin tóm tắt gồm: mã khiếu nại (complaint_id), tên/tiêu đề khiếu nại (name),
    phân loại (category) và thời gian (event_time). Không trả về description dài trừ khi include_description=True.
    """
    if not db_repo:
        return {"tool": "get_recent_complaints", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_recent_complaints",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu danh sách khiếu nại.",
            "complaints": [],
        }

    date_prefix, _ = normalize_date_prefix(date)

    complaints_list: list[dict[str, Any]] = []

    # 1. Query canonical complaints table
    db_complaints = []
    if hasattr(db_repo, "get_complaints"):
        try:
            db_complaints = db_repo.get_complaints(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=max(limit * 2, 50))
        except Exception:
            pass

    if isinstance(db_complaints, list):
        for comp in db_complaints:
            c_time = getattr(comp, "event_time", "") or ""
            if date_prefix and not c_time.startswith(date_prefix):
                continue
            c_desc = getattr(comp, "description", "") or getattr(comp, "content", "") or ""
            comp_item = {
                "complaint_id": comp.complaint_id,
                "name": comp.name or comp.category or "Khiếu nại khách hàng",
                "category": comp.category or "customer_feedback",
                "event_time": c_time,
            }
            if include_description:
                comp_item["description"] = c_desc
            complaints_list.append(comp_item)

    # 2. Fallback to trips low rating / feedback
    if not complaints_list:
        try:
            trips = []
            if hasattr(db_repo, "get_trips"):
                try:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, snapshot_id=snapshot_id, limit=200)
                except TypeError:
                    trips = db_repo.get_trips(driver_id=driver.driver_id, limit=200)
            if isinstance(trips, list):
                for t in trips:
                    start_t = getattr(t, "start_time", "") or ""
                    if date_prefix and not start_t.startswith(date_prefix):
                        continue
                    p_rating = getattr(t, "passenger_rating", None)
                    p_feedback = getattr(t, "passenger_feedback", None) or ""
                    if (p_rating is not None and p_rating <= 3) or p_feedback:
                        comp_item = {
                            "complaint_id": f"CMP-TRIP-{t.trip_id}",
                            "name": p_feedback or f"Đánh giá khách hàng thấp ({p_rating}★)",
                            "category": "service_rating",
                            "event_time": start_t,
                        }
                        if include_description:
                            comp_item["description"] = p_feedback or f"Khách đánh giá {p_rating}★ cho chuyến {t.trip_id[:8]}"
                        complaints_list.append(comp_item)
        except Exception:
            pass

    # Sort descending by event_time and limit
    complaints_list.sort(key=lambda x: str(x.get("event_time", "")), reverse=True)
    top_complaints = complaints_list[:limit]

    time_str = f" trong thời gian {date_prefix}" if date_prefix else ""
    snap_str = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""
    total_found = len(complaints_list)
    if not top_complaints:
        summary = f"Tài xế {driver.full_name} ({driver.driver_code}){time_str}{snap_str} không ghi nhận khiếu nại nào từ khách hàng."
    else:
        lines = [
            f"Tài xế {driver.full_name} ({driver.driver_code}){time_str}{snap_str} có TỔNG CỘNG {total_found} KHIẾU NẠI được ghi nhận (hiển thị {len(top_complaints)} khiếu nại):"
        ]
        for idx, comp in enumerate(top_complaints, 1):
            t_str = comp['event_time'][:10] if comp.get('event_time') else "Không rõ"
            desc_val = f"\n      + Nội dung: \"{comp['description']}\"" if (include_description and comp.get("description")) else ""
            lines.append(f"{idx}. [{comp['complaint_id'][:8]}] {comp['name']} (Phân loại: {comp['category']}, Ngày: {t_str}){desc_val}")
        if total_found > len(top_complaints):
            lines.append(f"... và còn {total_found - len(top_complaints)} khiếu nại khác trong tổng số {total_found} khiếu nại.")
            lines.append(
                f"-> QUAN TRỌNG: Tổng số khiếu nại thực tế là {total_found}. "
                f"Khi kết luận, BẮT BUỘC phải khẳng định đúng con số {total_found} khiếu nại này "
                f"(có thể nêu các vụ trên làm ví dụ minh họa hoặc liệt kê chi tiết, TUYỆT ĐỐI KHÔNG được kết luận sai lệch rằng tài xế chỉ có {len(top_complaints)} khiếu nại)."
            )
        else:
            lines.append(f"-> Ghi nhận đầy đủ {total_found} khiếu nại trong kỳ.")
        summary = "\n".join(lines)

    return {
        "tool": "get_recent_complaints",
        "found": True,
        "driver_id": driver.driver_id,
        "driver_code": driver.driver_code,
        "full_name": driver.full_name,
        "snapshot_id": snapshot_id,
        "date": date_prefix or None,
        "total_count": len(complaints_list),
        "limit": limit,
        "complaints": top_complaints,
        "summary": summary,
    }


def get_complaint_detail(
    complaint_id: str,
    db_repo: Any = None,
    pipeline: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tra cứu nội dung mô tả chi tiết của một khiếu nại theo mã khiếu nại (complaint_id)."""
    comp_id = str(complaint_id).strip()
    if not comp_id:
        return {"tool": "get_complaint_detail", "found": False, "error": "Thiếu mã khiếu nại (complaint_id)."}

    # 1. Query canonical complaint
    record = None
    if db_repo and hasattr(db_repo, "get_complaint"):
        try:
            record = db_repo.get_complaint(comp_id)
        except Exception:
            pass

    if record:
        summary = (
            f"Chi tiết khiếu nại [{record.complaint_id}] {record.name or record.category}:\n"
            f"- Mã khiếu nại: {record.complaint_id}\n"
            f"- Tiêu đề/Tên khiếu nại: {record.name or 'Khiếu nại khách hàng'}\n"
            f"- Phân loại: {record.category}\n"
            f"- Thời gian tiếp nhận: {record.event_time}\n"
            f"- Mã tài xế liên quan: {record.driver_id}\n"
            f"- Mã chuyến đi: {record.trip_id or 'Không liên kết chuyến cụ thể'}\n"
            f"- Nội dung mô tả chi tiết: {record.description or 'Không có mô tả chi tiết kèm theo.'}"
        )
        return {
            "tool": "get_complaint_detail",
            "found": True,
            "complaint_id": record.complaint_id,
            "name": record.name,
            "category": record.category,
            "event_time": record.event_time,
            "driver_id": record.driver_id,
            "trip_id": record.trip_id,
            "description": record.description,
            "summary": summary,
        }

    # 2. Check if complaint_id is a TRIP complaint fallback (e.g. CMP-TRIP-xxx or trip_id)
    clean_trip_id = comp_id.replace("CMP-TRIP-", "")
    if db_repo and hasattr(db_repo, "get_trip"):
        try:
            trip = db_repo.get_trip(clean_trip_id)
            if trip:
                desc = trip.passenger_feedback or f"Khách hàng đánh giá mức sao thấp {trip.passenger_rating}★."
                summary = (
                    f"Chi tiết khiếu nại [{comp_id}] Đánh giá chuyến đi:\n"
                    f"- Mã chuyến: {trip.trip_id}\n"
                    f"- Thời gian: {trip.start_time}\n"
                    f"- Đánh giá sao: {trip.passenger_rating}★\n"
                    f"- Lộ trình: {trip.pickup_address} -> {trip.dropoff_address}\n"
                    f"- Nội dung phản ánh chi tiết: {desc}"
                )
                return {
                    "tool": "get_complaint_detail",
                    "found": True,
                    "complaint_id": comp_id,
                    "name": f"Phản ánh khách hàng ({trip.passenger_rating}★)",
                    "category": "service_rating",
                    "event_time": trip.start_time,
                    "driver_id": trip.driver_id,
                    "trip_id": trip.trip_id,
                    "description": desc,
                    "summary": summary,
                }
        except Exception:
            pass

    return {
        "tool": "get_complaint_detail",
        "found": False,
        "complaint_id": comp_id,
        "summary": f"Không tìm thấy thông tin chi tiết cho mã khiếu nại '{comp_id}'. Vui lòng kiểm tra lại mã khiếu nại.",
    }


def query_driver_graph(
    pipeline: Any,
    driver_id: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    focus: str | None = None,
    target_node_types: list[str] | None = None,
    edge_types: list[str] | None = None,
    semantic_query: str | None = None,
    limit: int = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tra cứu đồ thị tri thức (Knowledge Graph) có định hướng từ node Tài xế.

    Hỗ trợ duyệt theo các nhánh ngữ nghĩa: 'location', 'complaints', 'incidents',
    'fleet', 'vehicle', 'kpi_metrics', 'enforcement', 'all'.
    Tích hợp bộ lọc ngữ nghĩa (semantic_query) để lọc sự cố hoặc khiếu nại phù hợp
    với câu hỏi, trả về đường dẫn liên kết (paths) và mô tả chi tiết của từng node.
    """
    if not pipeline:
        return {"tool": "query_driver_graph", "error": "Pipeline unavailable."}

    date_prefix, _ = normalize_date_prefix(date)

    try:
        # Resolve driver code/name to UUID if needed
        driver_code = ""
        driver_name = ""
        if getattr(pipeline, "db_repo", None) and driver_id:
            d_found = (
                pipeline.db_repo.find_driver_in_text(driver_id)
                or pipeline.db_repo.get_driver_by_code(driver_id)
                or pipeline.db_repo.get_driver(driver_id)
            )
            if d_found and hasattr(d_found, "driver_id") and isinstance(d_found.driver_id, str):
                driver_code = getattr(d_found, "driver_code", "")
                driver_name = getattr(d_found, "full_name", "")
                driver_id = d_found.driver_id

        # Execute directed traversal
        subgraph = None
        if hasattr(pipeline, "expand_subgraph_directed"):
            try:
                res_sub = pipeline.expand_subgraph_directed(
                    driver_id=driver_id,
                    snapshot_id=snapshot_id,
                    focus=focus,
                    target_node_types=target_node_types,
                    edge_types=edge_types,
                    semantic_query=semantic_query,
                    limit=limit,
                    date=date,
                )
                if hasattr(res_sub, "nodes") and isinstance(res_sub.nodes, list) and len(res_sub.nodes) > 0:
                    subgraph = res_sub
            except Exception:
                subgraph = None

        if not subgraph and hasattr(pipeline, "expand_subgraph_bfs"):
            res_sub = pipeline.expand_subgraph_bfs(driver_id=driver_id, snapshot_id=snapshot_id)
            if hasattr(res_sub, "nodes"):
                subgraph = res_sub

        if not subgraph or not subgraph.nodes:
            return {
                "tool": "query_driver_graph",
                "driver_id": driver_id,
                "found": False,
                "summary": f"Không tìm thấy dữ liệu đồ thị tri thức cho tài xế '{driver_name or driver_id}'.",
                "paths": [],
                "node_details": [],
            }

        # Cache on pipeline for downstream UI graph visualizer
        setattr(pipeline, "last_subgraph", subgraph)

        node_by_id = {n.id: n for n in subgraph.nodes}
        driver_node = next((n for n in subgraph.nodes if n.label == "Driver"), None)
        driver_name = driver_name or (driver_node.name if driver_node else driver_id)
        driver_code = driver_code or (driver_node.props.get("code", "") if driver_node else "")

        # 1. Format Graph Paths (Triplets: Node A -[REL]-> Node B)
        paths: list[str] = []
        for e in subgraph.edges:
            s_n = node_by_id.get(e.start_id)
            e_n = node_by_id.get(e.end_id)
            s_lbl = s_n.label if s_n else "Node"
            s_nm = s_n.name if s_n else e.start_id[:8]
            e_lbl = e_n.label if e_n else "Node"
            e_nm = e_n.name if e_n else e.end_id[:8]
            paths.append(f"({s_lbl}: {s_nm}) -[{e.rel_type}]-> ({e_lbl}: {e_nm})")

        # 2. Extract Category-specific node groups
        regions = [n for n in subgraph.nodes if n.label == "Region"]
        zones = [n for n in subgraph.nodes if n.label == "Zone"]
        trips = [n for n in subgraph.nodes if n.label == "Trip"]
        complaints = [n for n in subgraph.nodes if n.label in ("Complaint", "CustomerComplaint")]
        incidents = [n for n in subgraph.nodes if n.label == "Incident"]
        fleets = [n for n in subgraph.nodes if n.label in ("Fleet", "Hub")]
        vehicles = [n for n in subgraph.nodes if n.label == "Vehicle"]
        maints = [n for n in subgraph.nodes if n.label == "MaintenanceEvent"]
        vtypes = [n for n in subgraph.nodes if n.label == "VehicleType"]
        measurements = [n for n in subgraph.nodes if n.label == "Measurement"]
        decisions = [n for n in subgraph.nodes if n.label in ("EnforcementDecision", "RewardPenalty")]
        findings = [n for n in subgraph.nodes if n.label == "ViolationFinding"]
        rules = [n for n in subgraph.nodes if n.label in ("PolicyRule", "PolicyClause")]
        states = [n for n in subgraph.nodes if n.label == "StateObservation"]

        # 3. Format Node Details with descriptions
        node_details: list[dict[str, Any]] = []
        for n in subgraph.nodes:
            if n.label == "Driver":
                continue
            desc = (
                n.props.get("description")
                or n.props.get("content")
                or n.props.get("name")
                or ""
            )
            detail_item = {
                "id": n.id,
                "label": n.label,
                "name": n.name,
                "description": desc,
                "props": {k: v for k, v in n.props.items() if k not in ("visibility_snapshot_ids", "ingestion_time")},
            }
            if "semantic_score" in n.props:
                detail_item["semantic_score"] = n.props["semantic_score"]
            node_details.append(detail_item)

        # 4. Construct Structured Markdown Summary for ReAct AI
        focus_title = f" (Mục tiêu: {focus.upper()})" if focus and focus != "all" else ""
        period_str = f" trong khoảng thời gian {date_prefix}" if date_prefix else ""
        snap_str = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""

        summary_lines = [
            f"=== TRÍCH XUẤT ĐỒ THỊ TRI THỨC CÓ ĐỊNH HƯỚNG{focus_title} ===",
            f"Tài xế: {driver_name} (Mã: {driver_code or 'ID: ' + driver_id[:8]}){period_str}{snap_str}",
            f"- Tổng số nút: {len(subgraph.nodes)} | Tổng số cạnh liên kết: {len(subgraph.edges)}",
            "",
            "1. CÁC QUAN HỆ & ĐƯỜNG DẪN ĐỒ THỊ (GRAPH PATHS):",
        ]
        if paths:
            for p in paths[:20]:
                summary_lines.append(f"  * {p}")
            if len(paths) > 20:
                summary_lines.append(f"  * [...và {len(paths) - 20} cạnh liên kết khác...]")
        else:
            summary_lines.append("  * Không có cạnh liên kết trực tiếp.")

        summary_lines.append("")
        summary_lines.append("2. CHI TIẾT THỰC THỂ & MÔ TẢ (NODE DETAILS & DESCRIPTIONS):")

        # Location details
        if regions or zones or trips:
            if regions:
                r_names = ", ".join(r.name for r in regions)
                summary_lines.append(f"  * [Khu vực/Địa bàn]: {r_names}")
            if zones:
                z_names = ", ".join(set(z.name for z in zones[:10]))
                summary_lines.append(f"  * [Quận/Zone đón trả ({len(zones)} zone)]: {z_names}")
            if trips:
                completed_cnt = sum(1 for t in trips if t.props.get("outcome") == "completed")
                cancelled_cnt = sum(1 for t in trips if t.props.get("outcome") == "cancelled")
                summary_lines.append(f"  * [Chuyến đi gần nhất]: {len(trips)} chuyến ({completed_cnt} hoàn thành, {cancelled_cnt} bị hủy).")
                for t in trips[:4]:
                    t_pick = t.props.get("pickup", "")
                    t_drop = t.props.get("dropoff", "")
                    t_route = f" ({t_pick} -> {t_drop})" if t_pick or t_drop else ""
                    summary_lines.append(f"    - {t.name}: {t.props.get('outcome', 'chuyến')}{t_route}, Lúc: {t.props.get('event_time') or t.props.get('start_time', 'N/A')}")

        # Complaints details
        if complaints:
            summary_lines.append(f"  * [Phản ánh/Khiếu nại khách hàng ({len(complaints)} bản ghi)]:")
            for c in complaints:
                c_score = f" [Độ khớp: {c.props['semantic_score']}]" if "semantic_score" in c.props else ""
                c_desc = c.props.get("description") or c.props.get("content") or "Không có mô tả chi tiết."
                summary_lines.append(f"    - {c.name} (Phân loại: {c.props.get('category', 'khiếu nại')}){c_score}:")
                summary_lines.append(f"      + Nội dung: \"{c_desc}\"")

        # Incidents details
        if incidents:
            summary_lines.append(f"  * [Biên bản sự cố/vi phạm ({len(incidents)} biên bản)]:")
            for inc in incidents:
                i_score = f" [Độ khớp: {inc.props['semantic_score']}]" if "semantic_score" in inc.props else ""
                i_desc = inc.props.get("description") or "Không có mô tả chi tiết."
                summary_lines.append(f"    - {inc.name} (Loại: {inc.props.get('incident_type', 'sự cố')}){i_score}:")
                summary_lines.append(f"      + Nội dung: \"{i_desc}\"")

        # Fleet details
        if fleets:
            f_name = fleets[0].name
            summary_lines.append(f"  * [Đội xe / Hub]: {f_name}")

        # Vehicle details
        if vehicles:
            v_props = vehicles[0].props
            v_plate = v_props.get("mock_plate") or v_props.get("plate_number") or v_props.get("license_plate") or ""
            v_model = v_props.get("model") or v_props.get("vehicle_model") or vehicles[0].name
            v_type_str = f", Loại: {vtypes[0].name}" if vtypes else ""
            summary_lines.append(f"  * [Phương tiện]: {v_model} (Biển số: {v_plate or 'Biển số GSM'}{v_type_str})")
            if maints:
                summary_lines.append(f"    - Sự kiện bảo dưỡng xe ({len(maints)} đợt): {', '.join(m.name for m in maints)}")

        # KPI Measurements
        if measurements:
            summary_lines.append("  * [Chỉ số đo lường vận hành (KPI Measurements)]:")
            for m in measurements[:5]:
                m_val = m.props.get("value") or m.props.get("description")
                summary_lines.append(f"    - {m.name}: {m_val}")

        # Enforcement Decisions & Policy
        if decisions or findings:
            summary_lines.append("  * [Chế tài & Quyết định xử lý]:")
            for d in decisions[:3]:
                summary_lines.append(f"    - {d.name} -> Trạng thái: {d.props.get('status', 'áp dụng')}")
            for f in findings[:3]:
                summary_lines.append(f"    - Thẩm định vi phạm: {f.name} (Ghi nhận: {f.props.get('observed_value')}, Ngưỡng: {f.props.get('threshold')})")

        # State / Program
        if states:
            for s in states:
                summary_lines.append(f"  * [Trạng thái / Chương trình đối tác]: {s.name} = {s.props.get('value', '')}")

        summary_text = "\n".join(summary_lines)

        node_counts_by_label: dict[str, int] = {}
        for n in subgraph.nodes:
            node_counts_by_label[n.label] = node_counts_by_label.get(n.label, 0) + 1

        edge_types_dict: dict[str, int] = {}
        for e in subgraph.edges:
            edge_types_dict[e.rel_type] = edge_types_dict.get(e.rel_type, 0) + 1

        completed_cnt = sum(1 for t in trips if t.props.get("outcome") == "completed")
        cancelled_cnt = sum(1 for t in trips if t.props.get("outcome") == "cancelled")

        return {
            "tool": "query_driver_graph",
            "driver_id": driver_id,
            "driver_code": driver_code,
            "driver_name": driver_name,
            "focus": focus or "all",
            "snapshot_id": snapshot_id,
            "date": date_prefix or None,
            "node_count": len(subgraph.nodes),
            "edge_count": len(subgraph.edges),
            "node_breakdown": node_counts_by_label,
            "edge_breakdown": edge_types_dict,
            "paths": paths,
            "node_details": node_details,
            "fleet": fleets[0].name if fleets else None,
            "trips_completed": completed_cnt,
            "trips_cancelled": cancelled_cnt,
            "regions": [r.name for r in regions],
            "zones": [z.name for z in zones],
            "trips": [{"id": t.id, "name": t.name, "props": t.props} for t in trips],
            "complaints": [
                {
                    "id": c.id,
                    "name": c.name,
                    "category": c.props.get("category", "khiếu nại"),
                    "description": c.props.get("description", ""),
                    "event_time": c.props.get("event_time", ""),
                    "props": c.props,
                }
                for c in complaints
            ],
            "incidents": [
                {
                    "id": i.id,
                    "name": i.name,
                    "incident_type": i.props.get("incident_type", "sự cố"),
                    "description": i.props.get("description", ""),
                    "event_time": i.props.get("event_time", ""),
                    "props": i.props,
                }
                for i in incidents
            ],
            "findings": [
                {
                    "id": f.id,
                    "name": f.name,
                    "status": f.props.get("status", ""),
                    "observed_value": f.props.get("observed_value"),
                    "threshold": f.props.get("threshold"),
                    "description": f.props.get("description", ""),
                    "props": f.props,
                }
                for f in findings
            ],
            "decisions": [
                {
                    "id": d.id,
                    "name": d.name,
                    "action_type": d.props.get("action_type") or d.name,
                    "status": d.props.get("status", ""),
                    "effective_at": d.props.get("effective_at", ""),
                    "description": d.props.get("description", ""),
                    "props": d.props,
                }
                for d in decisions
            ],
            "measurements": [
                {
                    "id": m.id,
                    "name": m.name,
                    "definition_id": m.props.get("definition_id", ""),
                    "value": m.props.get("value"),
                    "unit": m.props.get("unit", ""),
                    "window_start": m.props.get("window_start", ""),
                    "window_end": m.props.get("window_end", ""),
                    "description": m.props.get("description", ""),
                    "props": m.props,
                }
                for m in measurements
            ],
            "summary": summary_text,
        }
    except Exception as e:
        return {"tool": "query_driver_graph", "error": str(e)}


def search_gsm_policies(pipeline: Any, query: str, policy_code: str | None = None, top_k: int = 5) -> dict[str, Any]:
    """Tra cứu các điều khoản quy chế GSM qua BM25 và Qdrant hybrid retrieval."""
    if not pipeline:
        return {"tool": "search_gsm_policies", "error": "Policy search index unavailable."}

    try:
        # Detect any explicit policy codes like P132, P154, P05 from query or parameter
        target_codes: list[str] = []
        if policy_code and policy_code.strip():
            target_codes.append(policy_code.strip().upper())
        for m in re.findall(r"\b(P\d{1,4})\b", query, re.IGNORECASE):
            code_upper = m.strip().upper()
            if code_upper not in target_codes:
                target_codes.append(code_upper)

        search_query = f"{policy_code} {query}".strip() if policy_code else query
        items: list[dict[str, Any]] = []

        # 1. Direct Alias Resolution: if specific policy codes like P132 are identified,
        # fetch directly from pipeline's catalog mapping to prevent lexical mismatch
        if target_codes and hasattr(pipeline, "doc_by_alias"):
            for code in target_codes:
                if code in pipeline.doc_by_alias:
                    doc_info = pipeline.doc_by_alias[code]
                    p_rev = doc_info.get("document_revision_id", "")
                    p_source = doc_info.get("source_id", "")
                    p_title = doc_info.get("title", f"Văn bản quy chế {code}")

                    matching_chunks = [
                        c for c in getattr(pipeline, "chunks", [])
                        if (p_rev and c.document_revision_id == p_rev) or (p_source and c.source_id == p_source)
                    ]
                    if matching_chunks:
                        for c in matching_chunks[:top_k]:
                            items.append({
                                "chunk_id": f"doc-{c.chunk_id}",
                                "policy_alias": code,
                                "title": p_title,
                                "snippet": c.text.strip(),
                            })
                    elif hasattr(pipeline, "release_dir") and p_rev:
                        norm_path = pipeline.release_dir / "public" / "documents" / "normalized" / f"{p_rev}.md"
                        if norm_path.exists():
                            text_content = norm_path.read_text(encoding="utf-8")
                            items.append({
                                "chunk_id": f"doc-{code}",
                                "policy_alias": code,
                                "title": p_title,
                                "snippet": text_content[:1500].strip(),
                            })

        # 2. Hybrid Retrieval (BM25 + Qdrant)
        if getattr(pipeline, "hybrid_searcher", None):
            policy_scope_arg = target_codes if target_codes else ([policy_code] if policy_code else None)
            evidence_list, _ = pipeline.hybrid_searcher.search_and_rerank(
                search_query,
                final_top_k=top_k,
                policy_scope=policy_scope_arg,
            )
            for ev in evidence_list:
                cid = ev.get("evidence_id", "")
                if not any(it.get("chunk_id") == cid for it in items):
                    items.append({
                        "chunk_id": cid,
                        "policy_alias": ev.get("policy_alias", ""),
                        "title": ev.get("policy_title", ""),
                        "snippet": (ev.get("chunk_text") or ev.get("content") or "").strip(),
                    })

        # 3. BM25 Fallback
        if not items and getattr(pipeline, "bm25_index", None):
            results = pipeline.bm25_index.search(search_query, top_k=top_k)
            chunk_map = getattr(pipeline, "chunks", [])
            chunk_dict = {c.chunk_id: c for c in chunk_map} if chunk_map else {}
            for r in results:
                cid = getattr(r, "chunk_id", str(r))
                c_obj = chunk_dict.get(cid)
                text = getattr(c_obj, "text", "") if c_obj else ""
                alias = policy_code or "Quy chế GSM"
                title = "Văn bản quy chế GSM"
                if c_obj and hasattr(pipeline, "doc_catalog_meta"):
                    meta = pipeline.doc_catalog_meta.get(c_obj.document_revision_id) or pipeline.doc_catalog_meta.get(c_obj.source_id) or {}
                    alias = meta.get("alias") or alias
                    title = meta.get("title") or title
                if not any(it.get("chunk_id") == cid for it in items):
                    items.append({
                        "chunk_id": cid,
                        "policy_alias": alias,
                        "title": title,
                        "snippet": text.strip(),
                    })

        unique_policy_codes: list[str] = []
        for it in items[:top_k]:
            pa = (it.get("policy_alias") or "").upper()
            if pa and pa.startswith("P") and pa not in unique_policy_codes:
                unique_policy_codes.append(pa)

        summary_note = ""
        if unique_policy_codes:
            summary_note = f" (Các văn bản quy chế liên quan: [{', '.join(unique_policy_codes)}]. Hãy sử dụng công cụ `get_full_policy_document` với tham số policy_code: '{', '.join(unique_policy_codes)}' để đọc toàn văn)."
        elif target_codes:
            found_aliases = [c for c in target_codes if any((it.get("policy_alias") or "").upper() == c for it in items)]
            if found_aliases:
                summary_note = f" (đã định vị chính xác văn bản [{', '.join(found_aliases)}])"

        reflection_msg = None
        if unique_policy_codes:
            codes_str = ", ".join(unique_policy_codes)
            reflection_msg = (
                f"Đã tìm thấy các văn bản quy chế liên quan: [{codes_str}]. "
                f"Để đọc chi tiết toàn văn điều khoản, hãy gọi công cụ 'get_full_policy_document' với tham số policy_code: '{codes_str}' "
                f"(hỗ trợ nạp cùng lúc nhiều mã văn bản) để nắm toàn bộ quy định trước khi kết luận."
            )

        return {
            "tool": "search_gsm_policies",
            "query": query,
            "policy_code": policy_code or (target_codes[0] if target_codes else None),
            "matched_policy_codes": unique_policy_codes,
            "results_count": len(items[:top_k]),
            "policies": items[:top_k],
            "summary": f"Tìm thấy {len(items[:top_k])} điều khoản quy chế liên quan đến '{query}'{summary_note}.",
            "_reflection_hint": reflection_msg,
        }
    except Exception as e:
        return {"tool": "search_gsm_policies", "error": str(e)}


def get_full_policy_document(pipeline: Any, policy_code: str | list[str], max_chars: int = 8000) -> dict[str, Any]:
    """Lấy toàn văn nội dung một hoặc nhiều văn bản quy chế GSM hoàn chỉnh theo mã quy chế Pxxx (ví dụ: P094, hoặc P094, P027, P017).

    Sau khi tìm kiếm theo ngữ nghĩa để xác định các mã văn bản điều chỉnh, công cụ này cho phép
    Agent nạp toàn bộ văn bản để kiểm tra thấu đáo mọi điều khoản, điều kiện xét thưởng hoặc chế tài.
    Hỗ trợ nạp đơn lẻ một mã hoặc đồng thời nhiều mã quy chế cách nhau bằng dấu phẩy.
    """
    raw_input = policy_code
    codes: list[str] = []
    if isinstance(raw_input, list):
        for item in raw_input:
            codes.extend(re.findall(r"\b(P\d{1,4})\b", str(item).upper()))
    else:
        codes.extend(re.findall(r"\b(P\d{1,4})\b", str(raw_input or "").upper()))

    seen = set()
    unique_codes = [c for c in codes if not (c in seen or seen.add(c))]

    if not unique_codes:
        fallback_code = str(raw_input or "").strip().upper()
        if fallback_code:
            unique_codes = [fallback_code]
        else:
            return {
                "tool": "get_full_policy_document",
                "error": "Vui lòng cung cấp mã văn bản quy chế hợp lệ (ví dụ: 'P094', 'P027', 'P017', 'P154').",
            }

    release_dir = getattr(pipeline, "release_dir", None) or Path("data/gsm-dev-core-0.2.2")
    if not isinstance(release_dir, Path):
        release_dir = Path(str(release_dir))

    def _fetch_single_policy(code: str) -> dict[str, Any] | None:
        title = f"Văn bản quy chế {code}"
        posted_date = ""
        doc_rev_id = ""
        full_text = ""

        # 1. Resolve metadata from pipeline.doc_by_alias if available
        if pipeline and hasattr(pipeline, "doc_by_alias") and code in pipeline.doc_by_alias:
            doc_info = pipeline.doc_by_alias[code]
            title = doc_info.get("title") or title
            posted_date = doc_info.get("posted_date") or ""
            doc_rev_id = doc_info.get("document_revision_id") or ""

        # 2. Fallback to catalog.jsonl if not in doc_by_alias
        if not doc_rev_id and release_dir.exists():
            catalog_path = release_dir / "public" / "documents" / "catalog.jsonl"
            if catalog_path.exists():
                try:
                    for line in catalog_path.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        if (row.get("alias") or "").strip().upper() == code:
                            doc_rev_id = row.get("document_revision_id") or ""
                            posted_date = row.get("posted_date") or posted_date
                            path = row.get("archive_member_path") or ""
                            if path:
                                fname = Path(path).stem
                                title = re.sub(r"^\d+_\d{4}-\d{2}-\d{2}_", "", fname).strip() or title
                            break
                except Exception:
                    pass

        # 3. Read normalized markdown file
        if doc_rev_id and release_dir.exists():
            norm_path = release_dir / "public" / "documents" / "normalized" / f"{doc_rev_id}.md"
            if norm_path.exists():
                try:
                    full_text = norm_path.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

        # 4. Fallback to concatenating chunks if normalized file not found directly
        if not full_text and pipeline and hasattr(pipeline, "chunks"):
            matching_chunks = [
                c for c in getattr(pipeline, "chunks", [])
                if (doc_rev_id and c.document_revision_id == doc_rev_id)
            ]
            if matching_chunks:
                full_text = "\n\n---\n\n".join(c.text.strip() for c in matching_chunks)

        if not full_text:
            return None

        return {
            "code": code,
            "title": title,
            "posted_date": posted_date,
            "doc_rev_id": doc_rev_id,
            "full_text": full_text,
        }

    # If single policy requested, preserve standard single-policy output structure
    if len(unique_codes) == 1:
        single_code = unique_codes[0]
        doc = _fetch_single_policy(single_code)
        if not doc:
            return {
                "tool": "get_full_policy_document",
                "policy_code": single_code,
                "error": f"Không tìm thấy nội dung văn bản quy chế cho mã '{single_code}'. Vui lòng kiểm tra lại mã quy chế trong danh mục.",
            }

        full_text = doc["full_text"]
        total_len = len(full_text)
        is_truncated = False
        if total_len > max_chars:
            content = full_text[:max_chars].strip() + f"\n\n... [Đã cắt bớt vì vượt quá {max_chars} ký tự. Toàn bộ văn bản có {total_len} ký tự]."
            is_truncated = True
        else:
            content = full_text

        return {
            "tool": "get_full_policy_document",
            "policy_code": single_code,
            "title": doc["title"],
            "posted_date": doc["posted_date"],
            "total_characters": total_len,
            "is_truncated": is_truncated,
            "content": content,
            "summary": f"Văn bản quy chế {single_code} ('{doc['title']}', ngày đăng: {doc['posted_date'] or 'N/A'}, độ dài: {total_len} ký tự). Đã tải toàn văn thành công.",
        }

    # If multiple policies requested, aggregate all of them
    found_docs = []
    text_blocks = []
    for c in unique_codes:
        doc = _fetch_single_policy(c)
        if doc:
            found_docs.append({
                "policy_code": doc["code"],
                "title": doc["title"],
                "posted_date": doc["posted_date"],
                "characters": len(doc["full_text"]),
                "content": doc["full_text"][:max_chars],
            })
            block_content = doc["full_text"]
            if len(block_content) > max_chars:
                block_content = block_content[:max_chars].strip() + f"\n\n... [Đã cắt bớt vì vượt quá {max_chars} ký tự]."
            header = f"# VĂN BẢN QUY CHẾ {doc['code']}: {doc['title']}\n- Ngày đăng: {doc['posted_date'] or 'N/A'}"
            text_blocks.append(f"{header}\n\n{block_content}")

    if not found_docs:
        return {
            "tool": "get_full_policy_document",
            "policy_code": ", ".join(unique_codes),
            "error": f"Không tìm thấy nội dung văn bản quy chế cho các mã [{', '.join(unique_codes)}]. Vui lòng kiểm tra lại danh mục.",
        }

    combined_content = ("\n\n" + ("=" * 50) + "\n\n").join(text_blocks)
    codes_str = ", ".join(d["policy_code"] for d in found_docs)
    total_chars = sum(d["characters"] for d in found_docs)

    return {
        "tool": "get_full_policy_document",
        "policy_code": codes_str,
        "policies_count": len(found_docs),
        "documents": found_docs,
        "total_characters": total_chars,
        "content": combined_content,
        "summary": f"Đã nạp toàn văn thành công {len(found_docs)} văn bản quy chế: [{codes_str}] (tổng cộng {total_chars:,} ký tự).",
    }



# =============================================================================
# 3. TOOL SCHEMAS FOR REACT AGENT
# =============================================================================

TOOL_SCHEMAS = [
    {
        "name": "calculate_acceptance_rate",
        "description": "Tính tỷ lệ nhận cuốc (AR = accepted/offered) dưới dạng phân số và tỷ lệ phần trăm chính xác theo chuẩn số học. Kết quả trả về tỷ lệ số học để Agent đối chiếu với quy chế.",
        "parameters": {
            "type": "object",
            "properties": {
                "offered_trips": {"type": "integer", "description": "Tổng số cuốc xe được hệ thống phát đến tài xế"},
                "accepted_trips": {"type": "integer", "description": "Số cuốc xe tài xế đã bấm nhận"},
                "threshold_pct": {"type": "number", "description": "Tùy chọn ngưỡng tỷ lệ nhận cuốc (%) nếu cần đối chiếu phụ trợ"},
            },
            "required": ["offered_trips", "accepted_trips"],
        },
    },
    {
        "name": "calculate_completion_rate",
        "description": "Tính tỷ lệ hoàn thành cuốc (CR = completed/accepted) dưới dạng phân số và tỷ lệ phần trăm chính xác theo chuẩn số học. Kết quả trả về tỷ lệ số học để Agent đối chiếu với quy chế.",
        "parameters": {
            "type": "object",
            "properties": {
                "accepted_trips": {"type": "integer", "description": "Số cuốc xe tài xế đã nhận"},
                "completed_trips": {"type": "integer", "description": "Số cuốc xe tài xế hoàn thành thành công"},
                "threshold_pct": {"type": "number", "description": "Tùy chọn ngưỡng tỷ lệ hoàn thành (%) nếu cần đối chiếu phụ trợ"},
            },
            "required": ["accepted_trips", "completed_trips"],
        },
    },
    {
        "name": "evaluate_daily_revenue",
        "description": "CHỈ SỬ DỤNG KHI người dùng yêu cầu kiểm tra/đối soát doanh số hoặc doanh thu của tài xế so với định mức. KHÔNG sử dụng khi người dùng hỏi về khiếu nại, sự cố, thái độ phục vụ hay lý do sự việc. Hỗ trợ tự động tra cứu doanh thu từ CSDL theo driver_id, date và snapshot_id nếu không truyền revenue_vnd.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_id": {"type": "string", "description": "Mã tài xế (DRV-xxx) hoặc UUID để tự động tra cứu doanh thu từ CSDL"},
                "date": {"type": "string", "description": "Ngày hoặc tháng cần kiểm tra doanh số (định dạng YYYY-MM-DD hoặc YYYY-MM)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu doanh thu nếu có"},
                "revenue_vnd": {"type": "integer", "description": "Tùy chọn tổng doanh số đã biết (VNĐ). Nếu không truyền hoặc <= 0, sẽ tự động tra cứu từ CSDL."},
                "threshold_vnd": {"type": "integer", "description": "Định mức doanh số yêu cầu theo quy chế (VNĐ, ví dụ: 720000 hoặc 900000)"},
            },
            "required": [],
        },
    },
    {
        "name": "calculate_cancel_rate",
        "description": "Tính tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d = cancelled / total_trips) theo định nghĩa M01 và đối chiếu với ngưỡng trần quy chế (threshold_pct). LƯU Ý QUAN TRỌNG: Bắt buộc phải gọi `get_driver_trip_summary` (hoặc `get_driver_trip_metrics`) trước để lấy số liệu thực tế, hoặc truyền `driver_identifier` và `snapshot_id` để hệ thống tự động đối soát chính xác từ CSDL. TUYỆT ĐỐI CẤM tự bịa ra số cuốc xe!",
        "parameters": {
            "type": "object",
            "properties": {
                "cancelled_trips": {"type": "integer", "description": "Số cuốc bị hủy lấy từ số liệu thực tế hệ thống"},
                "total_trips": {"type": "integer", "description": "Tổng số cuốc phát sinh (nếu không có thì hệ thống tự tính từ cancelled_trips + completed_trips)"},
                "completed_trips": {"type": "integer", "description": "Số cuốc hoàn thành thành công lấy từ số liệu thực tế"},
                "threshold_pct": {"type": "number", "description": "Ngưỡng tỷ lệ hủy tối đa cho phép theo quy chế (ví dụ: 20 hoặc 15)"},
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx) hoặc UUID để hệ thống tự động đối soát và lấy số liệu chính xác từ CSDL"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot thời gian cần đối soát số liệu nếu có"},
                "date": {"type": "string", "description": "Ngày hoặc tháng cần đối soát số liệu"},
            },
            "required": [],
        },
    },
    {
        "name": "evaluate_rating_condition",
        "description": "CHỈ SỬ DỤNG KHI người dùng yêu cầu kiểm tra/đối chiếu điểm sao đánh giá của tài xế với quy chế hoặc tiêu chuẩn chất lượng. KHÔNG sử dụng cho câu hỏi tra cứu khiếu nại, sự cố, thái độ phục vụ hay chi tiết chuyến xe.",
        "parameters": {
            "type": "object",
            "properties": {
                "rating_stars": {"type": "number", "description": "Điểm đánh giá sao của tài xế (ví dụ: 4.9)"},
                "threshold": {"type": "number", "description": "Ngưỡng điểm sao quy định trong văn bản quy chế (ví dụ: 4.85 hoặc 4.8)"},
                "operator": {"type": "string", "enum": [">", ">=", "<", "<="], "description": "Toán tử so sánh (mặc định: >=)"},
            },
            "required": ["rating_stars"],
        },
    },
    {
        "name": "calculate_revenue_charge",
        "description": "Tính mức giảm trừ bù trừ doanh thu theo công thức P154 / Task T02: max(280_000 - revenue_vnd, 0) // 5. Có thể truyền thêm chương trình, vùng và ngày vận doanh để kiểm tra điều kiện áp dụng.",
        "parameters": {
            "type": "object",
            "properties": {
                "revenue_vnd": {"type": "integer", "description": "Doanh thu của tài xế (VNĐ)"},
                "program": {"type": "string", "description": "Chương trình tài xế (ví dụ: bike_partner, taxi_driver)"},
                "operating_region": {"type": "string", "description": "Khu vực hoạt động (ví dụ: Hà Nội)"},
                "is_operating_day": {"type": "boolean", "description": "Có phải là ngày vận doanh tiêu chuẩn không (RM_OPDAY)"},
            },
            "required": ["revenue_vnd"],
        },
    },
    {
        "name": "calculate_violation_penalty_points",
        "description": "Tính tổng điểm phạt tích lũy từ các lỗi vi phạm và xác định biện pháp chế tài tương ứng theo thang quy chế GSM (Nhắc nhở, Cảnh cáo, Khóa app tạm thời, Chấm dứt hợp đồng).",
        "parameters": {
            "type": "object",
            "properties": {
                "points": {"type": "integer", "description": "Tổng điểm phạt hoặc điểm của lỗi vi phạm cần tính"},
                "violation_count": {"type": "integer", "description": "Số lượng vi phạm phát sinh"},
                "rule_codes": {"type": "array", "items": {"type": "string"}, "description": "Danh sách mã quy chế hoặc lỗi vi phạm liên quan"},
            },
            "required": ["points"],
        },
    },
    {
        "name": "calculate_attendance_hours",
        "description": "Tính tổng số giờ làm việc / ca trực của tài xế và đối chiếu với định mức ngày công chuẩn (8 giờ/ca hoặc định mức ngày công theo quy chế P172).",
        "parameters": {
            "type": "object",
            "properties": {
                "hours_worked": {"type": "number", "description": "Tổng số giờ làm việc thực tế ghi nhận"},
                "standard_hours_per_day": {"type": "number", "description": "Định mức giờ/ngày công tiêu chuẩn (mặc định 8.0 giờ)"},
                "required_days": {"type": "integer", "description": "Số ngày công định mức yêu cầu để đối chiếu đạt/không đạt"},
            },
            "required": ["hours_worked"],
        },
    },
    {
        "name": "get_driver_profile",
        "description": "Tra cứu hồ sơ nhân sự cơ bản của tài xế (mã nhân viên, họ tên, số điện thoại, email, đội xe, phương tiện, biển số, chương trình, trạng thái, đánh giá sao trung bình).",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế, hoặc UUID"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_driver_trip_summary",
        "description": "Tra cứu tổng hợp số liệu chuyến đi (tổng số chuyến, số chuyến hoàn thành, số chuyến bị hủy, tỷ lệ hủy cancel_rate_30d, số sự cố vi phạm, số khiếu nại khách hàng) của tài xế theo ngày/tháng/năm cụ thể hoặc theo snapshot/toàn kỳ.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế, hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần tra cứu số liệu (ngày YYYY-MM-DD, tháng YYYY-MM hoặc năm YYYY)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu số liệu nếu có"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_driver_trip_metrics",
        "description": "Bí danh (alias) của `get_driver_trip_summary`. Lấy số liệu vận hành chuyến đi: tổng số chuyến đi, số chuyến hoàn thành, số chuyến bị hủy, tỷ lệ hủy cancel_rate_30d, số sự cố vi phạm, số khiếu nại khách hàng của tài xế trong một snapshot và khoảng thời gian cụ thể (ngày/tháng/năm).",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế, hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần tra cứu số liệu (ngày YYYY-MM-DD, tháng YYYY-MM hoặc năm YYYY)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu số liệu nếu có"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_cancelled_trips_detail",
        "description": "Tra cứu danh sách chi tiết các chuyến đi bị hủy của tài xế (mã chuyến, thời gian phát sinh, lý do hủy reason_code, bên hủy cancel_party ví dụ: tài xế tự hủy driver_request hay khách hủy) theo ngày/tháng/năm hoặc snapshot.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế, hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần tra cứu danh sách hủy (ngày YYYY-MM-DD, tháng YYYY-MM hoặc năm YYYY)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu danh sách hủy nếu có"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_driver_operational_stats",
        "description": "Lấy số liệu vận hành thực tế các cuốc xe (phát, nhận, hoàn thành, hủy) và tổng doanh thu của tài xế theo ngày (YYYY-MM-DD), tháng/kỳ (YYYY-MM) và snapshot từ CSDL để phục vụ tính toán các chỉ số vận hành và đối chiếu quy chế.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_id": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "date": {"type": "string", "description": "Ngày hoặc tháng cần tra cứu (định dạng YYYY-MM-DD hoặc YYYY-MM)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu số liệu nếu có"},
            },
            "required": ["driver_id"],
        },
    },
    {
        "name": "get_recent_incidents",
        "description": "Lấy danh sách sự cố/vi phạm gần nhất của tài xế kèm TỔNG SỐ LƯỢNG (total_count), tên sự cố, phân loại và nội dung chi tiết của từng sự cố theo snapshot và mốc thời gian.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần lọc sự cố (ngày YYYY-MM-DD hoặc tháng YYYY-MM)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot thời gian cần tra cứu nếu có"},
                "limit": {"type": "integer", "description": "Số lượng sự cố tối đa cần lấy (mặc định 10)"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_incident_detail",
        "description": "Tra cứu nội dung mô tả chi tiết của một sự cố theo mã sự cố (incident_id). Dùng công cụ này khi cần đọc sâu thêm biên bản của một sự cố cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Mã sự cố cần tra cứu chi tiết (ví dụ: 'INC-001' hoặc 'inc-xxx')"},
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "get_recent_complaints",
        "description": "Lấy danh sách khiếu nại/phản ánh khách hàng của tài xế kèm TỔNG SỐ LƯỢNG (total_count), phân loại và nội dung mô tả chi tiết của từng khiếu nại theo snapshot và mốc thời gian.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần lọc khiếu nại (ngày YYYY-MM-DD hoặc tháng YYYY-MM)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot thời gian cần tra cứu nếu có"},
                "limit": {"type": "integer", "description": "Số lượng khiếu nại tối đa cần lấy (mặc định 10)"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "get_complaint_detail",
        "description": "Tra cứu nội dung mô tả chi tiết của một khiếu nại/phản ánh khách hàng theo mã khiếu nại (complaint_id). Dùng công cụ này khi cần đọc sâu thêm một khiếu nại cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "complaint_id": {"type": "string", "description": "Mã khiếu nại cần tra cứu chi tiết (ví dụ: 'CMP-001' hoặc 'comp-xxx')"},
            },
            "required": ["complaint_id"],
        },
    },
    {
        "name": "get_driver_incidents_and_complaints",
        "description": "Tra cứu chi tiết các sự cố vi phạm vận hành (incidents) và khiếu nại/phản ánh từ khách hàng (complaints, feedback tiêu cực, đánh giá sao thấp) của tài xế từ CSDL.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "date": {"type": "string", "description": "Thời gian cần lọc (ngày YYYY-MM-DD hoặc tháng YYYY-MM)"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot cần tra cứu nếu có"},
                "limit": {"type": "integer", "description": "Số lượng bản ghi tối đa (mặc định 20)"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "query_driver_graph",
        "description": "Truy vấn đồ thị tri thức (Knowledge Graph) có định hướng từ nút Tài xế. Xung quanh tài xế có các nhánh thực thể & cạnh phục vụ các câu hỏi chuyên biệt:\n- 'location': Khu vực/thành phố hoạt động (Driver->Region) và quận/zone cụ thể qua các chuyến đi gần nhất (Driver->Trip->Zone).\n- 'complaints': Phản ánh/khiếu nại của khách hàng (Driver->Complaint->Trip), hỗ trợ semantic_query lọc nội dung phàn nàn và xác định chuyến bị khiếu nại.\n- 'incidents': Biên bản sự cố vận hành/kỹ thuật (Driver->Incident->Trip/PolicyRule), hỗ trợ semantic_query lọc sự cố.\n- 'fleet': Đội xe, Hub điều hành và địa bàn quản lý (Driver->Fleet->Region).\n- 'vehicle': Phương tiện, dòng xe, biển số và lịch sử bảo dưỡng (Driver->Vehicle->VehicleType, MaintenanceEvent).\n- 'kpi_metrics': Các chỉ số vận hành chuẩn hóa theo kỳ (Driver->Measurement: AR, CR, cancel_rate_30d, rating).\n- 'enforcement': Quyết định chế tài & điều khoản vi phạm (Driver->EnforcementDecision->ViolationFinding->PolicyRule).\nBẮT BUỘC chọn 'focus' phù hợp hoặc truyền 'semantic_query' để lọc chính xác và tránh bùng nổ dữ liệu.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {
                    "type": "string",
                    "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"
                },
                "focus": {
                    "type": "string",
                    "enum": ["location", "complaints", "incidents", "fleet", "vehicle", "kpi_metrics", "enforcement", "all"],
                    "description": "Nhánh định hướng duyệt đồ thị: 'location' (khu vực, thành phố, zone đón trả), 'complaints' (khiếu nại khách hàng & chuyến xe liên quan), 'incidents' (sự cố kỹ thuật/vận hành), 'fleet' (đội xe/hub), 'vehicle' (xe & lịch sử bảo dưỡng), 'kpi_metrics' (chỉ số AR/CR/Cancel), 'enforcement' (chế tài/kỷ luật), 'all' (tổng hợp có giới hạn)"
                },
                "semantic_query": {
                    "type": "string",
                    "description": "Nội dung người dùng hỏi để so khớp ngữ nghĩa và lọc các node có mô tả (như Complaint, Incident). Ví dụ: 'thái độ phục vụ cộc cằn', 'lỗi pin', 'chạy quá tốc độ', 'hủy chuyến'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Số lượng node/bản ghi con tối đa cho mỗi nhánh (mặc định: 10 chuyến đi, 5 khiếu nại/sự cố liên quan nhất)"
                },
                "date": {
                    "type": "string",
                    "description": "Khoảng thời gian cần lọc các nút và cạnh (ngày YYYY-MM-DD hoặc tháng YYYY-MM, ví dụ '2026-08')"
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "Mã snapshot thời gian cần tra cứu đồ thị nếu có"
                },
                "target_node_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tùy chọn danh sách loại node đích cần duyệt (ví dụ: ['Region', 'Zone', 'Trip'] hoặc ['Complaint', 'Trip'] hoặc ['Vehicle', 'MaintenanceEvent'])"
                },
                "edge_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tùy chọn danh sách loại cạnh cho phép đi qua (ví dụ: ['OPERATES_IN', 'PERFORMED', 'PICKUP_IN', 'DROPOFF_IN'])"
                }
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "search_gsm_policies",
        "description": "Tìm kiếm ngữ nghĩa (semantic search) theo từ khóa/chủ đề trong kho 224 văn bản quy chế GSM để tìm các đoạn trích dẫn (chunk) phù hợp và xác định các mã quy chế điều chỉnh liên quan (như P094, P027, P017, P154...).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa hoặc câu hỏi cần tra cứu quy chế"},
                "policy_code": {"type": "string", "description": "Tùy chọn mã quy chế nếu muốn giới hạn phạm vi tìm kiếm (ví dụ: P154, P151, P05, P23)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_full_policy_document",
        "description": "Lấy và đọc toàn văn nội dung một hoặc nhiều văn bản quy chế GSM hoàn chỉnh theo mã quy chế Pxxx (ví dụ: 'P094' hoặc 'P094, P027, P017'). Dùng công cụ này sau khi tìm kiếm chunk để đọc trọn vẹn toàn bộ các điều khoản, đối tượng áp dụng và chế tài của các văn bản đó.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_code": {"type": "string", "description": "Mã văn bản quy chế cần đọc toàn văn (ví dụ: 'P094' hoặc nhiều mã 'P094, P027, P017'). Bắt buộc truyền mã Pxxx."},
                "max_chars": {"type": "integer", "description": "Số lượng ký tự tối đa cho mỗi văn bản (mặc định 8000 ký tự)"},
            },
            "required": ["policy_code"],
        },
    },
]
