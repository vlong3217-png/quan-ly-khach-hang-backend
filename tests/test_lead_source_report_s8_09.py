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
# 1. AC 1: Số lead, tỷ lệ được nhận, tỷ lệ chuyển đổi thành cơ hội theo nguồn và chiến dịch
# ==============================================================================

def test_lead_sources_and_campaigns_metrics():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['total_leads'] > 0
    assert data['overall_acceptance_rate'] > 0
    assert data['overall_conversion_rate'] > 0
    assert data['total_revenue_generated'] > 0

    # Nguon lead
    sources = data['source_metrics']
    assert len(sources) >= 4
    for s in sources:
        assert s['total_leads'] > 0
        assert s['accepted_leads'] <= s['total_leads']
        assert 0.0 <= s['acceptance_rate'] <= 100.0
        assert s['converted_opportunities'] <= s['total_leads']
        assert 0.0 <= s['conversion_rate'] <= 100.0
        assert s['closed_won_value'] >= 0

    # Chien dich
    campaigns = data['campaign_metrics']
    assert len(campaigns) >= 2
    for c in campaigns:
        assert c['campaign_id'] > 0
        assert c['total_leads'] > 0
        assert 0.0 <= c['acceptance_rate'] <= 100.0
        assert 0.0 <= c['conversion_rate'] <= 100.0

# ==============================================================================
# 2. AC 2: Lọc theo khoảng thời gian
# ==============================================================================

def test_lead_source_filter_by_date_range():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness?start_date=2026-01-01&end_date=2026-10-31', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['start_date'] == '2026-01-01'
    assert data['end_date'] == '2026-10-31'

# ==============================================================================
# 3. AC 3: Xuất Excel
# ==============================================================================

def test_export_lead_source_effectiveness_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness/export-excel', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO HIỆU QUẢ TỪNG NGUỒN LEAD' in content
    assert 'HIỆU QUẢ THEO CHIẾN DỊCH' in content
    assert 'Tỷ lệ được nhận' in content
    assert 'Tỷ lệ chuyển đổi' in content