from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    account: Optional[str] = None
    password: str

    def get_identifier(self) -> str:
        return (self.email or self.username or self.account or "").strip()


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
