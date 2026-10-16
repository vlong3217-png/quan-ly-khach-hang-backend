import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from app.core.database import SessionLocal
from app.models.opportunity import Opportunity
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.sales_quota import SalesQuota
from app.services.opportunity_service import FAKE_OPPORTUNITIES
from app.services.activity_service import FAKE_ACTIVITIES
from app.services import lead_service
from app.services.sales_quota_service import FAKE_SALES_QUOTAS

STAGE_WEIGHTS = {
    "PROSPECTING": 0.10,
    "QUALIFICATION": 0.25,
    "PROPOSAL": 0.50,
    "NEGOTIATION": 0.75,
    "CLOSED_WON": 1.0,
    "CLOSED_LOST": 0.0,
}

def get_role_based_dashboard(current_user: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.perf_counter()
    role = current_user.get("role", "USER").upper()
    user_id = current_user.get("id", 1)
    team_id = current_user.get("team_id", "TEAM_NORTH")

    # 1. Base Rep Data
    # Quota
    rep_quota_target = 100000000.0
    rep_quota_achieved = 35000000.0

    # Opportunities
    open_opps = [
        o for o in FAKE_OPPORTUNITIES 
        if o.get("stage") not in ["CLOSED_WON", "CLOSED_LOST"] 
        and (role in ["DIRECTOR", "ADMIN", "MANAGER"] or o.get("owner_id") == user_id)
    ]
    open_opps_count = len(open_opps)
    open_opps_value = sum(float(o.get("value") or 0.0) for o in open_opps)

    # Today Tasks
    today_str = date.today().isoformat()
    today_tasks = [
        a for a in FAKE_ACTIVITIES 
        if today_str in str(a.get("scheduled_start") or a.get("created_at") or "")
        and (role in ["DIRECTOR", "ADMIN", "MANAGER"] or a.get("owner_id") == user_id)
    ]

    # Leads uncontacted (status = NEW or contact_count = 0)
    all_leads = lead_service.FAKE_LEADS if hasattr(lead_service, "FAKE_LEADS") else []
    uncontacted_leads = [
        l for l in all_leads 
        if l.get("status") in ["NEW", "UNCONTACTED"]
        and (role in ["DIRECTOR", "ADMIN", "MANAGER"] or l.get("owner_id") == user_id or l.get("assigned_to_id") == user_id)
    ]

    rep_data = {
        "user_id": user_id,
        "quota_target": rep_quota_target,
        "quota_achieved": rep_quota_achieved,
        "attainment_rate": round((rep_quota_achieved / rep_quota_target) * 100, 2) if rep_quota_target else 0.0,
        "open_opportunities_count": open_opps_count,
        "open_opportunities_value": open_opps_value,
        "today_tasks_count": len(today_tasks),
        "today_tasks": today_tasks[:10],
        "uncontacted_leads_count": len(uncontacted_leads),
        "uncontacted_leads": uncontacted_leads[:10],
    }

    if role in ["USER", "SALES", "EMPLOYEE"]:
        elapsed = time.perf_counter() - start_time
        return {
            "role": role,
            "user_id": user_id,
            "data": rep_data,
            "load_time_seconds": round(elapsed, 4),
        }

    # 2. Manager Data (Xếp hạng thành viên, cơ hội đình trệ của nhóm, việc quá hạn của nhóm)
    member_rankings = [
        {"user_id": 1, "user_name": "Nguyễn Văn Admin", "closed_won_value": 150000000.0, "attainment_rate": 150.0, "rank": 1},
        {"user_id": 2, "user_name": "Trần Thị Manager", "closed_won_value": 90000000.0, "attainment_rate": 90.0, "rank": 2},
        {"user_id": 3, "user_name": "Lê Văn Sales", "closed_won_value": 60000000.0, "attainment_rate": 60.0, "rank": 3},
    ]

    # Stagnant opportunities: trong open_opps
    stagnant_opps = [
        o for o in open_opps if o.get("stage") in ["PROPOSAL", "NEGOTIATION", "QUALIFICATION"]
    ]

    # Overdue tasks
    overdue_tasks = [
        a for a in FAKE_ACTIVITIES
        if str(a.get("scheduled_start") or "") < today_str and a.get("status") not in ["COMPLETED", "CANCELLED"]
    ]

    manager_data = {
        **rep_data,
        "team_id": team_id,
        "member_rankings": member_rankings,
        "stagnant_opportunities_count": len(stagnant_opps),
        "stagnant_opportunities": stagnant_opps[:10],
        "overdue_tasks_count": len(overdue_tasks),
        "overdue_tasks": overdue_tasks[:10],
    }

    if role in ["MANAGER", "LEADER", "TEAM_LEAD"]:
        elapsed = time.perf_counter() - start_time
        return {
            "role": role,
            "user_id": user_id,
            "data": manager_data,
            "load_time_seconds": round(elapsed, 4),
        }

    # 3. Director / Admin Data (Dự báo so với chỉ tiêu, pipeline theo giai đoạn, doanh số đã chốt theo tháng)
    pipeline_by_stage = [
        {"stage": "PROSPECTING", "count": 12, "value": 240000000.0},
        {"stage": "QUALIFICATION", "count": 8, "value": 320000000.0},
        {"stage": "PROPOSAL", "count": 6, "value": 450000000.0},
        {"stage": "NEGOTIATION", "count": 4, "value": 500000000.0},
        {"stage": "CLOSED_WON", "count": 15, "value": 1200000000.0},
        {"stage": "CLOSED_LOST", "count": 5, "value": 180000000.0},
    ]

    # Weighted forecast
    total_forecast = sum(
        item["value"] * STAGE_WEIGHTS.get(item["stage"], 0.0)
        for item in pipeline_by_stage
        if item["stage"] not in ["CLOSED_LOST"]
    )

    total_quota_target = 2500000000.0
    overall_attainment = round((1200000000.0 / total_quota_target) * 100, 2)

    closed_won_by_month = [
        {"month": "2026-07", "closed_won_value": 180000000.0},
        {"month": "2026-08", "closed_won_value": 240000000.0},
        {"month": "2026-09", "closed_won_value": 380000000.0},
        {"month": "2026-10", "closed_won_value": 400000000.0},
    ]

    director_data = {
        **manager_data,
        "total_forecast_weighted": total_forecast,
        "total_quota_target": total_quota_target,
        "overall_attainment_rate": overall_attainment,
        "pipeline_by_stage": pipeline_by_stage,
        "closed_won_by_month": closed_won_by_month,
        "total_closed_won_ytd": 1200000000.0,
    }

    elapsed = time.perf_counter() - start_time
    return {
        "role": role,
        "user_id": user_id,
        "data": director_data,
        "load_time_seconds": round(elapsed, 4),
    }