from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.schemas.notification_preference import (
    NotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)
from app.services import notification_preference_service as service

router = APIRouter(prefix="/users/me/notification-preferences", tags=["Notification Preferences"])


@router.get("", response_model=NotificationPreferencesResponse)
def get_my_notification_preferences(current_user=Depends(get_current_user)):
    user_id = getattr(current_user, "id", 1) if not isinstance(current_user, dict) else current_user.get("id", 1)
    return service.get_user_preferences(user_id)


@router.put("", response_model=NotificationPreferencesResponse)
def update_my_notification_preferences(
    payload: UpdateNotificationPreferencesRequest,
    current_user=Depends(get_current_user),
):
    user_id = getattr(current_user, "id", 1) if not isinstance(current_user, dict) else current_user.get("id", 1)
    return service.update_user_preferences(
        user_id,
        [data.model_dump() for data in payload.preferences],
    )
