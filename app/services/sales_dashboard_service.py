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
    rep_quota_target = 0.0
    rep_quota_achieved = 0.0

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

    # 2. Manager Data
    member_rankings: List[Dict[str, Any]] = []

    stagnant_opps = [
        o for o in open_opps if o.get("stage") in ["PROPOSAL", "NEGOTIATION", "QUALIFICATION"]
    ]

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

    # 3. Director / Admin Data
    pipeline_by_stage = [
        {"stage": s, "count": 0, "value": 0.0}
        for s in STAGE_WEIGHTS.keys()
    ]

    total_forecast = sum(
        item["value"] * STAGE_WEIGHTS.get(item["stage"], 0.0)
        for item in pipeline_by_stage
        if item["stage"] not in ["CLOSED_LOST"]
    )

    total_quota_target = 0.0
    overall_attainment = 0.0

    closed_won_by_month: List[Dict[str, Any]] = []

    director_data = {
        **manager_data,
        "total_forecast_weighted": total_forecast,
        "total_quota_target": total_quota_target,
        "overall_attainment_rate": overall_attainment,
        "pipeline_by_stage": pipeline_by_stage,
        "closed_won_by_month": closed_won_by_month,
        "total_closed_won_ytd": 0.0,
    }

    elapsed = time.perf_counter() - start_time
    return {
        "role": role,
        "user_id": user_id,
        "data": director_data,
        "load_time_seconds": round(elapsed, 4),
    }
