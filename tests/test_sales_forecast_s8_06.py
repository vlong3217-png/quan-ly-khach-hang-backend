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

def test_forecast_and_quota_progress_report():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['period_name'] == '2026-Q4'

    summary = data['summary']
    assert summary['scope_type'] == 'company'
    assert summary['closed_won_amount'] >= 0
    assert summary['weighted_forecast_amount'] >= 0
    assert summary['quota_target_amount'] >= 0
    assert summary['progress_rate'] >= 0

    teams = data['breakdown_by_team']
    assert isinstance(teams, list)

    reps = data['breakdown_by_rep']
    assert isinstance(reps, list)

def test_win_loss_analysis_in_forecast_report():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    loss_cat = data['loss_analysis_by_category']
    assert isinstance(loss_cat, list)

    loss_comp = data['loss_analysis_by_competitor']
    assert isinstance(loss_comp, list)

def test_export_forecast_report_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-forecast-report/export-excel?period_name=2026-Q4', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO DỰ BÁO DOANH SỐ' in content
