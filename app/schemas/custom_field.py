from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TargetEntity(str, Enum):
    CUSTOMER = "CUSTOMER"
    OPPORTUNITY = "OPPORTUNITY"


class CustomFieldType(str, Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    SELECT = "SELECT"


class CustomFieldBase(BaseModel):
    target_entity: TargetEntity = Field(..., description="Đối tượng áp dụng: CUSTOMER hoặc OPPORTUNITY")
    field_key: str = Field(..., min_length=1, max_length=50, description="Mã trường kỹ thuật (ví dụ: tax_code, budget)")
    label: str = Field(..., min_length=1, max_length=100, description="Tên nhãn hiển thị cho người dùng")
    field_type: CustomFieldType = Field(..., description="Kiểu dữ liệu: TEXT, NUMBER, DATE, SELECT")
    options: Optional[List[str]] = Field(default=None, description="Danh sách các lựa chọn nếu field_type là SELECT")
    is_required: bool = Field(default=False, description="Trường này có bắt buộc nhập hay không")
    sort_order: int = Field(default=0, description="Thứ tự hiển thị trên form")


class CustomFieldCreate(CustomFieldBase):
    pass


class CustomFieldUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    sort_order: Optional[int] = None


class CustomFieldResponse(BaseModel):
    id: int
    target_entity: TargetEntity
    field_key: str
    label: str
    field_type: CustomFieldType
    options: Optional[List[str]] = None
    is_required: bool
    sort_order: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CustomFieldValuesValidateRequest(BaseModel):
    target_entity: TargetEntity
    values: Dict[str, Any]


class CustomFieldValuesValidateResponse(BaseModel):
    is_valid: bool
    errors: Dict[str, str] = {}
