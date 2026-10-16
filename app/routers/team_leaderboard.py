from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.team_leaderboard import TeamLeaderboardResponse, LeaderboardConfigUpdateRequest
from app.services import team_leaderboard_service as service

router = APIRouter(prefix="/team-leaderboard", tags=["Team Leaderboard"])

@router.get("", response_model=TeamLeaderboardResponse)
def get_leaderboard(
    period_name: str = Query("2026-10"),
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {
        "id": getattr(current_user, "id", 1),
        "team_id": getattr(current_user, "team_id", None),
    }
    return service.get_team_leaderboard(user_dict, period_name=period_name)

@router.put("/config")
def update_config(
    payload: LeaderboardConfigUpdateRequest,
    current_user=Depends(get_current_user),
):
    return service.update_leaderboard_config(payload.is_feature_enabled)