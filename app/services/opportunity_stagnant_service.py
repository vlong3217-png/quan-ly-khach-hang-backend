"""
S5-07: Cảnh báo cơ hội đình trệ.

- Cơ hội không có hoạt động nào trong N ngày (N cấu hình theo từng giai đoạn
  pipeline qua `stagnant_days`, mặc định theo DEFAULT_STAGNANT_DAYS) -> gắn cờ STAGNANT.
- Cơ hội quá ngày dự kiến chốt (expected_close_date < today) mà vẫn OPEN -> gắn cờ OVERDUE.
- Service quét (scan) cập nhật cờ cho các cơ hội, có thể chạy hàng ngày.
"""

from datetime import date, datetime
from typing import Any, Optional

from app.core.dependencies import DataScope
from app.services import activity_service, opportunity_service, pipeline_service

# Số ngày mặc định không hoạt động theo giai đoạn (dùng khi stage chưa cấu hình stagnant_days)
DEFAULT_STAGNANT_DAYS_BY_STAGE: dict[str, int] = {
    "PROSPECTING": 14,
    "QUALIFICATION": 10,
    "PROPOSAL": 7,
    "NEGOTIATION": 5,
}
DEFAULT_STAGNANT_DAYS = 14

REASON_STAGNANT = "STAGNANT"
REASON_OVERDUE = "OVERDUE"


def _to_datetime(value: Any) -> Optional[datetime]:
    """Chuẩn hóa date / datetime / chuỗi ISO về datetime (naive). Trả None nếu không hợp lệ."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _to_date(value: Any) -> Optional[date]:
    dt = _to_datetime(value)
    return dt.date() if dt else None


def is_opportunity_open(opp: dict) -> bool:
    """Cơ hội còn OPEN: status chưa đóng và giai đoạn không phải Won/Lost."""
    status_value = (opp.get("status") or "OPEN").upper()
    if status_value != "OPEN":
        return False
    stage = pipeline_service.find_stage(opp.get("stage"))
    if stage and (stage.get("is_won_stage") or stage.get("is_lost_stage")):
        return False
    return True


def get_stagnant_threshold_days(stage_code: Optional[str]) -> int:
    """N ngày theo giai đoạn: ưu tiên cấu hình của stage, sau đó mặc định theo mã giai đoạn."""
    stage = pipeline_service.find_stage(stage_code)
    if stage and stage.get("stagnant_days"):
        return int(stage["stagnant_days"])
    code = (stage["code"] if stage else str(stage_code or "")).upper()
    return DEFAULT_STAGNANT_DAYS_BY_STAGE.get(code, DEFAULT_STAGNANT_DAYS)


def get_last_activity_at(opp: dict) -> Optional[datetime]:
    """Thời điểm hoạt động gần nhất của cơ hội (activity liên kết, last_activity_at, hoặc created_at)."""
    candidates = [
        _to_datetime(a.get("created_at"))
        for a in activity_service.FAKE_ACTIVITIES
        if a.get("opportunity_id") == opp["id"]
    ]
    candidates.append(_to_datetime(opp.get("last_activity_at")))
    candidates = [c for c in candidates if c is not None]
    if candidates:
        return max(candidates)
    return _to_datetime(opp.get("created_at"))


def evaluate_opportunity(opp: dict, today: Optional[date] = None) -> dict:
    """Đánh giá một cơ hội, trả về kết quả cờ cảnh báo (không thay đổi dữ liệu)."""
    today = today or date.today()
    result = {
        "is_stagnant": False,
        "is_overdue": False,
        "is_flagged": False,
        "flag_reasons": [],
        "days_inactive": None,
        "stagnant_threshold_days": None,
        "days_overdue": None,
    }
    if not is_opportunity_open(opp):
        return result

    threshold = get_stagnant_threshold_days(opp.get("stage"))
    result["stagnant_threshold_days"] = threshold

    last_activity = get_last_activity_at(opp)
    if last_activity is not None:
        days_inactive = (today - last_activity.date()).days
        result["days_inactive"] = max(days_inactive, 0)
        if days_inactive >= threshold:
            result["is_stagnant"] = True
            result["flag_reasons"].append(REASON_STAGNANT)

    expected_close = _to_date(opp.get("expected_close_date"))
    if expected_close is not None and expected_close < today:
        result["is_overdue"] = True
        result["days_overdue"] = (today - expected_close).days
        result["flag_reasons"].append(REASON_OVERDUE)

    result["is_flagged"] = bool(result["flag_reasons"])
    return result


def _apply_flags(opp: dict, evaluation: dict, now: datetime) -> None:
    was_flagged = bool(opp.get("is_flagged"))
    opp.update(evaluation)
    if evaluation["is_flagged"]:
        if not was_flagged or not opp.get("flagged_at"):
            opp["flagged_at"] = now.isoformat()
    else:
        opp["flagged_at"] = None
    opp["flags_evaluated_at"] = now.isoformat()


def scan_opportunities(
    current_user: Optional[dict] = None,
    scope: DataScope = DataScope.ALL,
    today: Optional[date] = None,
) -> dict:
    """
    Quét và cập nhật cờ cảnh báo cho các cơ hội trong phạm vi (scope) của người dùng.
    Nếu current_user là None (daily job hệ thống) thì quét toàn bộ.
    """
    today = today or date.today()
    now = datetime.utcnow()

    if current_user is None:
        target_ids = {o["id"] for o in opportunity_service.FAKE_OPPORTUNITIES}
    else:
        scoped = opportunity_service.get_opportunities_by_scope(current_user, scope)
        target_ids = {o["id"] for o in scoped}

    scanned = flagged = stagnant = overdue = 0
    for opp in opportunity_service.FAKE_OPPORTUNITIES:
        if opp["id"] not in target_ids:
            continue
        evaluation = evaluate_opportunity(opp, today)
        _apply_flags(opp, evaluation, now)
        scanned += 1
        flagged += 1 if evaluation["is_flagged"] else 0
        stagnant += 1 if evaluation["is_stagnant"] else 0
        overdue += 1 if evaluation["is_overdue"] else 0

    return {
        "scanned": scanned,
        "flagged": flagged,
        "stagnant": stagnant,
        "overdue": overdue,
        "scan_date": today.isoformat(),
    }


def run_daily_scan(today: Optional[date] = None) -> dict:
    """Entry point cho daily job (cron/scheduler): quét toàn bộ cơ hội."""
    return scan_opportunities(current_user=None, today=today)


def get_flagged_opportunities(
    current_user: dict,
    scope: DataScope,
    reason: Optional[str] = None,
    refresh: bool = False,
    today: Optional[date] = None,
) -> list[dict]:
    """Danh sách cơ hội đang bị gắn cờ trong phạm vi của người dùng."""
    if refresh:
        scan_opportunities(current_user, scope, today)

    results = [
        o for o in opportunity_service.get_opportunities_by_scope(current_user, scope)
        if o.get("is_flagged")
    ]
    if reason:
        results = [o for o in results if reason in (o.get("flag_reasons") or [])]
    results.sort(key=lambda o: (-(o.get("days_inactive") or 0), o["id"]))
    return results
