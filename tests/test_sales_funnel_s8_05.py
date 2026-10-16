# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users

client = TestClient(app)

def get_auth_token(email: str = 'admin@gmail.com', password: str = '123456') -> str:
    response = client.post(
        '/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200, response.text
    return response.json()['access_token']

@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()

# ==============================================================================
# 1. AC 1: Số cơ hội và giá trị ở từng giai đoạn, tỷ lệ chuyển đổi giữa các giai đoạn
# ==============================================================================

def test_funnel_stages_and_conversion_rates():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-funnel', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['total_opportunities'] > 0
    assert data['total_pipeline_value'] > 0
    stages = data['stages']
    assert len(stages) == 5

    stage_names = [s['stage'] for s in stages]
    assert stage_names == ['PROSPECTING', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'CLOSED_WON']

    for stg in stages:
        assert stg['count'] >= 1
        assert stg['value'] >= 0
        assert 0.0 <= stg['conversion_rate_to_next'] <= 100.0

# ==============================================================================
# 2. AC 2: Thời gian trung bình một cơ hội nằm ở mỗi giai đoạn
# ==============================================================================

def test_stage_average_duration():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-funnel', headers=headers)
    assert resp.status_code == 200
    stages = resp.json()['stages']

    # Moi stage deu co chi so thoi gian trung binh (ngay)
    for stg in stages[:-1]:
        assert stg['avg_duration_days'] > 0.0

# ==============================================================================
# 3. AC 3: Chỉ ra giai đoạn rơi rụng nhiều nhất và giai đoạn tắc lâu nhất
# ==============================================================================

def test_funnel_bottlenecks_and_drop_insights():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-funnel', headers=headers)
    assert resp.status_code == 200
    insights = resp.json()['insights']

    # Giai doan roi rung nhieu nhat
    assert 'highest_drop_stage' in insights
    assert 'highest_drop_count' in insights
    assert insights['highest_drop_count'] > 0
    assert 'highest_drop_rate' in insights

    # Giai doan tac lau nhat
    assert 'longest_stagnant_stage' in insights
    assert 'longest_avg_duration_days' in insights
    assert insights['longest_avg_duration_days'] > 0

    # Negotiation thuong la giai doan dam phan thuong luong lau nhat
    assert insights['longest_stagnant_stage'] == 'NEGOTIATION'

# ==============================================================================
# 4. AC 4: Lọc theo nhóm, nhân viên, sản phẩm, khoảng thời gian
# ==============================================================================

def test_funnel_filters_applied():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Loc theo team_id
    resp_team = client.get('/sales-funnel?team_id=TEAM_NORTH', headers=headers)
    assert resp_team.status_code == 200
    assert resp_team.json()['filters_applied']['team_id'] == 'TEAM_NORTH'

    # Loc theo user_id
    resp_user = client.get('/sales-funnel?user_id=1', headers=headers)
    assert resp_user.status_code == 200
    assert resp_user.json()['filters_applied']['user_id'] == 1

    # Loc theo product_id
    resp_prod = client.get('/sales-funnel?product_id=2', headers=headers)
    assert resp_prod.status_code == 200
    assert resp_prod.json()['filters_applied']['product_id'] == 2

    # Loc theo khoang thoi gian
    resp_time = client.get('/sales-funnel?start_date=2026-01-01&end_date=2026-12-31', headers=headers)
    assert resp_time.status_code == 200
    assert resp_time.json()['filters_applied']['start_date'] == '2026-01-01'
    assert resp_time.json()['filters_applied']['end_date'] == '2026-12-31'