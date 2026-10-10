import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities, FAKE_OPPORTUNITIES
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
# AC S5-02: Bảng pipeline dạng Kanban & Điều hành cơ hội bán hàng
# ==============================================================================

def test_kanban_board_columns_structure_and_metrics():
    """Bảng Kanban hiển thị mỗi cột là một giai đoạn, có số cơ hội và tổng giá trị cột."""
    token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/opportunities/kanban?scope=ALL", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "columns" in data
    assert len(data["columns"]) == 6  # 6 stages mặc định

    stage_codes = [col["stage_code"] for col in data["columns"]]
    assert "PROSPECTING" in stage_codes
    assert "QUALIFICATION" in stage_codes
    assert "PROPOSAL" in stage_codes
    assert "NEGOTIATION" in stage_codes
    assert "CLOSED_WON" in stage_codes
    assert "CLOSED_LOST" in stage_codes

    # Kiểm tra metric tổng hợp của từng cột
    total_opps = sum(col["count"] for col in data["columns"])
    total_val = sum(col["total_value"] for col in data["columns"])
    assert data["total_opportunities"] == total_opps
    assert round(data["total_pipeline_value"], 2) == round(total_val, 2)

    # Mỗi cột phải có các trường bắt buộc
    for col in data["columns"]:
        assert "stage_id" in col
        assert "stage_name" in col
        assert "default_win_probability" in col
        assert col["count"] >= 0
        assert col["total_value"] >= 0
        assert isinstance(col["opportunities"], list)


def test_kanban_card_information_and_stagnant_warning():
    """Thẻ cơ hội hiển thị tên khách, giá trị, ngày dự kiến chốt và cảnh báo nếu đình trệ."""
    token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo một cơ hội có đầy đủ thông tin và giả lập đình trệ
    future_date = (date.today() + timedelta(days=25)).isoformat()
    opp_item = {
        "id": 999,
        "title": "Dự án Nâng cấp Hệ thống ERP Doanh nghiệp",
        "value": 180000000.0,
        "stage": "PROSPECTING",
        "customer_id": 1,
        "customer_name": "Công ty Cổ phần Công nghệ ABC",
        "contact_person": "Vũ Hải Đăng",
        "owner_id": 1,
        "team_id": 1,
        "expected_close_date": future_date,
        "is_stagnant": True,
        "days_inactive": 16,
        "stagnant_threshold_days": 14,
        "is_flagged": True,
        "flag_reasons": ["Đình trệ không hoạt động 16 ngày"],
    }
    FAKE_OPPORTUNITIES.append(opp_item)

    res = client.get("/opportunities/kanban?scope=ALL", headers=headers)
    assert res.status_code == 200
    data = res.json()

    prospecting_col = next(c for c in data["columns"] if c["stage_code"] == "PROSPECTING")
    target_card = next((card for card in prospecting_col["opportunities"] if card["id"] == 999), None)

    assert target_card is not None
    assert target_card["title"] == "Dự án Nâng cấp Hệ thống ERP Doanh nghiệp"
    assert target_card["customer_name"] == "Công ty Cổ phần Công nghệ ABC"
    assert target_card["value"] == 180000000.0
    assert target_card["expected_close_date"] == future_date
    assert target_card["is_stagnant"] is True
    assert target_card["stagnant_warning"] is not None
    assert "đình trệ" in target_card["stagnant_warning"].lower()


def test_kanban_drag_and_drop_stage_transition():
    """Kéo thả để chuyển giai đoạn cơ hội bán hàng trên bảng Kanban."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Cơ hội id 3 thuộc sở hữu của User 3 (user@gmail.com), ban đầu ở stage PROSPECTING
    res_move = client.patch(
        "/opportunities/3/stage",
        json={"new_stage": "PROPOSAL", "probability": 55.0, "probability_notes": "Khách yêu cầu gửi báo giá gấp"},
        headers=headers,
    )
    assert res_move.status_code == 200, res_move.text
    moved_opp = res_move.json()
    assert moved_opp["stage"] == "PROPOSAL"
    assert moved_opp["win_probability"] == 55.0

    # Kiểm tra trên bảng Kanban xem thẻ đã chuyển sang cột PROPOSAL chưa
    res_kanban = client.get("/opportunities/kanban", headers=headers)
    assert res_kanban.status_code == 200
    data = res_kanban.json()

    proposal_col = next(c for c in data["columns"] if c["stage_code"] == "PROPOSAL")
    card_ids_in_proposal = [c["id"] for c in proposal_col["opportunities"]]
    assert 3 in card_ids_in_proposal

    prospecting_col = next(c for c in data["columns"] if c["stage_code"] == "PROSPECTING")
    card_ids_in_prospecting = [c["id"] for c in prospecting_col["opportunities"]]
    assert 3 not in card_ids_in_prospecting


def test_kanban_data_scope_sales_person_default_sees_only_own():
    """Nhân viên kinh doanh mặc định chỉ thấy cơ hội của mình trên Kanban."""
    token = get_token("user@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/opportunities/kanban", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["scope"] == "MY"

    # Tất cả các thẻ cơ hội trên mọi cột đều phải có owner_id == 3
    for col in data["columns"]:
        for opp in col["opportunities"]:
            assert opp["owner_id"] == 3


def test_kanban_filter_by_owner_and_team():
    """Lọc Kanban theo người sở hữu (owner_id) và nhóm (team_id)."""
    admin_token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Lọc theo owner_id = 2 (Manager)
    res_owner = client.get("/opportunities/kanban?scope=ALL&owner_id=2", headers=headers)
    assert res_owner.status_code == 200
    for col in res_owner.json()["columns"]:
        for opp in col["opportunities"]:
            assert opp["owner_id"] == 2

    # Lọc theo team_id = 1
    res_team = client.get("/opportunities/kanban?scope=ALL&team_id=1", headers=headers)
    assert res_team.status_code == 200
    for col in res_team.json()["columns"]:
        for opp in col["opportunities"]:
            assert opp.get("team_id") == 1


def test_kanban_filter_by_close_date_range():
    """Lọc Kanban theo khoảng ngày dự kiến chốt."""
    admin_token = get_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Thêm 2 cơ hội với 2 ngày chốt khác nhau
    d1 = (date.today() + timedelta(days=10)).isoformat()
    d2 = (date.today() + timedelta(days=50)).isoformat()

    FAKE_OPPORTUNITIES.append({
        "id": 801,
        "title": "Cơ hội Ngày Gần",
        "value": 10000000.0,
        "stage": "PROSPECTING",
        "owner_id": 1,
        "team_id": 1,
        "expected_close_date": d1,
    })
    FAKE_OPPORTUNITIES.append({
        "id": 802,
        "title": "Cơ hội Ngày Xa",
        "value": 20000000.0,
        "stage": "PROSPECTING",
        "owner_id": 1,
        "team_id": 1,
        "expected_close_date": d2,
    })

    # Lọc chỉ lấy khoảng ngày xung quanh d1 (từ hôm nay đến +20 ngày)
    from_date = date.today().isoformat()
    to_date = (date.today() + timedelta(days=20)).isoformat()

    res = client.get(f"/opportunities/kanban?scope=ALL&from_date={from_date}&to_date={to_date}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    prospecting_col = next(c for c in data["columns"] if c["stage_code"] == "PROSPECTING")
    card_ids = [c["id"] for c in prospecting_col["opportunities"]]
    assert 801 in card_ids
    assert 802 not in card_ids
