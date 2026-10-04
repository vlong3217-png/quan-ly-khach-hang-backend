from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    status: Optional[str] = "ACTIVE"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255, description="H??? v?? t??n ng?????i d??ng")
    password: str = Field(..., min_length=6, max_length=100, description="M???t kh???u ng?????i d??ng (t???i thi???u 6 k?? t???)")
    role: Optional[str] = Field(default="USER", description="Vai tr??: ADMIN, MANAGER, USER")
    username: Optional[str] = Field(default=None, max_length=100, description="T??n ????ng nh???p")
    is_active: Optional[bool] = Field(default=True, description="Tr???ng th??i k??ch ho???t")


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(default=None, description="Email ng?????i d??ng")
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="H??? v?? t??n")
    password: Optional[str] = Field(default=None, min_length=6, max_length=100, description="M???t kh???u m???i (n???u mu???n ?????i)")
    role: Optional[str] = Field(default=None, description="Vai tr?? m???i: ADMIN, MANAGER, USER")
    username: Optional[str] = Field(default=None, max_length=100, description="T??n ????ng nh???p")
    is_active: Optional[bool] = Field(default=None, description="Tr???ng th??i k??ch ho???t")


class UserStatusUpdate(BaseModel):
    status: str = Field(..., description="Tr???ng th??i t??i kho???n: ACTIVE ho???c LOCKED")
    handover_to_user_id: Optional[int] = Field(
        default=None,
        description="ID ng?????i d??ng nh???n b??n giao d??? li???u khi kh??a t??i kho???n"
    )


class DataHandoverRequest(BaseModel):
    target_user_id: int = Field(..., description="ID ng?????i d??ng nh???n b??n giao")


class DataHandoverResponse(BaseModel):
    success: bool = True
    message: str
    source_user_id: int
    target_user_id: int
    transferred_items_count: int
    transferred_items: List[Any] = []


class UserStatusResponse(BaseModel):
    id: int
    email: EmailStr
    username: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    status: str
    message: str
    handover: Optional[DataHandoverResponse] = None


class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="Vai trò mới: ADMIN, MANAGER, USER")


class UserTeamUpdate(BaseModel):
    team_id: Optional[int] = Field(..., description="ID nhóm kinh doanh")


class UserAssignmentUpdate(BaseModel):
    role: Optional[str] = Field(default=None, description="Vai trò mới")
    team_id: Optional[int] = Field(default=None, description="ID nhóm mới")


class RoleInfo(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: str


class TeamInfo(BaseModel):
    user_id: int
    email: str
    full_name: str
    team_id: Optional[int]
    team_name: Optional[str]


class UserDetailResponse(BaseModel):
    id: int
    email: str
    username: Optional[str] = None
    full_name: str
    role: str
    team_id: Optional[int] = None
    is_active: bool


class UserImportRow(BaseModel):
    row_number: int
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = "USER"
    team_id: Optional[int] = None
    is_valid: bool = True
    errors: List[str] = []


class UserImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    rows: List[UserImportRow]


class UserImportResultItem(BaseModel):
    row_number: int
    email: Optional[str] = None
    full_name: Optional[str] = None
    status: str  # "SUCCESS" or "SKIPPED"
    error_message: Optional[str] = None


class UserImportSummaryResponse(BaseModel):
    total_rows: int
    imported_count: int
    skipped_count: int
    details: List[UserImportResultItem]


