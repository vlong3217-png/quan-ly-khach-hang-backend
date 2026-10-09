"""
Tests for Sprint 5 - S5-03: Thêm sản phẩm/dịch vụ vào cơ hội bán hàng.

Backlog AC:
- Chọn sản phẩm từ danh mục.
- Nhập số lượng và đơn giá, mặc định lấy từ bảng giá (list_price).
- Kiểm tra giá sàn (floor_price) - không được thấp hơn giá sàn.
- Tự động tính lại giá trị cơ hội khi thêm/sửa/xóa sản phẩm.
- Dịch vụ thuê bao (SUBSCRIPTION) có số kỳ, MRR, ARR và giá trị hợp đồng.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.services.product_service import fake_products_db

client = TestClient(app)


def get_auth_header(email="user@gmail.com", role="USER", user_id=3):
    token = create_access_token(
        data={"sub": email, "id": user_id, "role": role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_data():
    from app.services.opportunity_service import FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS
    FAKE_OPPORTUNITIES.clear()
    FAKE_OPPORTUNITY_PRODUCTS.clear()

    # Tạo một opportunity mẫu do user (user_id=3, team_id=1) sở hữu
    FAKE_OPPORTUNITIES.append({
        "id": 1,
        "title": "Cơ hội triển khai ERP cho Công ty A",
        "value": 0.0,
        "stage": "QUALIFIED",
        "customer_id": 10,
        "owner_id": 3,
        "team_id": 1,
    })

    # Đảm bảo có sản phẩm mẫu trong fake_products_db
    # Tìm sản phẩm ONE_TIME và SUBSCRIPTION
    p_onetime = next((p for p in fake_products_db if p["product_type"] == "ONE_TIME"), None)
    if not p_onetime:
        fake_products_db.append({
            "id": 101,
            "code": "PROD-ONETIME",
            "name": "Bản quyền phần mềm vĩnh viễn",
            "product_type": "ONE_TIME",
            "list_price": 50000000.0,
            "floor_price": 40000000.0,
            "status": "ACTIVE",
        })
    p_sub = next((p for p in fake_products_db if p["product_type"] == "SUBSCRIPTION"), None)
    if not p_sub:
        fake_products_db.append({
            "id": 102,
            "code": "PROD-SAAS",
            "name": "Gói thuê bao Cloud CRM Pro",
            "product_type": "SUBSCRIPTION",
            "list_price": 2000000.0,
            "floor_price": 1500000.0,
            "status": "ACTIVE",
        })


def test_add_product_default_list_price():
    """Thêm sản phẩm không truyền unit_price -> tự lấy list_price từ danh mục và cập nhật value cơ hội."""
    auth = get_auth_header()

    # Lấy sản phẩm 101 hoặc sản phẩm ONE_TIME đầu tiên
    product = next(p for p in fake_products_db if p["product_type"] == "ONE_TIME" and p.get("status") != "DISCONTINUED")

    resp = client.post(
        "/opportunities/1/products",
        json={
            "product_id": product["id"],
            "quantity": 2.0,
        },
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["product_id"] == product["id"]
    assert data["quantity"] == 2.0
    assert data["unit_price"] == product["list_price"]
    expected_amount = 2.0 * product["list_price"]
    assert data["amount"] == expected_amount

    # Kiểm tra cơ hội đã tự động tính lại tổng value
    opp_resp = client.get("/opportunities/1", headers=auth)
    assert opp_resp.status_code == 200
    opp_data = opp_resp.json()
    assert opp_data["value"] == expected_amount
    assert opp_data["has_products"] is True
    assert len(opp_data["products"]) == 1


def test_floor_price_validation():
    """Đơn giá nhập vào thấp hơn giá sàn (floor_price) phải bị từ chối với lỗi 400."""
    auth = get_auth_header()
    product = next(p for p in fake_products_db if p["product_type"] == "ONE_TIME" and p.get("status") != "DISCONTINUED")

    below_floor_price = product["floor_price"] - 1000.0
    resp = client.post(
        "/opportunities/1/products",
        json={
            "product_id": product["id"],
            "quantity": 1.0,
            "unit_price": below_floor_price,
        },
        headers=auth,
    )
    assert resp.status_code == 400
    assert "không được thấp hơn giá sàn" in resp.json()["detail"]


def test_add_subscription_product_calculations():
    """Dịch vụ thuê bao: tính toán đúng số kỳ, MRR, ARR và tổng giá trị hợp đồng."""
    auth = get_auth_header()
    product = next(p for p in fake_products_db if p["product_type"] == "SUBSCRIPTION" and p.get("status") != "DISCONTINUED")

    # Đăng ký gói theo tháng trong 12 kỳ (1 năm), số lượng 5 user, đơn giá lấy list_price
    resp = client.post(
        "/opportunities/1/products",
        json={
            "product_id": product["id"],
            "quantity": 5.0,
            "unit_price": product["list_price"],
            "billing_cycle": "MONTHLY",
            "number_of_cycles": 12,
            "discount_percent": 10.0,
        },
        headers=auth,
    )
    assert resp.status_code == 201
    item = resp.json()

    # Tính toán mong đợi:
    # monthly_sub = 5 * list_price * (1 - 0.10)
    expected_mrr = round(5.0 * product["list_price"] * 0.9, 2)
    expected_arr = round(expected_mrr * 12, 2)
    expected_amount = round(5.0 * product["list_price"] * 12 * 0.9, 2)

    assert item["mrr"] == expected_mrr
    assert item["arr"] == expected_arr
    assert item["amount"] == expected_amount
    assert item["term_months"] == 12

    # Cơ hội cũng phản ánh tổng ARR
    opp_resp = client.get("/opportunities/1", headers=auth)
    assert opp_resp.status_code == 200
    opp = opp_resp.json()
    assert opp["value"] == expected_amount
    assert opp["arr"] == expected_arr


def test_update_product_recalculates_opportunity():
    """Cập nhật số lượng/chiết khấu sản phẩm tự động cập nhật lại tổng giá trị cơ hội."""
    auth = get_auth_header()
    product = next(p for p in fake_products_db if p["product_type"] == "ONE_TIME" and p.get("status") != "DISCONTINUED")

    # Thêm sản phẩm
    add_resp = client.post(
        "/opportunities/1/products",
        json={"product_id": product["id"], "quantity": 1.0, "unit_price": product["list_price"]},
        headers=auth,
    )
    item_id = add_resp.json()["id"]

    # Cập nhật số lượng lên 3 và chiết khấu 10%
    put_resp = client.put(
        f"/opportunities/1/products/{item_id}",
        json={"quantity": 3.0, "discount_percent": 10.0},
        headers=auth,
    )
    assert put_resp.status_code == 200
    updated_item = put_resp.json()
    expected_amount = round(3.0 * product["list_price"] * 0.9, 2)
    assert updated_item["amount"] == expected_amount

    # Xem cơ hội
    opp_resp = client.get("/opportunities/1", headers=auth)
    assert opp_resp.json()["value"] == expected_amount


def test_delete_product_recalculates_opportunity():
    """Xóa sản phẩm trong cơ hội tự động trừ giá trị khỏi cơ hội."""
    auth = get_auth_header()
    product = next(p for p in fake_products_db if p["product_type"] == "ONE_TIME" and p.get("status") != "DISCONTINUED")

    add_resp = client.post(
        "/opportunities/1/products",
        json={"product_id": product["id"], "quantity": 2.0},
        headers=auth,
    )
    item_id = add_resp.json()["id"]

    del_resp = client.delete(f"/opportunities/1/products/{item_id}", headers=auth)
    assert del_resp.status_code == 200

    opp_resp = client.get("/opportunities/1", headers=auth)
    opp = opp_resp.json()
    assert opp["value"] == 0.0
    assert len(opp["products"]) == 0
    assert opp["has_products"] is False
