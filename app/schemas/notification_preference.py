from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class NotificationPreferenceItem(BaseModel):
    notification_type: str
    name: str
    description: Optional[str] = ""
    in_app_enabled: bool = True
    email_enabled: bool = True
    is_mandatory: bool = False
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationPreferencesResponse(BaseModel):
    user_id: int
    preferences: List[NotificationPreferenceItem]


    
    
    

class NotificationPreferenceUpdateItem(BaseModel):
    notification_type: str
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None

class UpdateNotificationPreferencesRequest(BaseModel):
    preferences: List[NotificationPreferenceUpdateItem]
