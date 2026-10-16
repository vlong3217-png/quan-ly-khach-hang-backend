# -*- coding: utf-8 -*-
import pytest
import time
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
# 1. AC 1: Nhân viên thấy chỉ tiêu, tiến độ, cơ hội đang mở, việc hôm nay, lead chưa liên hệ
# ==============================================================================

def test_sales_employee_dashboard():
    # Login user@gmail.com (role: USER)
    token = get_auth_token('user@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    t0 = time.time()
    resp = client.get('/sales-dashboard', headers=headers)
    duration = time.time() - t0

    assert resp.status_code == 200, resp.text
    assert duration < 2.0, f"Dashboard load time too long: {duration}s"

    res = resp.json()
    assert res['role'] == 'USER'
    data = res['data']

    # Chi tieu va tien do
    assert 'quota_target' in data
    assert 'quota_achieved' in data
    assert 'attainment_rate' in data

    # Co hoi dang mo
    assert 'open_opportunities_count' in data
    assert 'open_opportunities_value' in data

    # Viec hom nay
    assert 'today_tasks_count' in data
    assert 'today_tasks' in data

    # Lead chua lien he
    assert 'uncontacted_leads_count' in data
    assert 'uncontacted_leads' in data

    # Khong thay cac muc quan ly / giam doc
    assert 'member_rankings' not in data
    assert 'total_forecast_weighted' not in data

# ==============================================================================
# 2. AC 2: Trưởng nhóm thấy thêm: xếp hạng thành viên, cơ hội đình trệ, việc quá hạn
# ==============================================================================

def test_team_manager_dashboard():
    # Login manager@gmail.com (role: MANAGER)
    token = get_auth_token('manager@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    t0 = time.time()
    resp = client.get('/sales-dashboard', headers=headers)
    duration = time.time() - t0

    assert resp.status_code == 200, resp.text
    assert duration < 2.0, f"Dashboard load time too long: {duration}s"

    res = resp.json()
    assert res['role'] == 'MANAGER'
    data = res['data']

    # Thấy các mục nhân viên
    assert 'open_opportunities_count' in data
    assert 'today_tasks_count' in data
    assert 'uncontacted_leads_count' in data

    # Thấy thêm xếp hạng thành viên của nhóm
    assert 'member_rankings' in data
    assert len(data['member_rankings']) >= 1

    # Thấy cơ hội đình trệ của nhóm
    assert 'stagnant_opportunities_count' in data
    assert 'stagnant_opportunities' in data

    # Thấy việc quá hạn của nhóm
    assert 'overdue_tasks_count' in data
    assert 'overdue_tasks' in data

    # Không thấy mục riêng của Giám đốc toàn khối
    assert 'total_forecast_weighted' not in data

# ==============================================================================
# 3. AC 3: Giám đốc thấy toàn khối: dự báo so với chỉ tiêu, pipeline theo stage, chốt theo tháng
# ==============================================================================

def test_director_admin_dashboard():
    # Login admin@gmail.com (role: ADMIN / DIRECTOR)
    token = get_auth_token('admin@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    t0 = time.time()
    resp = client.get('/sales-dashboard', headers=headers)
    duration = time.time() - t0

    assert resp.status_code == 200, resp.text
    assert duration < 2.0, f"Dashboard load time too long: {duration}s"

    res = resp.json()
    assert res['role'] in ['ADMIN', 'DIRECTOR']
    data = res['data']

    # Dự báo so với chỉ tiêu
    assert 'total_forecast_weighted' in data
    assert data['total_forecast_weighted'] > 0
    assert 'total_quota_target' in data
    assert 'overall_attainment_rate' in data

    # Giá trị pipeline theo từng giai đoạn
    assert 'pipeline_by_stage' in data
    assert len(data['pipeline_by_stage']) >= 4
    stages = [item['stage'] for item in data['pipeline_by_stage']]
    assert 'PROSPECTING' in stages
    assert 'CLOSED_WON' in stages

    # Doanh số đã chốt theo tháng
    assert 'closed_won_by_month' in data
    assert len(data['closed_won_by_month']) >= 3
    months = [item['month'] for item in data['closed_won_by_month']]
    assert '2026-10' in months

# ==============================================================================
# 4. AC 4: Toàn bộ dữ liệu tải xong dưới 2 giây
# ==============================================================================

def test_dashboard_load_time_under_two_seconds():
    token = get_auth_token('admin@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-dashboard', headers=headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res['load_time_seconds'] < 2.0