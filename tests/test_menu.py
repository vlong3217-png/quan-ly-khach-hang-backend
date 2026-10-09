"""
Automated unit & integration tests for Story S1-06: Menu theo quy???n (Role-based menu).

Test Requirements:
1. Authentication & Token Security (401 Unauthorized):
   - Missing token -> 401
   - Invalid / malformed token -> 401
   - Expired token -> 401
   - Disabled user account -> 401
   - Check endpoint without token -> 401

2. Role ADMIN:
   - GET /auth/menu & GET /menu -> 200 OK
   - Role = ADMIN, Scope = ALL
   - Has all 3 groups: group-core, group-management, group-admin
   - Has all menu items and subitems (dashboard, customers, export, reports, teams, settings)
   - GET /auth/menu/check/menu-settings -> 200 OK
   - GET /auth/menu/check/menu-reports -> 200 OK
   - GET /auth/menu/check/menu-customers-export -> 200 OK
   - GET /auth/menu/admin-config -> 200 OK

3. Role MANAGER:
   - GET /auth/menu & GET /menu -> 200 OK
   - Role = MANAGER, Scope = TEAM
   - Has 2 groups: group-core, group-management
   - group-admin is completely HIDDEN
   - Has export, reports, teams
   - menu-settings is completely HIDDEN
   - GET /auth/menu/check/menu-reports -> 200 OK
   - GET /auth/menu/check/menu-customers-export -> 200 OK
   - GET /auth/menu/check/menu-settings -> 403 Forbidden
   - GET /auth/menu/admin-config -> 403 Forbidden

4. Role USER:
   - GET /auth/menu & GET /menu -> 200 OK
   - Role = USER, Scope = MY
   - Has only 1 group: group-core
   - group-management and group-admin are completely HIDDEN
   - In group-core: menu-customers-export is completely HIDDEN
   - GET /auth/menu/check/menu-dashboard -> 200 OK
   - GET /auth/menu/check/menu-customers-list -> 200 OK
   - GET /auth/menu/check/menu-customers-create -> 200 OK
   - GET /auth/menu/check/menu-customers-export -> 403 Forbidden
   - GET /auth/menu/check/menu-reports -> 403 Forbidden
   - GET /auth/menu/check/menu-teams -> 403 Forbidden
   - GET /auth/menu/check/menu-settings -> 403 Forbidden
   - GET /auth/menu/admin-config -> 403 Forbidden

5. Non-existent Menu item (404 Not Found):
   - GET /auth/menu/check/non-existent-menu -> 404 Not Found
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.security import ALGORITHM, SECRET_KEY, create_access_token
from app.main import app

client = TestClient(app)


def get_auth_headers(email: str, password: str = "123456") -> dict:
    """Helper to authenticate and return Bearer auth headers."""
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def extract_all_menu_ids(menu_groups: list) -> list:
    """Recursively extract all menu IDs from groups and items."""
    ids = []
    def _collect(items):
        for item in items:
            ids.append(item["id"])
            if item.get("children"):
                _collect(item["children"])

    for group in menu_groups:
        _collect(group.get("items", []))
    return ids


# ============================================================================
# 1. AUTHENTICATION & TOKEN VALIDATION (401)
# ============================================================================

def test_menu_missing_token_returns_401():
    """Accessing /auth/menu or /menu without token must return 401."""
    res1 = client.get("/auth/menu")
    assert res1.status_code == 401

    res2 = client.get("/menu")
    assert res2.status_code == 401

    res3 = client.get("/auth/menu/check/menu-dashboard")
    assert res3.status_code == 401

    res4 = client.get("/auth/menu/admin-config")
    assert res4.status_code == 401


def test_menu_invalid_token_returns_401():
    """Accessing with invalid or malformed token must return 401."""
    bad_headers = {"Authorization": "Bearer invalid.token.value"}
    res = client.get("/auth/menu", headers=bad_headers)
    assert res.status_code == 401

    res_check = client.get("/auth/menu/check/menu-dashboard", headers=bad_headers)
    assert res_check.status_code == 401


def test_menu_expired_token_returns_401():
    """Accessing with expired token must return 401."""
    expired_payload = {
        "sub": "admin@gmail.com",
        "id": 1,
        "role": "ADMIN",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {expired_token}"}

    res = client.get("/auth/menu", headers=headers)
    assert res.status_code == 401


def test_menu_disabled_user_returns_401():
    """Disabled user accessing menu endpoints must receive 401."""
    token = create_access_token({
        "sub": "disabled@gmail.com",
        "id": 5,
        "role": "USER",
    })
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/auth/menu", headers=headers)
    assert res.status_code == 401
    assert "vô hiệu hóa" in res.json()["detail"] or "bị vô hiệu hóa" in res.json()["detail"]


# ============================================================================
# 2. ROLE ADMIN TESTS
# ============================================================================

def test_admin_receives_all_menu_groups_and_items():
    """ADMIN must receive all 3 menu groups and all top-level / sub-items."""
    headers = get_auth_headers("admin@gmail.com")

    for endpoint in ["/auth/menu", "/menu"]:
        res = client.get(endpoint, headers=headers)
        assert res.status_code == 200, f"Failed for endpoint {endpoint}"
        data = res.json()

        assert data["role"] == "ADMIN"
        assert data["user_id"] == 1
        assert data["data_scope"] == "ALL"
        assert "SYSTEM_SETTINGS" in data["permissions"]
        assert "CUSTOMER_EXPORT" in data["permissions"]

        group_ids = [g["id"] for g in data["menu_groups"]]
        assert "group-core" in group_ids
        assert "group-management" in group_ids
        assert "group-admin" in group_ids
        assert len(group_ids) == 3

        all_ids = extract_all_menu_ids(data["menu_groups"])
        assert "menu-dashboard" in all_ids
        assert "menu-customers" in all_ids
        assert "menu-customers-list" in all_ids
        assert "menu-customers-create" in all_ids
        assert "menu-customers-export" in all_ids
        assert "menu-teams" in all_ids
        assert "menu-teams-members" in all_ids
        assert "menu-teams-assignments" in all_ids
        assert "menu-settings" in all_ids
        assert "menu-settings-general" in all_ids
        assert "menu-settings-roles" in all_ids
        assert "menu-settings-logs" in all_ids


def test_admin_menu_access_checks():
    """ADMIN must have access to all menu items when checked via /menu/check."""
    headers = get_auth_headers("admin@gmail.com")

    for menu_id in [
        "menu-dashboard",
        "menu-customers-export",
        "menu-teams",
        "menu-settings",
        "menu-settings-roles",
    ]:
        res = client.get(f"/auth/menu/check/{menu_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["allowed"] is True
        assert res.json()["menu_id"] == menu_id


def test_admin_can_access_admin_config():
    """ADMIN can view the unfiltered Master Menu config."""
    headers = get_auth_headers("admin@gmail.com")
    res = client.get("/auth/menu/admin-config", headers=headers)
    assert res.status_code == 200
    assert res.json()["total_groups"] == 3


# ============================================================================
# 3. ROLE MANAGER TESTS
# ============================================================================

def test_manager_receives_core_and_management_menus_only():
    """
    MANAGER must receive group-core and group-management.
    group-admin and menu-settings must be completely HIDDEN.
    """
    headers = get_auth_headers("manager@gmail.com")

    res = client.get("/auth/menu", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["role"] == "MANAGER"
    assert data["user_id"] == 2
    assert data["data_scope"] == "TEAM"

    group_ids = [g["id"] for g in data["menu_groups"]]
    assert "group-core" in group_ids
    assert "group-management" in group_ids
    assert "group-admin" not in group_ids, "MANAGER must NOT receive group-admin"
    assert len(group_ids) == 2

    all_ids = extract_all_menu_ids(data["menu_groups"])
    # Allowed items
    assert "menu-dashboard" in all_ids
    assert "menu-customers" in all_ids
    assert "menu-customers-list" in all_ids
    assert "menu-customers-create" in all_ids
    assert "menu-customers-export" in all_ids, "MANAGER must have customer export"
    assert "menu-teams" in all_ids, "MANAGER must have teams"

    # Restricted items
    assert "menu-settings" not in all_ids, "MANAGER must NOT see menu-settings"
    assert "menu-settings-general" not in all_ids
    assert "menu-settings-roles" not in all_ids
    assert "menu-settings-logs" not in all_ids


def test_manager_menu_access_checks():
    """MANAGER access check tests: allowed for export/teams, 403 for settings."""
    headers = get_auth_headers("manager@gmail.com")

    # Allowed items -> 200
    for menu_id in ["menu-dashboard", "menu-customers-export", "menu-teams"]:
        res = client.get(f"/auth/menu/check/{menu_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["allowed"] is True

    # Forbidden items -> 403
    res_settings = client.get("/auth/menu/check/menu-settings", headers=headers)
    assert res_settings.status_code == 403
    assert "kh??ng c?? quy???n" in res_settings.json()["detail"].lower()

    res_roles = client.get("/auth/menu/check/menu-settings-roles", headers=headers)
    assert res_roles.status_code == 403


def test_manager_access_admin_config_returns_403():
    """MANAGER cannot access /auth/menu/admin-config -> 403 Forbidden."""
    headers = get_auth_headers("manager@gmail.com")
    res = client.get("/auth/menu/admin-config", headers=headers)
    assert res.status_code == 403


# ============================================================================
# 4. ROLE USER TESTS
# ============================================================================

def test_user_receives_only_core_menu_without_export():
    """
    USER must receive only group-core.
    group-management and group-admin must be completely HIDDEN.
    Inside group-core, menu-customers-export must be HIDDEN.
    """
    headers = get_auth_headers("user1@gmail.com")

    res = client.get("/auth/menu", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["role"] == "USER"
    assert data["user_id"] == 3
    assert data["data_scope"] == "MY"

    group_ids = [g["id"] for g in data["menu_groups"]]
    assert group_ids == ["group-core"], "USER must only see group-core"

    all_ids = extract_all_menu_ids(data["menu_groups"])
    # Allowed items
    assert "menu-dashboard" in all_ids
    assert "menu-customers" in all_ids
    assert "menu-customers-list" in all_ids
    assert "menu-customers-create" in all_ids

    # Restricted items
    assert "menu-customers-export" not in all_ids, "USER must NOT see menu-customers-export"
    assert "menu-teams" not in all_ids, "USER must NOT see menu-teams"
    assert "menu-settings" not in all_ids, "USER must NOT see menu-settings"


def test_user_menu_access_checks():
    """USER access checks: allowed for dashboard/list/create, 403 for export/teams/settings."""
    headers = get_auth_headers("user1@gmail.com")

    # Allowed -> 200
    for menu_id in ["menu-dashboard", "menu-customers", "menu-customers-list", "menu-customers-create"]:
        res = client.get(f"/auth/menu/check/{menu_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["allowed"] is True

    # Forbidden -> 403
    for menu_id in [
        "menu-customers-export",
        "menu-teams",
        "menu-teams-members",
        "menu-settings",
        "menu-settings-roles",
    ]:
        res = client.get(f"/auth/menu/check/{menu_id}", headers=headers)
        assert res.status_code == 403, f"Expected 403 for {menu_id}, got {res.status_code}"
        assert "kh??ng c?? quy???n" in res.json()["detail"].lower()


def test_user_access_admin_config_returns_403():
    """USER cannot access /auth/menu/admin-config -> 403 Forbidden."""
    headers = get_auth_headers("user1@gmail.com")
    res = client.get("/auth/menu/admin-config", headers=headers)
    assert res.status_code == 403


# ============================================================================
# 5. NON-EXISTENT MENU ITEM CHECK (404)
# ============================================================================

def test_check_non_existent_menu_returns_404():
    """Checking a menu ID that does not exist in master config must return 404."""
    headers = get_auth_headers("admin@gmail.com")
    res = client.get("/auth/menu/check/unknown-menu-xyz", headers=headers)
    assert res.status_code == 404
    assert "kh??ng t???n t???i" in res.json()["detail"].lower()
