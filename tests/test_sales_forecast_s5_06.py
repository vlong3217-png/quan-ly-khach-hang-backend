"""
Tests for Sprint 5 - S5-06: Dự báo doanh số theo trọng số xác suất.

Công thức: Dự báo = Giá trị cơ hội × Xác suất thắng (%) của giai đoạn.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services import auth_service
from app.services.opportunity_service import FAKE_OPPORTUNITIES, reset_fake_opportunities
from app.services.pipeline_service import reset_fake_stages
from app.services.sales_forecast_service import (
    build_sales_forecast,
    calculate_weighted_amount,
    get_period_ranges,
)

client = TestClient(app)

REF = "2026-11-15"  # Quý 4: tháng 10-12; tháng này = 11; tháng sau = 12


def auth(email, role, user_id):
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


ADMIN = lambda: auth("admin@gmail.com", "ADMIN", 1)  # noqa: E731
MANAGER = lambda: auth("manager@gmail.com", "MANAGER", 2)  # noqa: E731  (team 1)
USER3 = lambda: auth("user@gmail.com", "USER", 3)  # noqa: E731  (team 1)
USER4 = lambda: auth("user2@gmail.com", "USER", 4)  # noqa: E731  (team 2)


def opp(id_, value, stage, owner, team, close):
    return {
        "id": id_, "title": f"Opp {id_}", "value": value, "stage": stage,
        "customer_id": None, "owner_id": owner, "team_id": team,
        "expected_close_date": close,
    }


@pytest.fixture(autouse=True)
def setup_data():
    auth_service.reset_fake_users_db()
    reset_fake_stages()
    reset_fake_opportunities()
    FAKE_OPPORTUNITIES.clear()
    FAKE_OPPORTUNITIES.extend([
        # Tháng này (11/2026)
        opp(1, 1000, "PROSPECTING", 3, 1, "2026-11-10"),   # 10% -> 100
        opp(2, 2000, "PROPOSAL", 3, 1, "2026-11-30"),      # 50% -> 1000
        opp(3, 4000, "NEGOTIATION", 4, 2, "2026-11-20"),   # 80% -> 3200
        opp(4, 5000, "CLOSED_WON", 3, 1, "2026-11-05"),    # đã chốt 5000
        opp(5, 9999, "CLOSED_LOST", 3, 1, "2026-11-05"),   # bị loại
        # Tháng sau (12/2026)
        opp(6, 10000, "QUALIFICATION", 3, 1, "2026-12-01"),  # 25% -> 2500
        opp(7, 2000, "NEGOTIATION", 4, 2, "2026-12-31"),     # 80% -> 1600
        # Quý này nhưng tháng trước (10/2026)
        opp(8, 3000, "PROPOSAL", 3, 1, "2026-10-15"),        # 50% -> 1500
        # Ngoài quý
        opp(9, 7000, "PROPOSAL", 3, 1, "2027-01-02"),
        opp(10, 7000, "PROPOSAL", 3, 1, None),
    ])
    for u in auth_service.fake_users_db:
        u["monthly_quota"] = {2: 0.0, 3: 6000.0, 4: 4000.0}.get(u["id"], 0.0)
    yield
    reset_fake_opportunities()
    auth_service.reset_fake_users_db()


# ---------------------------------------------------------------- Công thức
def test_weighted_formula():
    assert calculate_weighted_amount(1000, 10) == 100
    assert calculate_weighted_amount(4000, 80) == 3200
    assert calculate_weighted_amount(1234.5, 25) == 308.62
    assert calculate_weighted_amount(5000, 0) == 0


def test_forecast_weighted_values_this_month():
    r = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN())
    assert r.status_code == 200
    p = r.json()["periods"]["this_month"]
    assert p["weighted_forecast"] == 100 + 1000 + 3200
    assert p["pipeline_amount"] == 1000 + 2000 + 4000
    assert p["closed_won"] == 5000
    assert p["forecast_total"] == 4300 + 5000
    assert p["opportunity_count"] == 3
    by_id = {o["opportunity_id"]: o for o in p["opportunities"]}
    assert by_id[2]["win_probability"] == 50.0
    assert by_id[2]["weighted_amount"] == 1000


def test_closed_lost_excluded():
    r = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN())
    ids = [o["opportunity_id"] for o in r.json()["periods"]["this_month"]["opportunities"]]
    assert 5 not in ids


# ---------------------------------------------------------------- Mốc thời gian
def test_period_ranges():
    ranges = get_period_ranges(date(2026, 11, 15))
    assert ranges["this_month"] == (date(2026, 11, 1), date(2026, 11, 30))
    assert ranges["next_month"] == (date(2026, 12, 1), date(2026, 12, 31))
    assert ranges["this_quarter"] == (date(2026, 10, 1), date(2026, 12, 31))
    # Chuyển năm
    r2 = get_period_ranges(date(2026, 12, 20))
    assert r2["next_month"] == (date(2027, 1, 1), date(2027, 1, 31))
    assert r2["this_quarter"] == (date(2026, 10, 1), date(2026, 12, 31))


def test_period_filtering():
    r = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN()).json()["periods"]
    assert r["next_month"]["weighted_forecast"] == 2500 + 1600
    assert {o["opportunity_id"] for o in r["next_month"]["opportunities"]} == {6, 7}
    q = r["this_quarter"]
    assert {o["opportunity_id"] for o in q["opportunities"]} == {1, 2, 3, 6, 7, 8}
    assert q["weighted_forecast"] == 100 + 1000 + 3200 + 2500 + 1600 + 1500
    assert q["closed_won"] == 5000


def test_next_month_rolls_over_year():
    r = client.get("/sales-forecast?reference_date=2026-12-20", headers=ADMIN()).json()["periods"]
    assert {o["opportunity_id"] for o in r["next_month"]["opportunities"]} == {9}


# ---------------------------------------------------------------- Chỉ tiêu
def test_quota_comparison():
    p = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN()).json()["periods"]
    tm = p["this_month"]
    assert tm["quota"] == 10000
    assert tm["achievement_percent"] == 50.0
    assert tm["forecast_vs_quota_percent"] == 93.0
    assert tm["gap_to_quota"] == 10000 - 9300
    assert p["this_quarter"]["quota"] == 30000


def test_quota_zero_has_no_percent():
    for u in auth_service.fake_users_db:
        u["monthly_quota"] = 0.0
    tm = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN()).json()["periods"]["this_month"]
    assert tm["quota"] == 0
    assert tm["achievement_percent"] is None


# ---------------------------------------------------------------- Lọc owner/team
def test_filter_by_owner_and_team_as_admin():
    r = client.get(f"/sales-forecast?owner_id=4&reference_date={REF}", headers=ADMIN()).json()
    tm = r["periods"]["this_month"]
    assert tm["weighted_forecast"] == 3200
    assert tm["quota"] == 4000
    r = client.get(f"/sales-forecast?team_id=1&reference_date={REF}", headers=ADMIN()).json()
    tm = r["periods"]["this_month"]
    assert tm["weighted_forecast"] == 1100
    assert tm["closed_won"] == 5000
    assert tm["quota"] == 6000


# ---------------------------------------------------------------- Phân quyền
def test_user_sees_only_own_data():
    r = client.get(f"/sales-forecast?reference_date={REF}", headers=USER3())
    assert r.status_code == 200
    body = r.json()
    assert body["owner_id"] == 3
    for per in body["periods"].values():
        assert all(o["owner_id"] == 3 for o in per["opportunities"])
    assert body["periods"]["this_month"]["weighted_forecast"] == 1100


def test_user_forbidden_for_others():
    assert client.get("/sales-forecast?owner_id=4", headers=USER3()).status_code == 403
    assert client.get("/sales-forecast?team_id=1", headers=USER3()).status_code == 403
    assert client.get("/sales-forecast?owner_id=3", headers=USER3()).status_code == 200


def test_manager_defaults_to_team_and_is_limited():
    r = client.get(f"/sales-forecast?reference_date={REF}", headers=MANAGER())
    assert r.status_code == 200
    body = r.json()
    assert body["team_id"] == 1
    for per in body["periods"].values():
        assert all(o["team_id"] == 1 for o in per["opportunities"])
    assert client.get("/sales-forecast?team_id=2", headers=MANAGER()).status_code == 403
    assert client.get("/sales-forecast?owner_id=4", headers=MANAGER()).status_code == 403
    assert client.get("/sales-forecast?owner_id=3", headers=MANAGER()).status_code == 200


def test_admin_sees_everything():
    body = client.get(f"/sales-forecast?reference_date={REF}", headers=ADMIN()).json()
    assert body["owner_id"] is None and body["team_id"] is None
    owners = {o["owner_id"] for o in body["periods"]["this_quarter"]["opportunities"]}
    assert owners == {3, 4}


def test_requires_authentication():
    assert client.get("/sales-forecast").status_code in (401, 403)


def test_service_direct_call():
    res = build_sales_forecast(
        {"id": 1, "role": "ADMIN"}, owner_id=3, reference_date=date(2026, 11, 15)
    )
    assert res["periods"]["this_month"]["weighted_forecast"] == 1100
