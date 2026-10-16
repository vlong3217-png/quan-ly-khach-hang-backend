from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class LeaderboardRankItem(BaseModel):
    rank: int
    user_id: int
    user_name: str
    team_id: str
    closed_won_amount: float
    personal_quota_target: float
    progress_rate: float
    is_current_user: bool = False

class TeamLeaderboardResponse(BaseModel):
    is_feature_enabled: bool
    team_id: Optional[str] = None
    period_name: str
    rankings: List[LeaderboardRankItem]

class LeaderboardConfigUpdateRequest(BaseModel):
    is_feature_enabled: bool