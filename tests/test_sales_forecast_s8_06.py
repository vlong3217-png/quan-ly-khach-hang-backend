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
# 1. AC 1 & 2: So sánh 3 con số (đã chốt, dự báo, chỉ tiêu) theo nhân viên, nhóm, toàn khối
# ==============================================================================

def test_forecast_and_quota_progress_report():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['period_name'] == '2026-Q4'

    # 1. Toan khoi
    summary = data['summary']
    assert summary['scope_type'] == 'company'
    assert summary['closed_won_amount'] > 0
    assert summary['weighted_forecast_amount'] > 0
    assert summary['quota_target_amount'] > 0
    assert summary['progress_rate'] > 0

    # 2. Theo nhom
    teams = data['breakdown_by_team']
    assert len(teams) >= 2
    for t in teams:
        assert t['scope_type'] == 'team'
        assert t['closed_won_amount'] > 0
        assert t['weighted_forecast_amount'] > 0
        assert t['quota_target_amount'] > 0

    # 3. Theo nhan vien
    reps = data['breakdown_by_rep']
    assert len(reps) >= 3
    for r in reps:
        assert r['scope_type'] == 'user'
        assert r['closed_won_amount'] > 0
        assert r['weighted_forecast_amount'] > 0
        assert r['quota_target_amount'] > 0

# ==============================================================================
# 2. AC 3: Phân tích lý do thua theo danh mục và theo đối thủ
# ==============================================================================

def test_win_loss_analysis_in_forecast_report():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Theo danh muc
    loss_cat = data['loss_analysis_by_category']
    assert len(loss_cat) >= 3
    assert any('Giá' in c['category'] for c in loss_cat)
    for c in loss_cat:
        assert c['lost_count'] > 0
        assert c['lost_value'] > 0
        assert c['percentage'] > 0

    # Theo doi thu
    loss_comp = data['loss_analysis_by_competitor']
    assert len(loss_comp) >= 2
    assert any('Alpha' in comp['competitor'] for comp in loss_comp)
    for comp in loss_comp:
        assert comp['lost_count'] > 0
        assert comp['lost_value'] > 0

# ==============================================================================
# 3. AC 4: Xuất Excel
# ==============================================================================

def test_export_forecast_report_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report/export-excel?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO DỰ BÁO DOANH SỐ' in content
    assert 'PHÂN TÍCH LÝ DO THUA' in content