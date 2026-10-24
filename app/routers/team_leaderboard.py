from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.team_leaderboard import TeamLeaderboardResponse, LeaderboardConfigUpdateRequest
from app.services import team_leaderboard_service as service

router = APIRouter(prefix="/team-leaderboard", tags=["Team Leaderboard"])

@router.get("", response_model=TeamLeaderboardResponse)
def get_leaderboard(
    period_name: str = Query("2026-10"),
    page: Optional[int] = Query(None, ge=1, description="Trang bảng xếp hạng"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    user_dict = current_user if isinstance(current_user, dict) else {
        "id": getattr(current_user, "id", 1),
        "team_id": getattr(current_user, "team_id", None),
    }
    data = service.get_team_leaderboard(user_dict, period_name=period_name)
    rankings = data.get("rankings", [])
    total_rankings = len(rankings)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(total_rankings / effective_limit)) if total_rankings > 0 else 1

    paged_rankings = rankings[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    data["rankings"] = paged_rankings
    data["page"] = effective_page
    data["limit"] = effective_limit
    data["total_pages"] = total_pages
    data["total_rankings"] = total_rankings
    return data

@router.put("/config")
def update_config(
    payload: LeaderboardConfigUpdateRequest,
    current_user=Depends(get_current_user),
):
    return service.update_leaderboard_config(payload.is_feature_enabled)