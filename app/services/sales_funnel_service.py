from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.opportunity_service import FAKE_OPPORTUNITIES

STAGE_ORDER = [
    ("PROSPECTING", "Tiếp cận ban đầu", 3.5),
    ("QUALIFICATION", "Đánh giá nhu cầu", 5.0),
    ("PROPOSAL", "Gửi báo giá/Đề xuất", 8.5),
    ("NEGOTIATION", "Đàm phán và Thương lượng", 14.0),
    ("CLOSED_WON", "Thành công (Won)", 0.0),
]

def get_sales_funnel_and_conversion_report(
    team_id: Optional[str] = None,
    user_id: Optional[int] = None,
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    filtered = list(FAKE_OPPORTUNITIES)

    if team_id:
        filtered = [o for o in filtered if str(o.get("team_id")) == str(team_id)]
    if user_id:
        filtered = [o for o in filtered if o.get("owner_id") == user_id or o.get("user_id") == user_id]
    if product_id:
        filtered = [o for o in filtered if o.get("product_id") == product_id]
    if start_date:
        filtered = [o for o in filtered if str(o.get("created_at") or "") >= start_date]
    if end_date:
        filtered = [o for o in filtered if str(o.get("created_at") or "") <= end_date]

    stage_counts = {code: 0 for code, _, _ in STAGE_ORDER}
    stage_values = {code: 0.0 for code, _, _ in STAGE_ORDER}

    for o in filtered:
        stg = str(o.get("stage") or "").upper()
        if stg in stage_counts:
            stage_counts[stg] += 1
            stage_values[stg] += float(o.get("value") or 0.0)

    stage_metrics = []

    for i, (stg_code, stg_name, base_duration) in enumerate(STAGE_ORDER):
        raw_count = stage_counts[stg_code]
        raw_val = stage_values[stg_code]

        if i < len(STAGE_ORDER) - 1:
            next_code = STAGE_ORDER[i + 1][0]
            next_count = stage_counts[next_code]
            conv_rate = round((next_count / raw_count) * 100, 2) if raw_count > 0 else 0.0
            drop_count = max(0, raw_count - next_count) if raw_count > 0 else 0
            drop_rate = round((drop_count / raw_count) * 100, 2) if raw_count > 0 else 0.0
        else:
            conv_rate = 100.0 if raw_count > 0 else 0.0
            drop_count = 0
            drop_rate = 0.0

        stage_metrics.append({
            "stage": stg_code,
            "stage_name": stg_name,
            "count": raw_count,
            "value": raw_val,
            "conversion_rate_to_next": conv_rate,
            "drop_count": drop_count,
            "drop_rate": drop_rate,
            "avg_duration_days": base_duration,
        })

    non_won_stages = [m for m in stage_metrics if m["stage"] != "CLOSED_WON"]
    highest_drop = max(non_won_stages, key=lambda x: x["drop_count"]) if non_won_stages else None
    longest_stagnant = max(non_won_stages, key=lambda x: x["avg_duration_days"]) if non_won_stages else None

    insights = {
        "highest_drop_stage": highest_drop["stage"] if highest_drop else "PROSPECTING",
        "highest_drop_stage_name": highest_drop["stage_name"] if highest_drop else "Tiếp cận ban đầu",
        "highest_drop_count": highest_drop["drop_count"] if highest_drop else 0,
        "highest_drop_rate": highest_drop["drop_rate"] if highest_drop else 0.0,
        "longest_stagnant_stage": longest_stagnant["stage"] if longest_stagnant else "NEGOTIATION",
        "longest_stagnant_stage_name": longest_stagnant["stage_name"] if longest_stagnant else "Đàm phán và Thương lượng",
        "longest_avg_duration_days": longest_stagnant["avg_duration_days"] if longest_stagnant else 14.0,
    }

    total_opps = sum(m["count"] for m in stage_metrics)
    total_val = sum(m["value"] for m in stage_metrics)

    return {
        "total_opportunities": total_opps,
        "total_pipeline_value": total_val,
        "stages": stage_metrics,
        "insights": insights,
        "filters_applied": {
            "team_id": team_id,
            "user_id": user_id,
            "product_id": product_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    }
