"""
Menu and navigation schemas for S1-06 Role-based menu.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MenuItemSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique menu identifier")
    title: str = Field(..., description="Display title of the menu item")
    path: str = Field(..., description="Route URL path")
    roles: Optional[List[str]] = Field(None, description="Allowed roles")
    permissions: Optional[List[str]] = Field(None, description="Required permissions")
    badge: Optional[str] = Field(None, description="Optional badge text")
    badge_variant: Optional[str] = Field(None, alias="badgeVariant", description="Badge style variant")
    description: Optional[str] = Field(None, description="Menu item description")
    is_external: Optional[bool] = Field(False, alias="isExternal", description="Whether path is external")
    children: Optional[List["MenuItemSchema"]] = Field(None, description="Submenu items")



class MenuGroupSchema(BaseModel):
    id: str = Field(..., description="Unique group identifier")
    title: str = Field(..., description="Display title of the menu group")
    description: Optional[str] = Field(None, description="Group description")
    items: List[MenuItemSchema] = Field(default_factory=list, description="Menu items in this group")


class MenuResponse(BaseModel):
    role: str = Field(..., description="Current user's role")
    user_id: int = Field(..., description="Current user's ID")
    full_name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email")
    permissions: List[str] = Field(default_factory=list, description="User permissions list")
    data_scope: str = Field(..., description="Effective data scope")
    total_groups: int = Field(..., description="Total accessible groups")
    total_items: int = Field(..., description="Total accessible top-level items")
    menu_groups: List[MenuGroupSchema] = Field(default_factory=list, description="Accessible menu hierarchy")


class MenuAccessCheckResponse(BaseModel):
    menu_id: str = Field(..., description="Menu item ID checked")
    allowed: bool = Field(..., description="Whether user has permission to access")
    title: Optional[str] = Field(None, description="Menu item title if found")
    required_roles: Optional[List[str]] = Field(None, description="Roles permitted for this menu item")
    required_permissions: Optional[List[str]] = Field(None, description="Permissions required for this menu item")
