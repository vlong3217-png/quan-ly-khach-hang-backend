from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.schemas.sales_dashboard import RoleBasedDashboardResponse
from app.services import sales_dashboard_service as service

router = APIRouter(prefix="/sales-dashboard", tags=["Sales Dashboard"])

@router.get("", response_model=RoleBasedDashboardResponse)
def get_dashboard(current_user=Depends(get_current_user)):
    user_dict = current_user if isinstance(current_user, dict) else {
        "id": getattr(current_user, "id", 1),
        "role": getattr(current_user, "role", "USER"),
        "team_id": getattr(current_user, "team_id", "TEAM_NORTH"),
    }
    return service.get_role_based_dashboard(user_dict)