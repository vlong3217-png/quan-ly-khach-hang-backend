"""
S1-06: Menu & Permission Service.

Defines the master menu navigation hierarchy and role-based filtering logic:
- ADMIN: Full access to all menus (core, management, admin system settings).
- MANAGER: Access to core and management menus (including customer export, reports, teams).
- USER: Access only to core menu (dashboard, customer list/create). Restricted from export, reports, teams, admin settings.
"""

from copy import deepcopy
from typing import Dict, List, Optional, Tuple

# Role Constants
ROLE_ADMIN = "ADMIN"
ROLE_MANAGER = "MANAGER"
ROLE_USER = "USER"

# Permission Constants
PERMISSION_CUSTOMER_VIEW = "CUSTOMER_VIEW"
PERMISSION_CUSTOMER_CREATE = "CUSTOMER_CREATE"
PERMISSION_CUSTOMER_EDIT = "CUSTOMER_EDIT"
PERMISSION_CUSTOMER_DELETE = "CUSTOMER_DELETE"
PERMISSION_CUSTOMER_EXPORT = "CUSTOMER_EXPORT"
PERMISSION_REPORT_VIEW = "REPORT_VIEW"
PERMISSION_SYSTEM_SETTINGS = "SYSTEM_SETTINGS"

# Role -> Permissions Mapping
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    ROLE_ADMIN: [
        PERMISSION_CUSTOMER_VIEW,
        PERMISSION_CUSTOMER_CREATE,
        PERMISSION_CUSTOMER_EDIT,
        PERMISSION_CUSTOMER_DELETE,
        PERMISSION_CUSTOMER_EXPORT,
        PERMISSION_REPORT_VIEW,
        PERMISSION_SYSTEM_SETTINGS,
    ],
    ROLE_MANAGER: [
        PERMISSION_CUSTOMER_VIEW,
        PERMISSION_CUSTOMER_CREATE,
        PERMISSION_CUSTOMER_EDIT,
        PERMISSION_CUSTOMER_EXPORT,
        PERMISSION_REPORT_VIEW,
    ],
    ROLE_USER: [
        PERMISSION_CUSTOMER_VIEW,
        PERMISSION_CUSTOMER_CREATE,
        PERMISSION_CUSTOMER_EDIT,
    ],
}

# Master Menu Hierarchy definition
MASTER_MENU_GROUPS: List[dict] = [
    {
        "id": "group-core",
        "title": "T???NG QUAN & L??M VI???C",
        "description": "B???ng ??i???u khi???n v?? danh m???c kh??ch h??ng tr???ng t??m",
        "items": [
            {
                "id": "menu-dashboard",
                "title": "B???ng ??i???u khi???n",
                "path": "/dashboard",
                "roles": [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER],
                "description": "T???ng quan ch??? s??? ho???t ?????ng, ch??o m???ng v?? th??ng tin t??i kho???n",
            },
            {
                "id": "menu-customers",
                "title": "Qu???n l?? kh??ch h??ng",
                "path": "/dashboard/customers",
                "roles": [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER],
                "permissions": [PERMISSION_CUSTOMER_VIEW],
                "description": "Tra c???u, l???c d??? li???u v?? qu???n l?? h??? s?? kh??ch h??ng",
                "children": [
                    {
                        "id": "menu-customers-list",
                        "title": "Danh s??ch kh??ch h??ng",
                        "path": "/dashboard/customers",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER],
                        "permissions": [PERMISSION_CUSTOMER_VIEW],
                        "description": "Xem danh s??ch kh??ch h??ng theo ph???m vi d??? li???u ???????c c???p",
                    },
                    {
                        "id": "menu-customers-create",
                        "title": "Th??m m???i kh??ch h??ng",
                        "path": "/dashboard/customers?action=create",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER],
                        "permissions": [PERMISSION_CUSTOMER_CREATE],
                        "badge": "M???i",
                        "badge_variant": "primary",
                        "description": "T???o h??? s?? th??ng tin kh??ch h??ng m???i",
                    },
                    {
                        "id": "menu-customers-export",
                        "title": "Xu???t d??? li???u Excel/CSV",
                        "path": "/dashboard/customers?action=export",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER],
                        "permissions": [PERMISSION_CUSTOMER_EXPORT],
                        "badge": "Qu???n l??",
                        "badge_variant": "info",
                        "description": "Xu???t b??o c??o danh s??ch kh??ch h??ng ra ?????nh d???ng file",
                    },
                ],
            },
        ],
    },
    {
        "id": "group-management",
        "title": "NGHI???P V??? & QU???N L??",
        "description": "B??o c??o th???ng k?? s??? li???u v?? qu???n l?? t??? ch???c",
        "items": [
            {
                "id": "menu-reports",
                "title": "B??o c??o & Th???ng k??",
                "path": "/dashboard/reports",
                "roles": [ROLE_ADMIN, ROLE_MANAGER],
                "permissions": [PERMISSION_REPORT_VIEW],
                "badge": "Qu???n l??",
                "badge_variant": "warning",
                "description": "Xem b??o c??o doanh s???, chuy???n ?????i v?? th???ng k?? d??? li???u",
                "children": [
                    {
                        "id": "menu-reports-sales",
                        "title": "B??o c??o doanh s???",
                        "path": "/dashboard/reports/sales",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER],
                        "permissions": [PERMISSION_REPORT_VIEW],
                    },
                    {
                        "id": "menu-reports-performance",
                        "title": "Hi???u su???t ?????i ng??",
                        "path": "/dashboard/reports/performance",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER],
                        "permissions": [PERMISSION_REPORT_VIEW],
                    },
                ],
            },
            {
                "id": "menu-teams",
                "title": "Qu???n l?? ?????i nh??m",
                "path": "/dashboard/teams",
                "roles": [ROLE_ADMIN, ROLE_MANAGER],
                "badge": "N???i b???",
                "badge_variant": "info",
                "description": "Qu???n l?? th??nh vi??n ph??ng ban v?? ph??n chia ph??? tr??ch",
                "children": [
                    {
                        "id": "menu-teams-members",
                        "title": "Th??nh vi??n ?????i nh??m",
                        "path": "/dashboard/teams/members",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER],
                    },
                    {
                        "id": "menu-teams-assignments",
                        "title": "Ph??n b??? kh??ch h??ng",
                        "path": "/dashboard/teams/assignments",
                        "roles": [ROLE_ADMIN, ROLE_MANAGER],
                    },
                ],
            },
        ],
    },
    {
        "id": "group-admin",
        "title": "H??? TH???NG & C???U H??NH",
        "description": "Ch??? d??nh cho Qu???n tr??? vi??n (ADMIN)",
        "items": [
            {
                "id": "menu-settings",
                "title": "C???u h??nh h??? th???ng",
                "path": "/dashboard/settings",
                "roles": [ROLE_ADMIN],
                "permissions": [PERMISSION_SYSTEM_SETTINGS],
                "badge": "Admin",
                "badge_variant": "danger",
                "description": "C???u h??nh tham s???, ph??n quy???n vai tr?? v?? nh???t k?? h??? th???ng",
                "children": [
                    {
                        "id": "menu-settings-general",
                        "title": "Thi???t l???p chung",
                        "path": "/dashboard/settings/general",
                        "roles": [ROLE_ADMIN],
                        "permissions": [PERMISSION_SYSTEM_SETTINGS],
                    },
                    {
                        "id": "menu-settings-roles",
                        "title": "Ph??n quy???n & Vai tr??",
                        "path": "/dashboard/settings/roles",
                        "roles": [ROLE_ADMIN],
                        "permissions": [PERMISSION_SYSTEM_SETTINGS],
                    },
                    {
                        "id": "menu-settings-logs",
                        "title": "Nh???t k?? ho???t ?????ng",
                        "path": "/dashboard/settings/audit-logs",
                        "roles": [ROLE_ADMIN],
                        "permissions": [PERMISSION_SYSTEM_SETTINGS],
                    },
                ],
            },
        ],
    },
]


def get_role_permissions(role: str) -> List[str]:
    """Retrieve all permission codes for a role."""
    normalized_role = (role or "").strip().upper()
    return ROLE_PERMISSIONS.get(normalized_role, [])


def can_role_access_item(role: str, item: dict) -> bool:
    """
    Check if a role can access a menu item based on:
    1. Role restriction (item['roles'])
    2. Permission restriction (item['permissions'])
    """
    normalized_role = (role or "").strip().upper()
    if not normalized_role:
        return False

    # Check allowed roles if specified
    allowed_roles = item.get("roles")
    if allowed_roles is not None:
        if normalized_role not in allowed_roles:
            return False

    # Check required permissions if specified
    required_permissions = item.get("permissions")
    if required_permissions is not None:
        user_permissions = get_role_permissions(normalized_role)
        # Must have at least one of the required permissions
        if not any(perm in user_permissions for perm in required_permissions):
            return False

    return True


def _filter_items_recursive(items: List[dict], role: str) -> List[dict]:
    """Recursively filter menu items and their children for a given role."""
    filtered_items: List[dict] = []

    for item in items:
        # Check if item itself is accessible for this role
        if not can_role_access_item(role, item):
            continue

        item_copy = deepcopy(item)
        children = item.get("children")
        if children:
            filtered_children = _filter_items_recursive(children, role)
            item_copy["children"] = filtered_children

        filtered_items.append(item_copy)

    return filtered_items


def filter_menu_for_role(role: str) -> List[dict]:
    """
    Filter the master menu structure and return only groups and items
    that the specified role has permission to access.
    """
    normalized_role = (role or "").strip().upper()
    if not normalized_role:
        return []

    result_groups: List[dict] = []

    for group in MASTER_MENU_GROUPS:
        filtered_items = _filter_items_recursive(group["items"], normalized_role)
        if filtered_items:
            group_copy = deepcopy(group)
            group_copy["items"] = filtered_items
            result_groups.append(group_copy)

    return result_groups


def find_menu_item_by_id(menu_id: str) -> Optional[dict]:
    """Search for a menu item by ID across all groups and submenus."""
    target = (menu_id or "").strip()
    if not target:
        return None

    def _search(items: List[dict]) -> Optional[dict]:
        for item in items:
            if item.get("id") == target:
                return item
            if item.get("children"):
                found = _search(item["children"])
                if found:
                    return found
        return None

    for group in MASTER_MENU_GROUPS:
        found = _search(group["items"])
        if found:
            return found

    return None


def check_menu_access(role: str, menu_id: str) -> Tuple[bool, Optional[dict]]:
    """
    Check if a specific role can access a menu item by ID.
    Returns:
    - (True, item_dict) if allowed
    - (False, item_dict) if item exists but access denied
    - (False, None) if item not found
    """
    item = find_menu_item_by_id(menu_id)
    if item is None:
        return False, None

    allowed = can_role_access_item(role, item)
    return allowed, item
