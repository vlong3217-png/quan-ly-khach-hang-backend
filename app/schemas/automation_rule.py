"""Pydantic Schemas for Automation Workflow Rules (S7-09 EP-09)."""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class TriggerEventEnum(str, Enum):
    OPPORTUNITY_STAGE_CHANGED = "OPPORTUNITY_STAGE_CHANGED"
    LEAD_STATUS_CHANGED = "LEAD_STATUS_CHANGED"
    QUOTE_STATUS_CHANGED = "QUOTE_STATUS_CHANGED"
    TASK_COMPLETED = "TASK_COMPLETED"


class ActionTypeEnum(str, Enum):
    CREATE_TASK = "CREATE_TASK"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    CHANGE_OWNER = "CHANGE_OWNER"


class AutomationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Tên quy tắc tự động hóa")
    description: Optional[str] = Field(default=None, description="Mô tả quy tắc")
    is_active: bool = Field(default=True, description="Trạng thái bật/tắt của quy tắc")
    trigger_event: str = Field(..., description="Sự kiện kích hoạt (OPPORTUNITY_STAGE_CHANGED, LEAD_STATUS_CHANGED, QUOTE_STATUS_CHANGED)")
    conditions: Optional[Dict[str, Any]] = Field(default=None, description="Điều kiện lọc (ví dụ to_stage, min_value, team_id)")
    actions: List[Dict[str, Any]] = Field(..., min_length=1, description="Danh sách các hành động thực thi (CREATE_TASK, SEND_NOTIFICATION, CHANGE_OWNER)")

    model_config = ConfigDict(extra="allow")


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    trigger_event: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(extra="allow")


class AutomationRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    trigger_event: str
    conditions: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]]
    created_by: Optional[int] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class AutomationRuleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    rules: List[AutomationRuleResponse]

    model_config = ConfigDict(extra="allow")


class AutomationRuleToggleResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    message: str

    model_config = ConfigDict(extra="allow")


class AutomationExecutionLogResponse(BaseModel):
    id: int
    rule_id: int
    rule_name: str
    trigger_event: str
    entity_type: str
    entity_id: int
    entity_name: Optional[str] = None
    status: str
    actions_executed: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
    executed_at: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class AutomationExecutionLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    logs: List[AutomationExecutionLogResponse]

    model_config = ConfigDict(extra="allow")


class AutomationTestRunRequest(BaseModel):
    entity_id: int = Field(..., description="ID của thực thể muốn thử nghiệm (Opportunity ID, Lead ID, Quote ID)")
    to_stage: Optional[str] = Field(default=None, description="Giai đoạn giả lập (nếu có)")
    to_status: Optional[str] = Field(default=None, description="Trạng thái giả lập (nếu có)")


class AutomationTestRunResponse(BaseModel):
    rule_id: int
    rule_name: str
    matched: bool
    actions_count: int
    details: List[Dict[str, Any]]
