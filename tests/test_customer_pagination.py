import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_customers()
    yield
    reset_fake_users()
    reset_fake_customers()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_customer_list_default_pagination():
    """Mặc định trả về phân trang chuẩn với skip=0, limit=20, page=1."""
    headers = get_auth_headers("admin@gmail.com")
    res = client.get("/customers", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 5
    assert len(data["customers"]) == 5
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert data["page"] == 1
    assert data["total_pages"] == 1


def test_customer_list_page_and_limit():
    """Phân trang theo page và limit (page=1, limit=2 -> 2 khách hàng, page=3, limit=2 -> 1 khách hàng)."""
    headers = get_auth_headers("admin@gmail.com")

    # Page 1, limit 2
    res_p1 = client.get("/customers?page=1&limit=2", headers=headers)
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["total"] == 5
    assert len(d1["customers"]) == 2
    assert d1["page"] == 1
    assert d1["limit"] == 2
    assert d1["total_pages"] == 3
    assert d1["customers"][0]["id"] == 1
    assert d1["customers"][1]["id"] == 2

    # Page 2, limit 2
    res_p2 = client.get("/customers?page=2&limit=2", headers=headers)
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert d2["total"] == 5
    assert len(d2["customers"]) == 2
    assert d2["page"] == 2
    assert d2["customers"][0]["id"] == 3
    assert d2["customers"][1]["id"] == 4

    # Page 3, limit 2 (còn 1 khách hàng cuối)
    res_p3 = client.get("/customers?page=3&limit=2", headers=headers)
    assert res_p3.status_code == 200
    d3 = res_p3.json()
    assert d3["total"] == 5
    assert len(d3["customers"]) == 1
    assert d3["page"] == 3
    assert d3["customers"][0]["id"] == 5


def test_customer_list_skip_and_limit():
    """Phân trang theo skip (offset) và limit."""
    headers = get_auth_headers("admin@gmail.com")
    res = client.get("/customers?skip=2&limit=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert len(data["customers"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2
    assert data["page"] == 2
    assert data["customers"][0]["id"] == 3


def test_customer_pagination_with_search():
    """Phân trang kết hợp với tìm kiếm (search)."""
    headers = get_auth_headers("admin@gmail.com")
    res = client.get("/customers?search=Công ty&page=1&limit=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5  # cả 5 khách hàng đều có 'Công ty'
    assert len(data["customers"]) == 2
    assert data["page"] == 1
    assert data["total_pages"] == 3
