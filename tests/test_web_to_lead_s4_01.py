import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.lead import Lead, LeadSourceConfig
from app.services.lead_service import _ip_submission_timestamps

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_lead_data():
    """Dọn dẹp dữ liệu bảng leads, lead_forms và bộ nhớ tạm rate limit trước mỗi test."""
    _ip_submission_timestamps.clear()
    db = SessionLocal()
    try:
        db.query(Lead).delete()
        db.query(LeadSourceConfig).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield
    _ip_submission_timestamps.clear()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    """Hàm hỗ trợ lấy access token đăng nhập cho test."""
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# TEST CASES CHO S4-01: WEB-TO-LEAD
# ============================================================================

def test_create_lead_form_and_generate_embed_code():
    """
    AC S4-01: Sinh mã nhúng cho một biểu mẫu, dán được vào website bất kỳ.
    - Tạo biểu mẫu thành công và nhận lại form_key duy nhất.
    - Lấy đầy đủ mã nhúng: embed_script_tag, embed_iframe_code, embed_html_form.
    """
    headers = get_auth_headers()
    payload = {
        "name": "Biểu mẫu Đăng ký Dùng thử ERP",
        "source_name": "Landing Page ERP 2026",
        "description": "Form nhúng trên trang chủ chiến dịch Q4",
        "rate_limit_per_minute": 5,
    }
    res = client.post("/lead-forms", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "form_key" in data
    assert data["name"] == payload["name"]
    assert data["source_name"] == payload["source_name"]
    assert data["is_active"] is True
    assert "embed_script_tag" in data
    assert "embed_iframe_code" in data

    form_key = data["form_key"]

    # Kiểm tra endpoint lấy chi tiết mã nhúng
    res_embed = client.get(f"/lead-forms/{form_key}/embed-code", headers=headers)
    assert res_embed.status_code == 200
    embed_data = res_embed.json()
    assert form_key in embed_data["endpoint_url"]
    assert f"crm-lead-form-{form_key}" in embed_data["embed_script_tag"]
    assert f"/lead-forms/{form_key}/render" in embed_data["embed_iframe_code"]


def test_render_lead_form_iframe():
    """AC S4-01: Render trang biểu mẫu độc lập để nhúng iframe trên website."""
    headers = get_auth_headers()
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Khảo sát Nhu cầu", "source_name": "Website Banner"},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    render_res = client.get(f"/lead-forms/{form_key}/render")
    assert render_res.status_code == 200
    assert "text/html" in render_res.headers["content-type"]
    assert "Form Khảo sát Nhu cầu" in render_res.text
    assert 'id="full_name"' in render_res.text
    assert 'id="email"' in render_res.text


def test_submit_web_to_lead_success():
    """
    AC S4-01:
    - Biểu mẫu gồm họ tên, email, số điện thoại, công ty, nhu cầu quan tâm.
    - Gửi thành công tạo lead ở trạng thái 'Mới' (NEW) và gắn đúng nguồn của biểu mẫu.
    """
    headers = get_auth_headers()
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Tư vấn Chuyển đổi số", "source_name": "Google Ads Search"},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    # Public submit từ website bên ngoài (không cần token đăng nhập)
    submit_payload = {
        "full_name": "Trần Thị Thu Hà",
        "email": "ha.tran@vinacorp.vn",
        "phone": "0987654321",
        "company": "Tập đoàn VinaCorp",
        "interest": "Quan tâm giải pháp CRM quản lý 50 nhân viên kinh doanh",
    }
    res_submit = client.post(f"/lead-forms/{form_key}/submit", json=submit_payload)
    assert res_submit.status_code == 201
    submit_data = res_submit.json()
    assert submit_data["success"] is True
    assert submit_data["status"] == "NEW"
    lead_id = submit_data["lead_id"]
    assert lead_id is not None

    # Kiểm tra lead xuất hiện trong danh sách CRM của nhân viên
    res_list = client.get(f"/leads/{lead_id}", headers=headers)
    assert res_list.status_code == 200
    lead_detail = res_list.json()
    assert lead_detail["full_name"] == "Trần Thị Thu Hà"
    assert lead_detail["email"] == "ha.tran@vinacorp.vn"
    assert lead_detail["phone"] == "0987654321"
    assert lead_detail["company"] == "Tập đoàn VinaCorp"
    assert lead_detail["interest"] == "Quan tâm giải pháp CRM quản lý 50 nhân viên kinh doanh"
    assert lead_detail["status"] == "NEW"                     # Trạng thái Mới
    assert lead_detail["source"] == "Google Ads Search"       # Gắn đúng nguồn biểu mẫu
    assert lead_detail["form_key"] == form_key


def test_submit_lead_invalid_phone_format():
    """Kiểm tra validation số điện thoại Việt Nam khi nộp lead."""
    headers = get_auth_headers()
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Test Phone", "source_name": "Website"},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    invalid_phone_payload = {
        "full_name": "Nguyễn Văn Lỗi",
        "email": "loi@gmail.com",
        "phone": "123456",  # Không đúng định dạng VN
    }
    res = client.post(f"/lead-forms/{form_key}/submit", json=invalid_phone_payload)
    assert res.status_code == 400
    assert "Số điện thoại không đúng định dạng Việt Nam" in res.json()["detail"]


def test_anti_spam_honeypot_blocking():
    """
    AC S4-01: Chống spam bằng honeypot trap.
    Nếu bot spam tự động điền giá trị vào trường ẩn 'hp_website', hệ thống từ chối ngay.
    """
    headers = get_auth_headers()
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Chống Spam", "source_name": "Website Form"},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    spam_payload = {
        "full_name": "Spam Bot 3000",
        "email": "spambot@spamdomain.ru",
        "phone": "0912345678",
        "hp_website": "http://casino-online-bonus.com",  # Bot tự điền trường ẩn
    }
    res = client.post(f"/lead-forms/{form_key}/submit", json=spam_payload)
    assert res.status_code == 400
    assert "Spam detected" in res.json()["detail"]


def test_rate_limiting_per_ip():
    """
    AC S4-01: Giới hạn tần suất gửi theo địa chỉ IP (Rate limiting).
    Vượt quá rate_limit_per_minute trong vòng 1 phút sẽ nhận mã lỗi 429 Too Many Requests.
    """
    headers = get_auth_headers()
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Rate Limit Test", "source_name": "Web", "rate_limit_per_minute": 3},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    # Gửi 3 lần thành công
    for i in range(3):
        payload = {
            "full_name": f"Khách Hàng {i+1}",
            "email": f"customer_{i+1}@company.com",
            "phone": "0912345678",
        }
        res = client.post(f"/lead-forms/{form_key}/submit", json=payload)
        assert res.status_code == 201

    # Lần thứ 4 gửi liên tiếp trong 1 phút -> Phải bị chặn 429
    excess_payload = {
        "full_name": "Khách Hàng Bị Chặn",
        "email": "blocked@company.com",
        "phone": "0912345678",
    }
    res_excess = client.post(f"/lead-forms/{form_key}/submit", json=excess_payload)
    assert res_excess.status_code == 429
    assert "quá số lần cho phép" in res_excess.json()["detail"]


def test_submit_to_nonexistent_or_inactive_form():
    """Nộp vào form_key không tồn tại hoặc form đã bị tạm dừng."""
    # Form không tồn tại -> 404
    res_404 = client.post("/lead-forms/non_existent_key/submit", json={
        "full_name": "Test",
        "email": "test@gmail.com"
    })
    assert res_404.status_code == 404


def test_filter_and_search_leads():
    """Lọc và tìm kiếm danh sách Lead sau khi thu thập thành công."""
    headers = get_auth_headers()
    # Tạo 2 lead với 2 nguồn khác nhau
    create_res = client.post(
        "/lead-forms",
        json={"name": "Form Hội Thảo", "source_name": "Hội Thảo Tech 2026"},
        headers=headers,
    )
    form_key = create_res.json()["form_key"]

    client.post(f"/lead-forms/{form_key}/submit", json={
        "full_name": "Lê Văn Cường",
        "email": "cuong.le@techhub.vn",
        "company": "TechHub Vietnam",
    })

    # Lọc theo source
    res_filter = client.get("/leads?source=Hội Thảo", headers=headers)
    assert res_filter.status_code == 200
    items = res_filter.json()["items"]
    assert any(lead["email"] == "cuong.le@techhub.vn" for lead in items)

    # Tìm kiếm theo tên
    res_search = client.get("/leads?search=Cường", headers=headers)
    assert res_search.status_code == 200
    assert len(res_search.json()["items"]) >= 1
