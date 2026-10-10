import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.pipeline_service import reset_fake_stages

client = TestClient(app)


def get_token(email: str = "user@gmail.com", password: str = "123456") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_stages()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_stages()


# ==============================================================================
# AC S5-01: Tạo và quản lý cơ hội bán hàng (Opportunity Management)
# ==============================================================================

def test_sales_person_creates_opportunity_success():
    """Nhân viên kinh doanh (role USER) tạo cơ hội bán hàng thành công với đầy đủ thông tin."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    future_date = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "title": "Gói giải pháp Chuyển đổi số Doanh nghiệp",
        "customer_id": 1,
        "contact_person": "Nguyễn Văn Đức - Giám đốc Công nghệ",
        "stage": "PROSPECTING",
        "value": 150000000.0,
        "expected_close_date": future_date,
        "source": "Hội thảo Tech Expo 2026",
        "description": "Thương vụ tiếp cận từ sự kiện, khách quan tâm giải pháp CRM Cloud",
    }

    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["title"] == "Gói giải pháp Chuyển đổi số Doanh nghiệp"
    assert data["customer_id"] == 1
    assert data["customer_name"] is not None
    assert data["contact_person"] == "Nguyễn Văn Đức - Giám đốc Công nghệ"
    assert data["stage"] == "PROSPECTING"
    assert data["value"] == 150000000.0
    assert data["source"] == "Hội thảo Tech Expo 2026"
    assert data["expected_close_date"] == future_date
    assert data["owner_id"] == 3  # ID của user@gmail.com
    # Xác suất thắng mặc định của PROSPECTING là 10.0%
    assert data["win_probability"] == 10.0


def test_default_win_probability_by_stage():
    """Xác suất thắng lấy mặc định theo giai đoạn pipeline."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=45)).isoformat()

    # Stage: QUALIFICATION (mặc định 25.0%)
    res1 = client.post(
        "/opportunities",
        json={
            "title": "Cơ hội Đánh giá BANT",
            "customer_id": 2,
            "stage": "QUALIFICATION",
            "value": 80000000.0,
            "expected_close_date": future_date,
        },
        headers=headers,
    )
    assert res1.status_code == 201
    assert res1.json()["win_probability"] == 25.0

    # Stage: PROPOSAL (mặc định 50.0%)
    res2 = client.post(
        "/opportunities",
        json={
            "title": "Cơ hội Báo giá Chính thức",
            "customer_id": 2,
            "stage": "PROPOSAL",
            "value": 120000000.0,
            "expected_close_date": future_date,
        },
        headers=headers,
    )
    assert res2.status_code == 201
    assert res2.json()["win_probability"] == 50.0


def test_override_win_probability_with_notes_success():
    """Sửa tay xác suất thắng khác mặc định của giai đoạn thành công khi có kèm ghi chú."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=20)).isoformat()

    # Giai đoạn PROSPECTING mặc định 10%, sửa tay lên 45% kèm ghi chú giải trình
    payload = {
        "title": "Thương vụ Khách hàng Thân thiết",
        "customer_id": 1,
        "stage": "PROSPECTING",
        "value": 200000000.0,
        "expected_close_date": future_date,
        "win_probability": 45.0,
        "probability_notes": "Khách hàng thân thiết đã có cam kết miệng sẽ ký hợp đồng trong tháng",
    }

    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["win_probability"] == 45.0
    assert data["probability_notes"] == "Khách hàng thân thiết đã có cam kết miệng sẽ ký hợp đồng trong tháng"


def test_override_win_probability_without_notes_rejected():
    """Sửa tay xác suất thắng khác mặc định nhưng không kèm ghi chú sẽ bị từ chối."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=20)).isoformat()

    payload = {
        "title": "Thương vụ thiếu ghi chú",
        "customer_id": 1,
        "stage": "PROSPECTING",  # Mặc định 10.0%
        "value": 50000000.0,
        "expected_close_date": future_date,
        "win_probability": 60.0,  # Khác 10.0%
        "probability_notes": "",   # Để trống ghi chú
    }

    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 400
    assert "ghi chú" in res.json()["detail"].lower()


def test_expected_close_date_in_past_rejected():
    """Ngày dự kiến chốt không được ở quá khứ khi tạo mới."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    past_date = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "title": "Cơ hội có ngày chốt quá khứ",
        "customer_id": 1,
        "stage": "PROSPECTING",
        "value": 30000000.0,
        "expected_close_date": past_date,
    }

    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code in (400, 422)
    assert "quá khứ" in res.text.lower()


def test_multiple_concurrent_opportunities_for_same_customer():
    """Một khách hàng có thể có nhiều cơ hội bán hàng song song."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=60)).isoformat()

    # Tạo cơ hội 1 cho Customer 1
    res1 = client.post(
        "/opportunities",
        json={
            "title": "Cơ hội 1 - Bản quyền phần mềm CRM",
            "customer_id": 1,
            "stage": "PROSPECTING",
            "value": 50000000.0,
            "expected_close_date": future_date,
        },
        headers=headers,
    )
    assert res1.status_code == 201

    # Tạo cơ hội 2 cho cùng Customer 1 (song song)
    res2 = client.post(
        "/opportunities",
        json={
            "title": "Cơ hội 2 - Dịch vụ Tích hợp Hệ thống ERP",
            "customer_id": 1,
            "stage": "QUALIFICATION",
            "value": 120000000.0,
            "expected_close_date": future_date,
        },
        headers=headers,
    )
    assert res2.status_code == 201

    # Lọc danh sách cơ hội theo customer_id = 1 với quyền nhân viên sở hữu (mặc định scope=MY)
    res_list = client.get("/opportunities?customer_id=1", headers=headers)
    assert res_list.status_code == 200
    opps = res_list.json()["opportunities"]
    cust_1_opp_titles = [o["title"] for o in opps if o["customer_id"] == 1]
    assert "Cơ hội 1 - Bản quyền phần mềm CRM" in cust_1_opp_titles
    assert "Cơ hội 2 - Dịch vụ Tích hợp Hệ thống ERP" in cust_1_opp_titles
    assert len(cust_1_opp_titles) >= 2


def test_update_opportunity_details_and_probability():
    """Cập nhật thông tin cơ hội và sửa xác suất thắng kèm ghi chú."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=30)).isoformat()

    create_res = client.post(
        "/opportunities",
        json={
            "title": "Cơ hội ban đầu",
            "customer_id": 1,
            "stage": "PROSPECTING",
            "value": 50000000.0,
            "expected_close_date": future_date,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    opp_id = create_res.json()["id"]

    # Cập nhật thông tin
    new_close_date = (date.today() + timedelta(days=60)).isoformat()
    update_res = client.put(
        f"/opportunities/{opp_id}",
        json={
            "title": "Cơ hội đã cập nhật quy mô",
            "value": 90000000.0,
            "contact_person": "Trần Thị Mai - Trưởng phòng Thu mua",
            "source": "Khách hàng cũ giới thiệu",
            "expected_close_date": new_close_date,
            "win_probability": 70.0,
            "probability_notes": "Khách đã chốt ngân sách duyệt nội bộ",
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Cơ hội đã cập nhật quy mô"
    assert updated_data["value"] == 90000000.0
    assert updated_data["contact_person"] == "Trần Thị Mai - Trưởng phòng Thu mua"
    assert updated_data["source"] == "Khách hàng cũ giới thiệu"
    assert updated_data["win_probability"] == 70.0
    assert updated_data["probability_notes"] == "Khách đã chốt ngân sách duyệt nội bộ"
