from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status

LEADERBOARD_SYSTEM_CONFIG = {
    "is_feature_enabled": True
}

TEAM_MEMBERS_DATA: List[Dict[str, Any]] = []

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
        user_team = str(found_m["team_id"]) if found_m else "1"

    # Chi lay cac thanh vien cung nhom voi user
    team_members = [m for m in TEAM_MEMBERS_DATA if str(m.get("team_id")) == user_team]

    sorted_members = sorted(team_members, key=lambda x: x.get("closed_won_amount", 0.0), reverse=True)

    rankings = []
    for rank_idx, m in enumerate(sorted_members, start=1):
        target = float(m.get("personal_quota_target") or 0.0)
        achieved = float(m.get("closed_won_amount") or 0.0)
        rate = round((achieved / target) * 100, 2) if target > 0 else 0.0

        rankings.append({
            "rank": rank_idx,
            "user_id": m["user_id"],
            "user_name": m.get("user_name", f"User {m['user_id']}"),
            "team_id": str(m.get("team_id", user_team)),
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
