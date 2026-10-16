from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status

LEADERBOARD_SYSTEM_CONFIG = {
    "is_feature_enabled": True
}

TEAM_MEMBERS_DATA = [
    {"user_id": 1, "user_name": "Nguyễn Văn Admin", "team_id": "1", "closed_won_amount": 150000000.0, "personal_quota_target": 100000000.0},
    {"user_id": 2, "user_name": "Trần Thị Manager", "team_id": "1", "closed_won_amount": 95000000.0, "personal_quota_target": 90000000.0},
    {"user_id": 3, "user_name": "Lê Văn Sales", "team_id": "1", "closed_won_amount": 75000000.0, "personal_quota_target": 80000000.0},
    {"user_id": 4, "user_name": "Phạm Quốc Nam", "team_id": "2", "closed_won_amount": 120000000.0, "personal_quota_target": 110000000.0},
    {"user_id": 5, "user_name": "Vũ Minh Tuấn", "team_id": "2", "closed_won_amount": 80000000.0, "personal_quota_target": 90000000.0},
]

def reset_leaderboard_config():
    LEADERBOARD_SYSTEM_CONFIG["is_feature_enabled"] = True

def update_leaderboard_config(is_enabled: bool) -> Dict[str, Any]:
    LEADERBOARD_SYSTEM_CONFIG["is_feature_enabled"] = is_enabled
    return {"is_feature_enabled": is_enabled}

def get_team_leaderboard(current_user: Dict[str, Any], period_name: str = "2026-10") -> Dict[str, Any]:
    if not LEADERBOARD_SYSTEM_CONFIG.get("is_feature_enabled", True):
        return {
            "is_feature_enabled": False,
            "team_id": None,
            "period_name": period_name,
            "rankings": [],
        }

    user_id = current_user.get("id", 1)
    raw_team = current_user.get("team_id")
    if raw_team is not None:
        user_team = str(raw_team)
    else:
        found_m = next((m for m in TEAM_MEMBERS_DATA if m["user_id"] == user_id), None)
        user_team = found_m["team_id"] if found_m else "1"

    # Chỉ lấy các thành viên cùng nhóm với user
    team_members = [m for m in TEAM_MEMBERS_DATA if str(m["team_id"]) == user_team]

    # Sắp xếp theo doanh số đã chốt giảm dần
    sorted_members = sorted(team_members, key=lambda x: x["closed_won_amount"], reverse=True)

    rankings = []
    for rank_idx, m in enumerate(sorted_members, start=1):
        target = m["personal_quota_target"]
        achieved = m["closed_won_amount"]
        rate = round((achieved / target) * 100, 2) if target else 0.0

        rankings.append({
            "rank": rank_idx,
            "user_id": m["user_id"],
            "user_name": m["user_name"],
            "team_id": str(m["team_id"]),
            "closed_won_amount": achieved,
            "personal_quota_target": target,
            "progress_rate": rate,
            "is_current_user": (m["user_id"] == user_id),
        })

    return {
        "is_feature_enabled": True,
        "team_id": user_team,
        "period_name": period_name,
        "rankings": rankings,
    }