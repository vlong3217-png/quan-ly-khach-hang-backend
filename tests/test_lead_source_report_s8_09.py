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

def test_lead_sources_and_campaigns_metrics():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['total_leads'] >= 0
    assert data['overall_acceptance_rate'] >= 0
    assert data['overall_conversion_rate'] >= 0
    assert data['total_revenue_generated'] >= 0
    assert isinstance(data['source_metrics'], list)
    assert isinstance(data['campaign_metrics'], list)

def test_lead_source_filter_by_date_range():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness?start_date=2026-01-01&end_date=2026-10-31', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['start_date'] == '2026-01-01'
    assert data['end_date'] == '2026-10-31'

def test_export_lead_source_effectiveness_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/lead-source-effectiveness/export-excel', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO HIỆU QUẢ TỪNG NGUỒN LEAD' in content
