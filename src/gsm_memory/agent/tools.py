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

    accepted = max(0, min(accepted_trips, offered_trips))
    frac = Fraction(accepted, offered_trips)
    rate_pct = round(float(frac) * 100.0, 2)

    passed = None
    if threshold_pct is not None:
        thresh_val = float(threshold_pct)
        passed = rate_pct >= thresh_val
        summary = (
            f"Tỷ lệ nhận cuốc (AR): {rate_pct}% ({accepted}/{offered_trips} cuốc = {frac.numerator}/{frac.denominator}). "
            f"Ngưỡng đối chiếu: >= {thresh_val}%. "
            f"Kết quả: {'ĐẠT' if passed else f'KHÔNG ĐẠT (thiếu {round(thresh_val - rate_pct, 2)}%)'}."
        )
    else:
        summary = f"Tỷ lệ nhận cuốc (AR): {rate_pct}% ({accepted}/{offered_trips} cuốc = {frac.numerator}/{frac.denominator})."

    return {
        "tool": "calculate_acceptance_rate",
        "offered_trips": offered_trips,
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

    completed = max(0, min(completed_trips, accepted_trips))
    frac = Fraction(completed, accepted_trips)
    rate_pct = round(float(frac) * 100.0, 2)

    passed = None
    if threshold_pct is not None:
        thresh_val = float(threshold_pct)
        passed = rate_pct >= thresh_val
        summary = (
            f"Tỷ lệ hoàn thành cuốc (CR): {rate_pct}% ({completed}/{accepted_trips} cuốc = {frac.numerator}/{frac.denominator}). "
            f"Ngưỡng đối chiếu: >= {thresh_val}%. "
            f"Kết quả: {'ĐẠT' if passed else f'KHÔNG ĐẠT (thiếu {round(thresh_val - rate_pct, 2)}%)'}."
        )
    else:
        summary = f"Tỷ lệ hoàn thành cuốc (CR): {rate_pct}% ({completed}/{accepted_trips} cuốc = {frac.numerator}/{frac.denominator})."

    return {
        "tool": "calculate_completion_rate",
        "accepted_trips": accepted_trips,
        "completed_trips": completed,
        "rate_fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_pct": rate_pct,
        "threshold_pct": threshold_pct,
        "passed": passed,
        "summary": summary,
    }


def evaluate_daily_revenue(
    revenue_vnd: int,
    threshold_vnd: int | None = None,
    date: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Kiểm tra doanh số ngày so với định mức (threshold_vnd) được tra cứu từ văn bản quy chế.

    Nếu không truyền threshold_vnd, trả về thông tin doanh số thực tế đã định dạng.
    """
    diff_vnd = None
    passed = None
    date_str = f" ngày {date}" if date else ""
    if threshold_vnd is not None:
        thresh_val = int(threshold_vnd)
        passed = revenue_vnd >= thresh_val
        diff_vnd = revenue_vnd - thresh_val
        summary = (
            f"Doanh số{date_str}: {revenue_vnd:,.0f} VNĐ. "
            f"Định mức quy chế yêu cầu: {thresh_val:,.0f} VNĐ. "
            f"Kết quả: {'ĐẠT ĐỊNH MỨC' if passed else f'KHÔNG ĐẠT (thiếu {abs(diff_vnd):,.0f} VNĐ)'}."
        )
    else:
        summary = f"Doanh số ghi nhận{date_str}: {revenue_vnd:,.0f} VNĐ."

    return {
        "tool": "evaluate_daily_revenue",
        "date": date,
        "revenue_vnd": revenue_vnd,
        "threshold_vnd": threshold_vnd,
        "diff_vnd": diff_vnd,
        "passed": passed,
        "summary": summary,
    }


def calculate_cancel_rate(cancelled_trips: int, total_trips: int) -> dict[str, Any]:
    """Tính tỷ lệ hủy chuyến chuẩn xác số học theo definition M01 (cancel_rate_30d)."""
    if total_trips <= 0:
        return {
            "tool": "calculate_cancel_rate",
            "metric_status": "undefined",
            "cancel_rate": None,
            "rate_pct": 0.0,
            "summary": "Tỷ lệ hủy chuyến: undefined (mẫu số bằng 0 do không có chuyến đi ghi nhận).",
        }
    cancelled = max(0, min(cancelled_trips, total_trips))
    frac = Fraction(cancelled, total_trips)
    pct = round(float(frac) * 100.0, 2)
    return {
        "tool": "calculate_cancel_rate",
        "metric_status": "valid",
        "cancelled_trips": cancelled,
        "total_trips": total_trips,
        "fraction": f"{frac.numerator}/{frac.denominator}",
        "rate_pct": pct,
        "summary": f"Tỷ lệ hủy chuyến (cancel_rate_30d) = {frac.numerator}/{frac.denominator} ({cancelled}/{total_trips} chuyến) = {pct}%.",
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
    """
    rating_clean = round(float(rating_stars), 2)
    if threshold is not None:
        thresh_val = float(threshold)
        if operator == ">":
            passed = rating_clean > thresh_val
        elif operator == "<":
            passed = rating_clean < thresh_val
        elif operator == "<=":
            passed = rating_clean <= thresh_val
        else:
            passed = rating_clean >= thresh_val

        summary = f"Đánh giá sao: {rating_clean:.2f}/5.0 (Ngưỡng quy chế: {operator} {thresh_val}) -> {'ĐẠT ĐIỀU KIỆN' if passed else 'KHÔNG ĐẠT'}."
    else:
        passed = None
        summary = f"Đánh giá sao ghi nhận: {rating_clean:.2f}/5.0★. (Chưa cung cấp ngưỡng quy chế để đối chiếu)."

    return {
        "tool": "evaluate_rating_condition",
        "rating_stars": rating_clean,
        "threshold": threshold,
        "operator": operator if threshold is not None else None,
        "passed": passed,
        "summary": summary,
    }


def calculate_revenue_charge(revenue_vnd: int) -> dict[str, Any]:
    """Tính khoản giảm trừ/phí bù doanh thu theo công thức chuẩn: max(280_000 - revenue_vnd, 0) // 5."""
    charge = max(280_000 - revenue_vnd, 0) // 5
    return {
        "tool": "calculate_revenue_charge",
        "revenue_vnd": revenue_vnd,
        "charge_vnd": charge,
        "summary": f"Mức giảm trừ bảo lưu doanh thu: {charge:,.0f} VNĐ (từ doanh thu {revenue_vnd:,.0f} VNĐ).",
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


def get_driver_trip_metrics(
    db_repo: Any,
    driver_identifier: str,
    snapshot_id: str | None = None,
    date: str | None = None,
    pipeline: Any = None,
) -> dict[str, Any]:
    """Tra cứu tổng hợp số liệu chuyến đi (tổng số chuyến, hoàn thành, hủy, tỷ lệ hủy cancel_rate_30d) theo ngày/tháng/năm hoặc snapshot."""
    if not db_repo:
        return {"tool": "get_driver_trip_metrics", "error": "Database repository is unavailable."}

    driver = db_repo.get_driver(driver_identifier) or db_repo.find_driver_in_text(driver_identifier)
    if not driver:
        return {
            "tool": "get_driver_trip_metrics",
            "driver_identifier": driver_identifier,
            "found": False,
            "summary": f"Không tìm thấy tài xế '{driver_identifier}' để tra cứu số liệu chuyến đi.",
        }

    date_clean = ""
    date_prefix = ""
    period_label = ""
    if date:
        date_clean = str(date).strip()
        m_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_clean)
        if m_dmy:
            d, m, y = m_dmy.groups()
            date_clean = f"{y}-{int(m):02d}-{int(d):02d}"
        if len(date_clean) == 7:
            date_prefix = date_clean[:7]
            period_label = f"Tháng {date_prefix}"
        elif len(date_clean) >= 10:
            date_prefix = date_clean[:10]
            period_label = f"Ngày {date_prefix}"
        elif len(date_clean) == 4:
            date_prefix = date_clean[:4]
            period_label = f"Năm {date_prefix}"
        else:
            date_prefix = date_clean
            period_label = f"Thời gian {date_prefix}"

    completed_trips = driver.completed_trips_count
    cancelled_trips = driver.cancelled_trips_count
    cancel_rate_30d = driver.cancellation_rate_30d
    total_trips = completed_trips + cancelled_trips
    snapshot_total_trips = total_trips
    snapshot_completed_trips = completed_trips
    snapshot_cancelled_trips = cancelled_trips
    snapshot_cancel_rate_30d = cancel_rate_30d
    source_kind = "db_baseline"

    # Priority A: Check if pipeline has Knowledge Graph subgraph for this driver & snapshot
    if pipeline and hasattr(pipeline, "expand_subgraph_bfs"):
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
                elif date_prefix or snapshot_id:
                    completed_trips = 0
                    cancelled_trips = 0
                    total_trips = 0
                    cancel_rate_30d = 0.0
                    source_kind = "kg_snapshot"
        except Exception:
            pass

    if source_kind == "db_baseline" and db_repo and hasattr(db_repo, "get_driver_snapshot_metrics"):
        # Priority B: Query snapshot/date-specific metrics from SQLite
        snap_metrics = db_repo.get_driver_snapshot_metrics(driver.driver_id, snapshot_id=snapshot_id, date=date_prefix or None)
        if snap_metrics is not None:
            completed_trips = snap_metrics["completed_trips"]
            cancelled_trips = snap_metrics["cancelled_trips"]
            total_trips = snap_metrics["total_trips"]
            cancel_rate_30d = snap_metrics["cancel_rate"]
            snapshot_total_trips = snap_metrics.get("snapshot_total_trips", snapshot_total_trips)
            snapshot_completed_trips = snap_metrics.get("snapshot_completed_trips", snapshot_completed_trips)
            snapshot_cancelled_trips = snap_metrics.get("snapshot_cancelled_trips", snapshot_cancelled_trips)
            snapshot_cancel_rate_30d = snap_metrics.get("snapshot_cancel_rate", snapshot_cancel_rate_30d)
            source_kind = "db_filtered" if (date_prefix or snapshot_id) else "db_snapshot"

    time_filter_label = f" ({period_label})" if period_label else ""
    snap_label = f" (Snapshot: {snapshot_id[:8]}...)" if snapshot_id else ""
    cancel_pct = round(cancel_rate_30d * 100, 2)
    snap_pct = round(snapshot_cancel_rate_30d * 100, 2)

    if total_trips == 0 and (date or snapshot_id):
        if snapshot_total_trips > 0:
            summary_text = (
                f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
                f"Trong {period_label or 'thời gian chỉ định'} không phát sinh chuyến xe mới (0 chuyến). "
                f"Tuy nhiên, trong kỳ đánh giá 30 ngày gần nhất của Snapshot: "
                f"Tài xế có tổng cộng {snapshot_total_trips} chuyến xe ({snapshot_completed_trips} hoàn thành, {snapshot_cancelled_trips} bị hủy), "
                f"tỷ lệ hủy chuyến (cancel_rate_30d) là {snap_pct}% ({snapshot_cancelled_trips}/{snapshot_total_trips} chuyến)."
            )
        else:
            summary_text = (
                f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
                f"Không ghi nhận chuyến xe nào phát sinh trong khoảng thời gian này (0 cuốc xe)."
            )
    else:
        summary_text = (
            f"Số liệu vận hành tài xế {driver.full_name} ({driver.driver_code}){time_filter_label}{snap_label}: "
            f"Tổng cộng {total_trips} chuyến xe ({completed_trips} chuyến hoàn thành, {cancelled_trips} chuyến bị hủy). "
            f"Tỷ lệ hủy chuyến (cancel_rate_30d): {cancel_pct}% ({cancelled_trips}/{total_trips} chuyến)."
        )

    return {
        "tool": "get_driver_trip_metrics",
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
        "summary": summary_text,
    }


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

    date_clean = ""
    date_prefix = ""
    period_label = ""
    if date:
        date_clean = str(date).strip()
        m_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_clean)
        if m_dmy:
            d, m, y = m_dmy.groups()
            date_clean = f"{y}-{int(m):02d}-{int(d):02d}"
        if len(date_clean) == 7:
            date_prefix = date_clean[:7]
            period_label = f"Tháng {date_prefix}"
        elif len(date_clean) >= 10:
            date_prefix = date_clean[:10]
            period_label = f"Ngày {date_prefix}"
        elif len(date_clean) == 4:
            date_prefix = date_clean[:4]
            period_label = f"Năm {date_prefix}"
        else:
            date_prefix = date_clean
            period_label = f"Thời gian {date_prefix}"

    cancelled_items: list[dict[str, Any]] = []

    # Priority A: Check if pipeline has Knowledge Graph subgraph
    if pipeline and hasattr(pipeline, "expand_subgraph_bfs"):
        try:
            subgraph = pipeline.expand_subgraph_bfs(driver_id=driver.driver_id, snapshot_id=snapshot_id)
            if subgraph and subgraph.nodes:
                trips = [n for n in subgraph.nodes if n.label == "Trip" and n.props.get("outcome") == "cancelled"]
                all_snap_canc = list(trips)
                if date_prefix:
                    trips = [
                        t for t in trips
                        if (t.props.get("event_time") or t.props.get("start_time") or t.props.get("date") or t.props.get("valid_at") or "").startswith(date_prefix)
                    ]
                if not trips and all_snap_canc and date_prefix:
                    # Provide rolling 30d window cancelled trips if specified date has 0
                    trips = all_snap_canc
                for t in trips:
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
        except Exception:
            pass

    # Priority B: Query SQLite trips table if KG didn't return or not available
    if not cancelled_items and db_repo and hasattr(db_repo, "get_trips"):
        try:
            db_trips = db_repo.get_trips(driver_id=driver.driver_id, outcome="cancelled", limit=100)
            if snapshot_id:
                filtered = [t for t in db_trips if t.snapshot_id == snapshot_id or not t.snapshot_id]
                if filtered:
                    db_trips = filtered
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


def get_driver_daily_stats(db_repo: Any, driver_id: str, date: str) -> dict[str, Any]:
    """Lấy danh sách cuốc xe và tổng hợp doanh số, số chuyến của tài xế trong một ngày cụ thể."""
    if not db_repo:
        return {"tool": "get_driver_daily_stats", "error": "Database repository is unavailable."}

    date_clean = str(date or "").strip()
    m_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_clean)
    if m_dmy:
        d, m, y = m_dmy.groups()
        date_clean = f"{y}-{int(m):02d}-{int(d):02d}"
    date_prefix = date_clean[:7] if len(date_clean) == 7 else date_clean[:10]

    # Resolve driver by identifier/code/name if possible
    driver = None
    if hasattr(db_repo, "get_driver"):
        driver = db_repo.get_driver(driver_id)
    if not driver and hasattr(db_repo, "find_driver_in_text"):
        driver = db_repo.find_driver_in_text(driver_id)
    if not driver and hasattr(db_repo, "get_driver_by_code"):
        driver = db_repo.get_driver_by_code(driver_id)

    target_id = driver.driver_id if driver else driver_id
    trips = db_repo.get_trips(driver_id=target_id, limit=200) if hasattr(db_repo, "get_trips") else []

    # Filter trips matching the target date or month
    day_trips = [t for t in trips if (getattr(t, "start_time", None) or "").startswith(date_prefix)]

    completed_cnt = sum(1 for t in day_trips if t.outcome == "completed")
    cancelled_cnt = sum(1 for t in day_trips if t.outcome == "cancelled")
    total_revenue = sum(t.fare_amount for t in day_trips if t.outcome == "completed")

    total_trips = len(day_trips)
    accepted_cnt = total_trips
    if driver and getattr(driver, "acceptance_rate", None) and driver.acceptance_rate > 0 and total_trips > 0:
        offered_cnt = int(round(accepted_cnt / driver.acceptance_rate))
    else:
        offered_cnt = max(total_trips, total_trips + (1 if cancelled_cnt > 0 else 0))

    period_label = f"Tháng {date_prefix}" if len(date_prefix) == 7 else f"Ngày {date_prefix}"
    driver_name = driver.full_name if driver else target_id
    driver_code = driver.driver_code if driver else target_id

    summary = (
        f"{period_label}: Tài xế {driver_name} ({driver_code}) ghi nhận {total_trips} cuốc xe "
        f"(phát: {offered_cnt}, nhận: {accepted_cnt}, hoàn thành: {completed_cnt}, hủy: {cancelled_cnt}). "
        f"Tổng doanh thu ghi nhận: {total_revenue:,.0f} VNĐ."
    )

    return {
        "tool": "get_driver_daily_stats",
        "driver_id": target_id,
        "driver_code": driver_code,
        "full_name": driver_name,
        "date": date_prefix,
        "trips_count": total_trips,
        "completed_trips": completed_cnt,
        "cancelled_trips": cancelled_cnt,
        "total_revenue_vnd": total_revenue,
        "offered_trips": offered_cnt,
        "accepted_trips": accepted_cnt,
        "summary": summary,
    }


def query_driver_graph(pipeline: Any, driver_id: str, snapshot_id: str | None = None) -> dict[str, Any]:
    """Tra cứu đồ thị tri thức (Knowledge Graph) cho tài xế: trích xuất các nút và cạnh liên kết quan hệ."""
    if not pipeline:
        return {"tool": "query_driver_graph", "error": "Pipeline unavailable."}

    try:
        # Resolve driver code/name to UUID if needed
        driver_code = ""
        driver_name = ""
        if getattr(pipeline, "db_repo", None) and driver_id:
            d_found = pipeline.db_repo.find_driver_in_text(driver_id) or pipeline.db_repo.get_driver_by_code(driver_id) or pipeline.db_repo.get_driver(driver_id)
            if d_found:
                driver_code = d_found.driver_code
                driver_name = d_found.full_name
                driver_id = d_found.driver_id

        subgraph = None
        if hasattr(pipeline, "expand_subgraph_bfs"):
            subgraph = pipeline.expand_subgraph_bfs(driver_id=driver_id, snapshot_id=snapshot_id)
        elif hasattr(pipeline, "expand_subgraph"):
            subgraph = pipeline.expand_subgraph(seed_id=driver_id)

        # Fallback to local SQLite repo to build nodes and edges if subgraph is empty
        if (not subgraph or not subgraph.nodes) and getattr(pipeline, "db_repo", None) and driver_id:
            d_rec = pipeline.db_repo.get_driver(driver_id)
            if d_rec:
                from gsm_memory.agent.conversational_pipeline import Subgraph, SubgraphNode, SubgraphEdge
                subgraph = Subgraph(seed_id=driver_id, snapshot_id=snapshot_id, nodes=[], edges=[])
                driver_name = driver_name or d_rec.full_name
                driver_code = driver_code or d_rec.driver_code
                subgraph.nodes.append(
                    SubgraphNode(
                        id=driver_id,
                        label="Driver",
                        name=d_rec.full_name,
                        props={"code": d_rec.driver_code, "depot": d_rec.depot_name, "vehicle": d_rec.vehicle_model, "rating": d_rec.rating_avg}
                    )
                )
                if d_rec.depot_name:
                    fleet_id = f"fleet-{d_rec.depot_name[:8]}"
                    subgraph.nodes.append(SubgraphNode(id=fleet_id, label="Fleet", name=d_rec.depot_name, props={}))
                    subgraph.edges.append(SubgraphEdge(start_id=driver_id, end_id=fleet_id, rel_type="ASSIGNED_TO_FLEET", props={}))
                trips_db = pipeline.db_repo.get_trips(driver_id=driver_id, limit=50)
                for t in trips_db:
                    subgraph.nodes.append(
                        SubgraphNode(
                            id=t.trip_id,
                            label="Trip",
                            name=f"Chuyến {t.trip_id[:8]}",
                            props={"outcome": t.outcome, "reason_code": t.reason_code, "fare": t.fare_amount}
                        )
                    )
                    subgraph.edges.append(
                        SubgraphEdge(
                            start_id=driver_id,
                            end_id=t.trip_id,
                            rel_type="PERFORMED_TRIP",
                            props={"outcome": t.outcome}
                        )
                    )

        if not subgraph:
            return {"tool": "query_driver_graph", "error": "Không thể mở rộng đồ thị cho tài xế này."}

        # Cache on pipeline for downstream UI graph visualizer
        setattr(pipeline, "last_subgraph", subgraph)

        incidents = [n for n in subgraph.nodes if n.label == "Incident"]
        fleets = [n for n in subgraph.nodes if n.label in ("Fleet", "Hub")]
        trips = [n for n in subgraph.nodes if n.label == "Trip"]
        vehicles = [n for n in subgraph.nodes if n.label == "Vehicle"]
        shifts = [n for n in subgraph.nodes if n.label == "Shift"]
        complaints = [n for n in subgraph.nodes if n.label == "CustomerComplaint"]
        maints = [n for n in subgraph.nodes if n.label == "MaintenanceEvent"]
        rules = [n for n in subgraph.nodes if n.label == "PolicyRule"]
        decisions = [n for n in subgraph.nodes if n.label == "RewardPenalty"]

        inc_list = [{"name": inc.name, "description": inc.props.get("description", "")} for inc in incidents]
        fleet_name = fleets[0].name if fleets else None

        node_counts_by_label: dict[str, int] = {}
        for n in subgraph.nodes:
            node_counts_by_label[n.label] = node_counts_by_label.get(n.label, 0) + 1

        edge_types: dict[str, int] = {}
        for e in subgraph.edges:
            edge_types[e.rel_type] = edge_types.get(e.rel_type, 0) + 1

        completed_cnt = sum(1 for t in trips if t.props.get("outcome") == "completed")
        cancelled_cnt = sum(1 for t in trips if t.props.get("outcome") == "cancelled")

        label_summary_parts = [f"{lbl}: {cnt}" for lbl, cnt in node_counts_by_label.items()]
        rel_summary_parts = [f"{rel}: {cnt}" for rel, cnt in edge_types.items()]

        sample_nodes = [{"id": n.id[:8], "label": n.label, "name": n.name} for n in subgraph.nodes[:10]]
        sample_edges = [{"start": e.start_id[:8], "end": e.end_id[:8], "rel_type": e.rel_type} for e in subgraph.edges[:10]]

        summary_lines = [
            f"Trích xuất đồ thị tri thức (Knowledge Graph) cho tài xế {driver_name or driver_id[:8]} ({driver_code or 'ID: ' + driver_id[:8]}):",
            f"- Tổng số nút: {len(subgraph.nodes)} nút ({', '.join(label_summary_parts)}).",
            f"- Tổng số cạnh quan hệ: {len(subgraph.edges)} cạnh ({', '.join(rel_summary_parts) if rel_summary_parts else 'không có'}).",
            f"- Đội xe / Hub: {fleet_name or 'Chưa phân bổ'}.",
        ]
        if vehicles:
            v_props = vehicles[0].props
            summary_lines.append(f"- Phương tiện: {v_props.get('model')} (Biển số: {v_props.get('plate_number')}, Pin: {v_props.get('battery_health')}%).")
        if shifts:
            summary_lines.append(f"- Ca làm việc: {len(shifts)} ca ghi nhận trong đồ thị.")
        summary_lines.append(f"- Chuyến đi trong đồ thị: {len(trips)} chuyến ({completed_cnt} hoàn thành, {cancelled_cnt} bị hủy).")
        if incidents:
            summary_lines.append(f"- Biên bản sự cố/vi phạm: {len(inc_list)} biên bản.")
        if complaints:
            summary_lines.append(f"- Phản ánh/khiếu nại từ khách hàng: {len(complaints)} khiếu nại.")
        if maints:
            summary_lines.append(f"- Sự kiện bảo dưỡng xe: {len(maints)} đợt bảo dưỡng.")
        if rules:
            summary_lines.append(f"- Quy chế đối soát liên quan: {', '.join(r.name for r in rules)}.")
        if decisions:
            summary_lines.append(f"- Quyết định khen thưởng/kỷ luật: {', '.join(d.props.get('action_type', d.name) for d in decisions)}.")

        summary_text = "\n".join(summary_lines)

        return {
            "tool": "query_driver_graph",
            "driver_id": driver_id,
            "driver_code": driver_code,
            "driver_name": driver_name,
            "node_count": len(subgraph.nodes),
            "edge_count": len(subgraph.edges),
            "node_breakdown": node_counts_by_label,
            "edge_breakdown": edge_types,
            "fleet": fleet_name,
            "trips_in_kg": len(trips),
            "trips_completed": completed_cnt,
            "trips_cancelled": cancelled_cnt,
            "incidents": inc_list,
            "nodes_sample": sample_nodes,
            "edges_sample": sample_edges,
            "summary": summary_text,
        }
    except Exception as e:
        return {"tool": "query_driver_graph", "error": str(e)}


def search_gsm_policies(pipeline: Any, query: str, policy_code: str | None = None, top_k: int = 5) -> dict[str, Any]:
    """Tra cứu các điều khoản quy chế GSM qua BM25 và Qdrant hybrid retrieval."""
    if not pipeline:
        return {"tool": "search_gsm_policies", "error": "Policy search index unavailable."}

    try:
        search_query = f"{policy_code} {query}".strip() if policy_code else query
        items = []

        if getattr(pipeline, "hybrid_searcher", None):
            policy_scope_arg = [policy_code] if policy_code else None
            evidence_list, _ = pipeline.hybrid_searcher.search_and_rerank(
                search_query,
                final_top_k=top_k,
                policy_scope=policy_scope_arg,
            )
            for ev in evidence_list:
                items.append({
                    "chunk_id": ev.get("evidence_id", ""),
                    "policy_alias": ev.get("policy_alias", ""),
                    "title": ev.get("policy_title", ""),
                    "snippet": (ev.get("chunk_text") or ev.get("content") or "").strip(),
                })
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
                items.append({
                    "chunk_id": cid,
                    "policy_alias": alias,
                    "title": title,
                    "snippet": text.strip(),
                })

        return {
            "tool": "search_gsm_policies",
            "query": query,
            "policy_code": policy_code,
            "results_count": len(items),
            "policies": items,
            "summary": f"Tìm thấy {len(items)} điều khoản quy chế liên quan đến '{query}'.",
        }
    except Exception as e:
        return {"tool": "search_gsm_policies", "error": str(e)}


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
        "description": "Kiểm tra doanh số ngày so với định mức (threshold_vnd) được tra cứu từ văn bản quy chế tương ứng. Nếu không truyền threshold_vnd, trả về thông tin doanh số thực tế chuẩn hóa.",
        "parameters": {
            "type": "object",
            "properties": {
                "revenue_vnd": {"type": "integer", "description": "Tổng doanh số tài xế đạt được trong ngày (VNĐ)"},
                "threshold_vnd": {"type": "integer", "description": "Định mức doanh số yêu cầu theo quy chế (VNĐ, ví dụ: 720000 hoặc 900000)"},
                "date": {"type": "string", "description": "Ngày kiểm tra (định dạng YYYY-MM-DD)"},
            },
            "required": ["revenue_vnd"],
        },
    },
    {
        "name": "calculate_cancel_rate",
        "description": "Tính tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d = cancelled / total_trips) theo định nghĩa M01.",
        "parameters": {
            "type": "object",
            "properties": {
                "cancelled_trips": {"type": "integer", "description": "Số cuốc bị hủy"},
                "total_trips": {"type": "integer", "description": "Tổng số cuốc phát sinh"},
            },
            "required": ["cancelled_trips", "total_trips"],
        },
    },
    {
        "name": "evaluate_rating_condition",
        "description": "Đối chiếu điểm đánh giá sao của tài xế với ngưỡng quy chế (threshold) sau khi tra cứu quy định từ search_gsm_policies. Nếu không truyền threshold, trả về số liệu đánh giá chuẩn hóa.",
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
        "description": "Tính mức giảm trừ bù trừ doanh thu theo công thức max(280_000 - revenue_vnd, 0) // 5.",
        "parameters": {
            "type": "object",
            "properties": {
                "revenue_vnd": {"type": "integer", "description": "Doanh thu của tài xế (VNĐ)"},
            },
            "required": ["revenue_vnd"],
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
        "name": "get_driver_trip_metrics",
        "description": "Tra cứu tổng hợp số liệu chuyến đi (tổng số chuyến, số chuyến hoàn thành, số chuyến bị hủy, tỷ lệ hủy cancel_rate_30d) của tài xế theo ngày/tháng/năm cụ thể hoặc theo snapshot/toàn kỳ.",
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
        "name": "get_driver_daily_stats",
        "description": "Lấy số liệu thực tế các cuốc xe (phát, nhận, hoàn thành, hủy) và tổng doanh thu của tài xế trong một ngày cụ thể từ CSDL để phục vụ tính toán các chỉ số vận hành và đối chiếu quy chế.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_id": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "date": {"type": "string", "description": "Ngày cần tra cứu (định dạng YYYY-MM-DD)"},
            },
            "required": ["driver_id", "date"],
        },
    },
    {
        "name": "query_driver_graph",
        "description": "Truy vấn đồ thị tri thức (Knowledge Graph) mở rộng: tìm kiếm và trích xuất các nút thực thể (Driver, Trip, Fleet, Incident, Measurement) và các cạnh liên kết quan hệ trong đồ thị cho tài xế theo mốc snapshot.",
        "parameters": {
            "type": "object",
            "properties": {
                "driver_identifier": {"type": "string", "description": "Mã tài xế (DRV-xxx), tên tài xế hoặc UUID"},
                "snapshot_id": {"type": "string", "description": "Mã snapshot thời gian cần tra cứu đồ thị nếu có"},
            },
            "required": ["driver_identifier"],
        },
    },
    {
        "name": "search_gsm_policies",
        "description": "Tìm kiếm điều khoản và nội dung quy chế trong kho 224 văn bản chính sách GSM.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa hoặc câu hỏi cần tra cứu quy chế"},
                "policy_code": {"type": "string", "description": "Mã quy chế nếu có (ví dụ: P154, P151, P05, P23)"},
            },
            "required": ["query"],
        },
    },
]
