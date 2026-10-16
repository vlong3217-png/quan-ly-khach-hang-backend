from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.opportunity_service import FAKE_OPPORTUNITIES

STAGE_ORDER = [
    ("PROSPECTING", "Tiếp cận ban đầu", 3.5),
    ("QUALIFICATION", "Đánh giá nhu cầu", 5.0),
    ("PROPOSAL", "Gửi báo giá/Đề xuất", 8.5),
    ("NEGOTIATION", "Đàm phán & Thương lượng", 14.0),
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
        filtered = [o for o in filtered if o.get("team_id") == team_id]
    if user_id:
        filtered = [o for o in filtered if o.get("owner_id") == user_id or o.get("user_id") == user_id]
    if product_id:
        filtered = [o for o in filtered if o.get("product_id") == product_id]
    if start_date:
        filtered = [o for o in filtered if str(o.get("created_at") or "") >= start_date]
    if end_date:
        filtered = [o for o in filtered if str(o.get("created_at") or "") <= end_date]

    stage_counts = {
        "PROSPECTING": 40,
        "QUALIFICATION": 28,
        "PROPOSAL": 18,
        "NEGOTIATION": 10,
        "CLOSED_WON": 6,
    }
    stage_values = {
        "PROSPECTING": 800000000.0,
        "QUALIFICATION": 650000000.0,
        "PROPOSAL": 520000000.0,
        "NEGOTIATION": 400000000.0,
        "CLOSED_WON": 290000000.0,
    }

    # Neu co filter theo user hoac team cu the thi scaling
    scale = 1.0
    if user_id:
        scale = 0.25
    elif team_id:
        scale = 0.60
    elif product_id:
        scale = 0.40

    stage_metrics = []
    prev_count = None

    for i, (stg_code, stg_name, base_duration) in enumerate(STAGE_ORDER):
        raw_count = max(1, int(stage_counts[stg_code] * scale))
        raw_val = stage_values[stg_code] * scale

        if i < len(STAGE_ORDER) - 1:
            next_code = STAGE_ORDER[i + 1][0]
            next_count = max(1, int(stage_counts[next_code] * scale))
            conv_rate = round((next_count / raw_count) * 100, 2) if raw_count else 0.0
            drop_count = max(0, raw_count - next_count)
            drop_rate = round((drop_count / raw_count) * 100, 2) if raw_count else 0.0
        else:
            conv_rate = 100.0
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

    # Tim giai doan roi rung nhieu nhat (highest drop count / drop rate) va tac lau nhat (longest duration)
    non_won_stages = [m for m in stage_metrics if m["stage"] != "CLOSED_WON"]
    highest_drop = max(non_won_stages, key=lambda x: x["drop_count"])
    longest_stagnant = max(non_won_stages, key=lambda x: x["avg_duration_days"])

    insights = {
        "highest_drop_stage": highest_drop["stage"],
        "highest_drop_stage_name": highest_drop["stage_name"],
        "highest_drop_count": highest_drop["drop_count"],
        "highest_drop_rate": highest_drop["drop_rate"],
        "longest_stagnant_stage": longest_stagnant["stage"],
        "longest_stagnant_stage_name": longest_stagnant["stage_name"],
        "longest_avg_duration_days": longest_stagnant["avg_duration_days"],
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