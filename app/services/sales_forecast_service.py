"""
S5-06: Dự báo doanh số theo trọng số xác suất (Weighted Sales Forecast).

Công thức: Dự báo = Giá trị cơ hội (value) × Xác suất thắng (%) của giai đoạn.
Gom nhóm theo expected_close_date: tháng này, tháng sau, quý này.
So sánh với chỉ tiêu (monthly_quota của nhân viên) và doanh số đã chốt (Closed Won).
"""

from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException, status

from app.services import auth_service, opportunity_service, pipeline_service

PERIOD_THIS_MONTH = "this_month"
PERIOD_NEXT_MONTH = "next_month"
PERIOD_THIS_QUARTER = "this_quarter"
PERIODS = (PERIOD_THIS_MONTH, PERIOD_NEXT_MONTH, PERIOD_THIS_QUARTER)


def _to_date(value) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def get_period_ranges(reference: Optional[date] = None) -> dict[str, tuple[date, date]]:
    """Trả về khoảng [start, end] (bao gồm 2 đầu) của từng mốc thời gian."""
    ref = reference or date.today()

    def month_range(y: int, m: int) -> tuple[date, date]:
        start = date(y, m, 1)
        ny, nm = _add_months(y, m, 1)
        return start, date.fromordinal(date(ny, nm, 1).toordinal() - 1)

    this_m = month_range(ref.year, ref.month)
    ny, nm = _add_months(ref.year, ref.month, 1)
    next_m = month_range(ny, nm)

    q_start_month = 3 * ((ref.month - 1) // 3) + 1
    q_start = date(ref.year, q_start_month, 1)
    qy, qm = _add_months(ref.year, q_start_month, 2)
    q_end = month_range(qy, qm)[1]

    return {
        PERIOD_THIS_MONTH: this_m,
        PERIOD_NEXT_MONTH: next_m,
        PERIOD_THIS_QUARTER: (q_start, q_end),
    }


def _months_in_range(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def resolve_forecast_filters(
    current_user: dict,
    owner_id: Optional[int],
    team_id: Optional[int],
) -> tuple[Optional[int], Optional[int]]:
    """Kiểm tra phân quyền và trả về (owner_id, team_id) hiệu lực."""
    role = current_user.get("role", "USER")
    my_id = current_user.get("id")
    my_team = current_user.get("team_id")

    if role == "ADMIN":
        return owner_id, team_id

    if role == "MANAGER":
        if team_id is not None and team_id != my_team:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn chỉ được xem dự báo doanh số của nhóm mình quản lý",
            )
        if owner_id is not None and owner_id != my_id:
            target = auth_service.get_user_by_id(owner_id)
            if target is None or my_team is None or target.get("team_id") != my_team:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn chỉ được xem dự báo doanh số của nhân viên thuộc nhóm mình",
                )
        if team_id is None and owner_id is None:
            # Mặc định: toàn bộ nhóm (hoặc chính mình nếu chưa thuộc nhóm nào)
            if my_team is not None:
                return None, my_team
            return my_id, None
        return owner_id, team_id

    # USER: chỉ xem số liệu của chính mình
    if (owner_id is not None and owner_id != my_id) or team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nhân viên chỉ được xem dự báo doanh số của chính mình",
        )
    return my_id, None


def _quota_per_month(owner_id: Optional[int], team_id: Optional[int]) -> float:
    total = 0.0
    for u in auth_service.fake_users_db:
        if not u.get("is_active", True):
            continue
        if owner_id is not None and u.get("id") != owner_id:
            continue
        if team_id is not None and u.get("team_id") != team_id:
            continue
        total += float(u.get("monthly_quota") or 0.0)
    return total


def calculate_weighted_amount(value: float, win_probability: float) -> float:
    return round(float(value or 0.0) * float(win_probability or 0.0) / 100.0, 2)


def _stage_info(stage_identifier) -> dict:
    stage = pipeline_service.find_stage(stage_identifier)
    if stage is None:
        return {"win_probability": 0.0, "is_won_stage": False, "is_lost_stage": False}
    return stage


def build_sales_forecast(
    current_user: dict,
    owner_id: Optional[int] = None,
    team_id: Optional[int] = None,
    reference_date: Optional[date] = None,
) -> dict:
    eff_owner, eff_team = resolve_forecast_filters(current_user, owner_id, team_id)
    ranges = get_period_ranges(reference_date)

    opps = [
        o
        for o in opportunity_service.FAKE_OPPORTUNITIES
        if (eff_owner is None or o.get("owner_id") == eff_owner)
        and (eff_team is None or o.get("team_id") == eff_team)
    ]

    monthly_quota = _quota_per_month(eff_owner, eff_team)

    periods = {}
    for key in PERIODS:
        start, end = ranges[key]
        pipeline_amount = 0.0
        weighted = 0.0
        closed_won = 0.0
        details = []
        for o in opps:
            stage = _stage_info(o.get("stage"))
            if stage.get("is_lost_stage"):
                continue
            if stage.get("is_won_stage"):
                d = _to_date(o.get("closed_date")) or _to_date(o.get("expected_close_date"))
            else:
                d = _to_date(o.get("expected_close_date"))
            if d is None or not (start <= d <= end):
                continue
            value = float(o.get("value") or 0.0)
            if stage.get("is_won_stage"):
                closed_won += value
                continue
            prob = float(stage.get("win_probability") or 0.0)
            w = calculate_weighted_amount(value, prob)
            pipeline_amount += value
            weighted += w
            details.append(
                {
                    "opportunity_id": o["id"],
                    "title": o.get("title"),
                    "owner_id": o.get("owner_id"),
                    "team_id": o.get("team_id"),
                    "stage": o.get("stage"),
                    "amount": value,
                    "win_probability": prob,
                    "weighted_amount": w,
                    "expected_close_date": d.isoformat(),
                }
            )

        quota = round(monthly_quota * _months_in_range(start, end), 2)
        forecast_total = round(closed_won + weighted, 2)
        periods[key] = {
            "period": key,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "opportunity_count": len(details),
            "pipeline_amount": round(pipeline_amount, 2),
            "weighted_forecast": round(weighted, 2),
            "closed_won": round(closed_won, 2),
            "forecast_total": forecast_total,
            "quota": quota,
            "achievement_percent": round(closed_won / quota * 100, 2) if quota > 0 else None,
            "forecast_vs_quota_percent": round(forecast_total / quota * 100, 2) if quota > 0 else None,
            "gap_to_quota": round(quota - forecast_total, 2),
            "opportunities": details,
        }

    return {
        "owner_id": eff_owner,
        "team_id": eff_team,
        "reference_date": (reference_date or date.today()).isoformat(),
        "periods": periods,
    }
