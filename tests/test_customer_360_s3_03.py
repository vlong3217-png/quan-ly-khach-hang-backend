import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.activity_service import reset_fake_activities

client = TestClient(app)


def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()


def test_customer_360_view_full_data():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch Customer 1 360 view
    resp = client.get("/customers/1/360", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Check basic profile
    customer = data["customer"]
    assert customer["id"] == 1
    assert customer["name"] == "Công ty Cổ phần Công nghệ ABC"
    assert customer["tax_code"] == "0101234567"

    # Check contacts
    assert len(data["contacts"]) >= 2
    assert any(c["name"] == "Nguyễn Văn Giám Đốc" for c in data["contacts"])

    # Check opportunities
    assert len(data["open_opportunities"]) >= 1
    assert data["open_opportunities"][0]["stage"] == "PROPOSAL"
    assert data["total_open_value"] > 0

    # Check activities timeline
    assert len(data["activities_timeline"]) >= 1
    assert any(a["type"] == "MEETING" for a in data["activities_timeline"])

    # Check attachments
    assert len(data["attachments"]) >= 2
    assert any("hop_dong" in a["filename"] for a in data["attachments"])


def test_customer_360_view_scope_forbidden():
    # User 2 belongs to Team B, customer 1 belongs to Team A
    token = get_auth_token("user2@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/1/360", headers=headers)
    assert resp.status_code == 403


def test_customer_360_view_not_found():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/99999/360", headers=headers)
    assert resp.status_code == 404


def test_customer_360_won_value_and_attachments_verified():
    from app.services.opportunity_service import create_opportunity_record
    from app.services.customer_service import add_customer_attachment

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Thêm cơ hội CLOSED_WON
    create_opportunity_record(
        {"title": "Dự án đã ký kết thành công", "value": 150000000.0, "stage": "CLOSED_WON", "customer_id": 1},
        current_user={"id": 1, "team_id": 1},
    )

    # Thêm tệp đính kèm
    add_customer_attachment(
        customer_id=1,
        filename="phu_luc_hop_dong_bo_sung.pdf",
        file_url="/uploads/documents/phu_luc_hop_dong_bo_sung.pdf",
        file_size_bytes=204800,
        uploaded_by="admin",
    )

    resp = client.get("/customers/1/360", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Xác nhận tính đúng tổng giá trị hợp đồng đã ký
    assert data["total_won_value"] >= 150000000.0

    # Xác nhận lưu và truy xuất tệp đính kèm đúng
    assert len(data["attachments"]) >= 3
    att = next((a for a in data["attachments"] if a["filename"] == "phu_luc_hop_dong_bo_sung.pdf"), None)
    assert att is not None
    assert att["file_size_bytes"] == 204800
    assert att["file_url"] == "/uploads/documents/phu_luc_hop_dong_bo_sung.pdf"


def test_customer_360_benchmark_with_500_activities():
    import time
    from app.services.activity_service import FAKE_ACTIVITIES

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo tối thiểu 500 hoạt động cho Customer 1
    bulk_activities = [
        {
            "id": 1000 + i,
            "title": f"Hoạt động tương tác tự động #{i + 1}",
            "type": "CALL" if i % 2 == 0 else "EMAIL",
            "description": f"Ghi chú chi tiết trao đổi định kỳ với khách hàng #{i + 1}",
            "customer_id": 1,
            "owner_id": 1,
            "team_id": 1,
        }
        for i in range(500)
    ]
    FAKE_ACTIVITIES.extend(bulk_activities)

    # Benchmark: thời gian thực thi API phải dưới 1.5 giây
    start_time = time.perf_counter()
    resp = client.get("/customers/1/360", headers=headers)
    elapsed = time.perf_counter() - start_time

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["activities_timeline"]) >= 500
    assert elapsed < 1.5, f"Thời gian thực thi {elapsed:.3f}s vượt quá ngưỡng 1.5s"


def test_customer_360_role_scope_permissions_matrix():
    # Manager Team 1 (id=2, team_id=1) được xem Customer 1 thuộc Team 1
    token_mgr = get_auth_token("manager@gmail.com", "123456")
    res_mgr = client.get("/customers/1/360", headers={"Authorization": f"Bearer {token_mgr}"})
    assert res_mgr.status_code == 200

    # User 1 (id=3, Team 1) sở hữu Customer 3 -> Xem được Customer 3
    token_u1 = get_auth_token("user1@gmail.com", "123456")
    res_u1_own = client.get("/customers/3/360", headers={"Authorization": f"Bearer {token_u1}"})
    assert res_u1_own.status_code == 200

    # User 1 cố tình xem Customer 4 (thuộc Team 2) -> 403 Forbidden
    res_u1_other = client.get("/customers/4/360", headers={"Authorization": f"Bearer {token_u1}"})
    assert res_u1_other.status_code == 403


def test_customer_upload_actual_file_attachment():
    """AC S3-03: Tải lên và truy xuất tệp đính kèm thực tế qua API."""
    import io

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"PDF-1.7 Demo Content Hop Dong Dich Vu Thuc Te 2026"
    files = {"file": ("hop_dong_thuc_te_trien_khai.pdf", io.BytesIO(file_content), "application/pdf")}

    # Upload attachment
    res_upload = client.post("/customers/1/attachments", files=files, headers=headers)
    assert res_upload.status_code == 201
    att_data = res_upload.json()
    assert att_data["filename"] == "hop_dong_thuc_te_trien_khai.pdf"
    assert att_data["file_size_bytes"] == len(file_content)

    # Truy xuất danh sách attachments
    res_list = client.get("/customers/1/attachments", headers=headers)
    assert res_list.status_code == 200
    att_list = res_list.json()
    assert any(a["filename"] == "hop_dong_thuc_te_trien_khai.pdf" for a in att_list)

    # Xuất hiện trong Customer 360 View
    res_360 = client.get("/customers/1/360", headers=headers)
    assert res_360.status_code == 200
    assert any(a["filename"] == "hop_dong_thuc_te_trien_khai.pdf" for a in res_360.json()["attachments"])


def test_contract_actual_won_calculation_with_accepted_quotes():
    """AC S3-03: Xác minh tổng giá trị đã ký từ hợp đồng / báo giá thực tế."""
    from app.services.quote_service import FAKE_QUOTES

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Thêm một báo giá có trạng thái ACCEPTED (hợp đồng đã ký) cho Customer 1
    new_quote = {
        "id": 999,
        "title": "Hợp đồng đã ký chính thức",
        "amount": 88000000.0,
        "status": "ACCEPTED",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
    }
    FAKE_QUOTES.append(new_quote)

    res_360 = client.get("/customers/1/360", headers=headers)
    assert res_360.status_code == 200
    data = res_360.json()
    # Tổng giá trị hợp đồng đã ký phải bao gồm 88,000,000 từ báo giá ACCEPTED
    assert data["total_won_value"] >= 88000000.0

