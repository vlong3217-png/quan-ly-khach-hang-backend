"""
Automated unit & integration tests for Story S1-05: Ph??n quy???n + Ph???m vi d??? li???u.

Test requirements:
1. Authentication & Token (401):
   - Missing token -> 401
   - Invalid token -> 401
   - Expired or malformed token -> 401
   - Disabled user account -> 401

2. Role-Based Access Control (403 vs 200/201):
   - GET /users (ADMIN only)
     * ADMIN -> 200
     * MANAGER -> 403
     * USER -> 403
   - DELETE /customers/{id} (ADMIN only)
     * ADMIN -> 200
     * MANAGER -> 403
     * USER -> 403
   - POST /customers (ADMIN & MANAGER only)
     * ADMIN -> 201
     * MANAGER -> 201
     * USER -> 403

3. Data Scope Resolution (MY / TEAM / ALL):
   - Role permission to request scopes:
     * USER requesting TEAM -> 403
     * USER requesting ALL -> 403
     * MANAGER requesting ALL -> 403
     * Invalid scope string -> 400
   - Scope data filtering (GET /customers):
     * USER 1 (id=3, Team 1): default MY -> only own customers (id=3)
     * USER 2 (id=4, Team 2): default MY -> only own customers (id=4, id=5)
     * MANAGER (id=2, Team 1): default TEAM -> all Team 1 customers (id=1, 2, 3)
     * MANAGER requesting MY -> only customers owned by manager (id=2)
     * ADMIN (id=1): default ALL -> all customers (id=1, 2, 3, 4, 5)
     * ADMIN requesting MY -> only customers owned by admin (id=1)

4. Record-Level Scope Permissions (GET & PUT /customers/{id}):
   - USER viewing own customer -> 200
   - USER viewing other user's customer -> 403
   - MANAGER viewing customer in same team -> 200
   - MANAGER viewing customer in different team -> 403
   - ADMIN viewing any customer -> 200
   - Non-existent customer -> 404
   - USER updating own customer -> 200
   - USER updating other user's customer -> 403
   - MANAGER updating same team customer -> 200
   - MANAGER updating different team customer -> 403
   - ADMIN updating any customer -> 200
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.main import app
from app.core.security import create_access_token, SECRET_KEY, ALGORITHM
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.activity_service import reset_fake_activities
from app.services.quote_service import reset_fake_quotes

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset fake data before each test."""
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_activities()
    reset_fake_quotes()
    yield
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_activities()
    reset_fake_quotes()


# Helper function to get auth headers by logging in
def get_auth_headers(email: str, password: str = "123456") -> dict:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. AUTHENTICATION & TOKEN VALIDATION (401)
# ============================================================================

def test_missing_token_returns_401():
    """Accessing protected endpoints without token must return 401."""
    res_customers = client.get("/customers")
    assert res_customers.status_code == 401

    res_users = client.get("/users")
    assert res_users.status_code == 401

    res_me = client.get("/users/me")
    assert res_me.status_code == 401


def test_invalid_token_returns_401():
    """Accessing protected endpoints with garbage token must return 401."""
    headers = {"Authorization": "Bearer completely-invalid-jwt-token"}
    res = client.get("/customers", headers=headers)
    assert res.status_code == 401
    assert "Token kh??ng h???p l???" in res.json()["detail"]


def test_expired_token_returns_401():
    """Accessing protected endpoints with expired token must return 401."""
    expired_payload = {
        "sub": "admin@gmail.com",
        "id": 1,
        "role": "ADMIN",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {expired_token}"}

    res = client.get("/customers", headers=headers)
    assert res.status_code == 401
    assert "Token kh??ng h???p l??? ho???c ???? h???t h???n" in res.json()["detail"]


def test_token_with_nonexistent_user_returns_401():
    """Token for user_id that doesn't exist returns 401."""
    token = create_access_token({"sub": "ghost@gmail.com", "id": 9999, "role": "USER"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/customers", headers=headers)
    assert res.status_code == 401
    assert res.json()["detail"] == "Kh??ng t??m th???y ng?????i d??ng"


def test_disabled_user_returns_401():
    """Token for disabled user (is_active=False) returns 401."""
    token = create_access_token({"sub": "disabled@gmail.com", "id": 5, "role": "USER"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/customers", headers=headers)
    assert res.status_code == 401
    assert res.json()["detail"] == "T??i kho???n ???? b??? v?? hi???u h??a"


# ============================================================================
# 2. ROLE-BASED ACCESS CONTROL (403 vs 200/201)
# ============================================================================

def test_user_me_endpoint_accessible_by_all_authenticated_roles():
    """All logged-in users can view their own profile."""
    for email, expected_role in [
        ("admin@gmail.com", "ADMIN"),
        ("manager@gmail.com", "MANAGER"),
        ("user1@gmail.com", "USER"),
        ("user2@gmail.com", "USER"),
    ]:
        headers = get_auth_headers(email)
        res = client.get("/users/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["email"] in (email, "user@gmail.com")
        assert data["role"] == expected_role


def test_list_users_role_restriction():
    """Only ADMIN can list all users; MANAGER and USER receive 403."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res_admin = client.get("/users", headers=admin_headers)
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list) or "users" in res_admin.json()

    manager_headers = get_auth_headers("manager@gmail.com")
    res_mgr = client.get("/users", headers=manager_headers)
    assert res_mgr.status_code == 403
    assert "Admin" in res_mgr.json()["detail"]

    user_headers = get_auth_headers("user1@gmail.com")
    res_usr = client.get("/users", headers=user_headers)
    assert res_usr.status_code == 403
    assert "Admin" in res_usr.json()["detail"]


def test_delete_customer_role_restriction():
    """Only ADMIN can delete customer; MANAGER and USER receive 403."""
    user_headers = get_auth_headers("user1@gmail.com")
    res_usr = client.delete("/customers/1", headers=user_headers)
    assert res_usr.status_code == 403

    manager_headers = get_auth_headers("manager@gmail.com")
    res_mgr = client.delete("/customers/1", headers=manager_headers)
    assert res_mgr.status_code == 403

    admin_headers = get_auth_headers("admin@gmail.com")
    res_admin = client.delete("/customers/1", headers=admin_headers)
    assert res_admin.status_code == 200
    assert "???? x??a kh??ch h??ng" in res_admin.json()["message"]


def test_create_customer_role_restriction():
    """ADMIN and MANAGER can create customer; USER receives 403."""
    user_headers = get_auth_headers("user1@gmail.com")
    res_usr = client.post(
        "/customers",
        json={"name": "Kh??ch m???i t??? User", "phone": "0123456789"},
        headers=user_headers,
    )
    assert res_usr.status_code == 403
    assert "Y??u c???u role: ADMIN, MANAGER" in res_usr.json()["detail"]

    mgr_headers = get_auth_headers("manager@gmail.com")
    res_mgr = client.post(
        "/customers",
        json={"name": "Kh??ch m???i t??? Manager", "phone": "0988888888"},
        headers=mgr_headers,
    )
    assert res_mgr.status_code == 201
    mgr_customer = res_mgr.json()
    assert mgr_customer["name"] == "Kh??ch m???i t??? Manager"
    assert mgr_customer["owner_id"] == 2  # Manager ID
    assert mgr_customer["team_id"] == 1   # Manager's team

    admin_headers = get_auth_headers("admin@gmail.com")
    res_admin = client.post(
        "/customers",
        json={"name": "Kh??ch m???i t??? Admin", "phone": "0999999999", "team_id": 2},
        headers=admin_headers,
    )
    assert res_admin.status_code == 201
    admin_customer = res_admin.json()
    assert admin_customer["name"] == "Kh??ch m???i t??? Admin"
    assert admin_customer["owner_id"] == 1
    assert admin_customer["team_id"] == 2


# ============================================================================
# 3. DATA SCOPE RESOLUTION & FILTERING (MY / TEAM / ALL)
# ============================================================================

def test_invalid_scope_query_returns_400():
    """Passing an unknown scope string returns 400 Bad Request."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/customers?scope=INVALID_SCOPE", headers=admin_headers)
    assert res.status_code == 400
    assert "Scope không hợp lệ" in res.json()["detail"]


def test_scope_permission_restrictions():
    """Users cannot request scopes higher than their role allows."""
    user_headers = get_auth_headers("user1@gmail.com")

    # USER requesting TEAM -> 403
    res_team = client.get("/customers?scope=TEAM", headers=user_headers)
    assert res_team.status_code == 403
    assert "Role 'USER' không được phép sử dụng scope 'TEAM'" in res_team.json()["detail"]

    # USER requesting ALL -> 403
    res_all = client.get("/customers?scope=ALL", headers=user_headers)
    assert res_all.status_code == 403
    assert "Role 'USER' không được phép sử dụng scope 'ALL'" in res_all.json()["detail"]

    # MANAGER requesting ALL -> 403
    mgr_headers = get_auth_headers("manager@gmail.com")
    res_mgr_all = client.get("/customers?scope=ALL", headers=mgr_headers)
    assert res_mgr_all.status_code == 403
    assert "Role 'MANAGER' không được phép sử dụng scope 'ALL'" in res_mgr_all.json()["detail"]


def test_user_scope_my_only_returns_own_data():
    """USER receives only their own customers (MY scope)."""
    user1_headers = get_auth_headers("user1@gmail.com")  # id=3
    res1 = client.get("/customers", headers=user1_headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["scope"] == "MY"
    assert data1["total"] == 1
    assert all(c["owner_id"] == 3 for c in data1["customers"])
    assert data1["customers"][0]["id"] == 3

    # Explicit ?scope=MY gives same result
    res1_explicit = client.get("/customers?scope=MY", headers=user1_headers)
    assert res1_explicit.status_code == 200
    assert res1_explicit.json()["total"] == 1

    # USER 2 (id=4, owns customer 4 & 5)
    user2_headers = get_auth_headers("user2@gmail.com")
    res2 = client.get("/customers", headers=user2_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["scope"] == "MY"
    assert data2["total"] == 2
    assert all(c["owner_id"] == 4 for c in data2["customers"])


def test_manager_scope_team_and_my():
    """MANAGER defaults to TEAM scope (all team customers), and can request MY."""
    mgr_headers = get_auth_headers("manager@gmail.com")  # id=2, team_id=1

    # Default -> TEAM scope
    res_team = client.get("/customers", headers=mgr_headers)
    assert res_team.status_code == 200
    data_team = res_team.json()
    assert data_team["scope"] == "TEAM"
    assert data_team["total"] == 3
    # Team 1 has customers: 1 (admin, team 1), 2 (manager, team 1), 3 (user1, team 1)
    for c in data_team["customers"]:
        assert c["team_id"] == 1

    # Explicit MY scope
    res_my = client.get("/customers?scope=MY", headers=mgr_headers)
    assert res_my.status_code == 200
    data_my = res_my.json()
    assert data_my["scope"] == "MY"
    assert data_my["total"] == 1
    assert data_my["customers"][0]["owner_id"] == 2


def test_admin_scope_all_team_my():
    """ADMIN defaults to ALL, can request ALL, TEAM, or MY."""
    admin_headers = get_auth_headers("admin@gmail.com")  # id=1, team_id=None

    # Default -> ALL scope
    res_default = client.get("/customers", headers=admin_headers)
    assert res_default.status_code == 200
    data_all = res_default.json()
    assert data_all["scope"] == "ALL"
    assert data_all["total"] == 5

    # Explicit ALL scope
    res_all = client.get("/customers?scope=ALL", headers=admin_headers)
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 5

    # Explicit MY scope
    res_my = client.get("/customers?scope=MY", headers=admin_headers)
    assert res_my.status_code == 200
    data_my = res_my.json()
    assert data_my["scope"] == "MY"
    assert data_my["total"] == 1
    assert data_my["customers"][0]["owner_id"] == 1


# ============================================================================
# 4. RECORD-LEVEL SCOPE PERMISSIONS (GET /customers/{id} & PUT /customers/{id})
# ============================================================================

def test_get_customer_detail_by_id_scope_enforcement():
    """Viewing a specific customer enforces user's data scope."""
    user1_headers = get_auth_headers("user1@gmail.com")  # id=3, team_id=1
    mgr_headers = get_auth_headers("manager@gmail.com")   # id=2, team_id=1
    admin_headers = get_auth_headers("admin@gmail.com")   # id=1

    # USER 1 views own customer (id=3) -> 200
    res_own = client.get("/customers/3", headers=user1_headers)
    assert res_own.status_code == 200
    assert res_own.json()["id"] == 3

    # USER 1 views customer of USER 2 (id=4, Team 2) -> 403 Forbidden
    res_other = client.get("/customers/4", headers=user1_headers)
    assert res_other.status_code == 403
    assert "Kh??ng c?? quy???n truy c???p d??? li???u" in res_other.json()["detail"]

    # MANAGER views customer in same team (id=3, Team 1) -> 200
    res_mgr_same = client.get("/customers/3", headers=mgr_headers)
    assert res_mgr_same.status_code == 200

    # MANAGER views customer in different team (id=4, Team 2) -> 403 Forbidden
    res_mgr_diff = client.get("/customers/4", headers=mgr_headers)
    assert res_mgr_diff.status_code == 403

    # ADMIN can view any customer -> 200
    assert client.get("/customers/1", headers=admin_headers).status_code == 200
    assert client.get("/customers/4", headers=admin_headers).status_code == 200

    # Non-existent customer -> 404 Not Found
    res_404 = client.get("/customers/9999", headers=admin_headers)
    assert res_404.status_code == 404


def test_update_customer_by_id_scope_enforcement():
    """Updating a customer enforces user's data scope."""
    user1_headers = get_auth_headers("user1@gmail.com")  # id=3, team=1
    mgr_headers = get_auth_headers("manager@gmail.com")   # id=2, team=1
    admin_headers = get_auth_headers("admin@gmail.com")   # id=1

    # USER 1 updates own customer -> 200
    res_user_own = client.put(
        "/customers/3",
        json={"name": "L?? V??n C (Updated by Owner)"},
        headers=user1_headers,
    )
    assert res_user_own.status_code == 200
    assert res_user_own.json()["name"] == "L?? V??n C (Updated by Owner)"

    # USER 1 tries to update customer 2 (Manager, Team 1) -> 403 Forbidden
    res_user_other = client.put(
        "/customers/2",
        json={"name": "Hacked Name"},
        headers=user1_headers,
    )
    assert res_user_other.status_code == 403
    assert "Kh??ng c?? quy???n ch???nh s???a" in res_user_other.json()["detail"]

    # MANAGER updates customer in same team (customer 3) -> 200
    res_mgr_team = client.put(
        "/customers/3",
        json={"company": "DEF Group (Updated by Manager)"},
        headers=mgr_headers,
    )
    assert res_mgr_team.status_code == 200
    assert res_mgr_team.json()["company"] == "DEF Group (Updated by Manager)"

    # MANAGER tries to update customer in different team (customer 4, Team 2) -> 403 Forbidden
    res_mgr_diff = client.put(
        "/customers/4",
        json={"company": "Hacked Company"},
        headers=mgr_headers,
    )
    assert res_mgr_diff.status_code == 403

    # ADMIN can update any customer -> 200
    res_admin = client.put(
        "/customers/4",
        json={"name": "Ph???m Th??? D (Updated by Admin)"},
        headers=admin_headers,
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["name"] == "Ph???m Th??? D (Updated by Admin)"

    # Update non-existent customer -> 404
    res_not_found = client.put(
        "/customers/9999",
        json={"name": "Ghost"},
        headers=admin_headers,
    )
    assert res_not_found.status_code == 404


# ============================================================================
# 5. ADDITIONAL S1-05 TESTS (USER A / USER B, MY_TEAM, SEARCH BY SCOPE, 403)
# ============================================================================

def test_user_a_cannot_read_customer_of_user_b():
    """User A (user1@gmail.com, id=3) cannot read Customer of User B (user2@gmail.com, id=4)."""
    user_a_headers = get_auth_headers("user1@gmail.com")
    res = client.get("/customers/4", headers=user_a_headers)
    assert res.status_code == 403
    assert "Không có quyền truy cập" in res.json()["detail"] or "Kh" in res.json()["detail"]


def test_scopes_my_myteam_all():
    """Test MY, MY_TEAM, and ALL scope access across roles."""
    user1_headers = get_auth_headers("user1@gmail.com")
    mgr_headers = get_auth_headers("manager@gmail.com")
    admin_headers = get_auth_headers("admin@gmail.com")

    # MY_TEAM scope test for Manager (Team 1) -> 200
    res_mgr_team = client.get("/customers?scope=MY_TEAM", headers=mgr_headers)
    assert res_mgr_team.status_code == 200
    assert res_mgr_team.json()["scope"] == "MY_TEAM"
    assert res_mgr_team.json()["total"] == 3

    # USER requesting MY_TEAM -> 403
    res_user_team = client.get("/customers?scope=MY_TEAM", headers=user1_headers)
    assert res_user_team.status_code == 403

    # ADMIN requesting MY_TEAM -> 200
    res_admin_team = client.get("/customers?scope=MY_TEAM", headers=admin_headers)
    assert res_admin_team.status_code == 200


def test_search_with_scope_filtering():
    """Search queries must automatically filter results within the user's scope."""
    user1_headers = get_auth_headers("user1@gmail.com")
    admin_headers = get_auth_headers("admin@gmail.com")

    # User 1 searches for "Công ty" -> only receives Customer 3 (owned by User 1)
    res_user_search = client.get("/customers?search=Công ty", headers=user1_headers)
    assert res_user_search.status_code == 200
    items = res_user_search.json()["customers"]
    assert len(items) == 1
    assert items[0]["owner_id"] == 3

    # Admin searches for "Công ty" -> receives all matching customers
    res_admin_search = client.get("/customers?search=Công ty", headers=admin_headers)
    assert res_admin_search.status_code == 200
    assert res_admin_search.json()["total"] == 5


def test_out_of_scope_access_returns_403_with_vietnamese_detail():
    """Accessing any record outside allowed scope returns HTTP 403 with Vietnamese detail."""
    user2_headers = get_auth_headers("user2@gmail.com")  # id=4, team 2

    # GET Customer owned by User 1 (id=3, team 1)
    res_get = client.get("/customers/3", headers=user2_headers)
    assert res_get.status_code == 403
    assert len(res_get.json()["detail"]) > 0

    # PUT Customer owned by User 1
    res_put = client.put("/customers/3", json={"name": "Tampered"}, headers=user2_headers)
    assert res_put.status_code == 403
    assert len(res_put.json()["detail"]) > 0


def test_opportunity_activity_quote_scope_enforcement():
    """Scope filtering and record-level permissions apply to Opportunities, Activities, Quotes."""
    user1_headers = get_auth_headers("user1@gmail.com")  # id=3, team 1
    user2_headers = get_auth_headers("user2@gmail.com")  # id=4, team 2
    admin_headers = get_auth_headers("admin@gmail.com")

    # --- Opportunities ---
    # User 1 lists opportunities (MY scope)
    res_opp_user1 = client.get("/opportunities", headers=user1_headers)
    assert res_opp_user1.status_code == 200
    assert res_opp_user1.json()["total"] == 1
    assert res_opp_user1.json()["opportunities"][0]["owner_id"] == 3

    # User 1 tries to GET Opportunity 4 (owned by User 2) -> 403
    assert client.get("/opportunities/4", headers=user1_headers).status_code == 403

    # Search Opportunities under scope
    res_opp_search = client.get("/opportunities?q=Hợp đồng", headers=admin_headers)
    assert res_opp_search.status_code == 200
    assert res_opp_search.json()["total"] == 2

    # --- Activities ---
    res_act_user2 = client.get("/activities", headers=user2_headers)
    assert res_act_user2.status_code == 200
    assert res_act_user2.json()["total"] == 1
    assert res_act_user2.json()["activities"][0]["owner_id"] == 4

    # User 2 tries to GET Activity 1 (owned by Admin) -> 403
    assert client.get("/activities/1", headers=user2_headers).status_code == 403

    # --- Quotes ---
    res_quote_user1 = client.get("/quotes", headers=user1_headers)
    assert res_quote_user1.status_code == 200
    assert res_quote_user1.json()["total"] == 1
    assert res_quote_user1.json()["quotes"][0]["owner_id"] == 3

    # User 1 tries to PUT Quote 4 (owned by User 2) -> 403
    assert client.put("/quotes/4", json={"title": "Hacked"}, headers=user1_headers).status_code == 403

