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

def test_sales_employee_dashboard():
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

    assert 'quota_target' in data
    assert 'quota_achieved' in data
    assert 'attainment_rate' in data
    assert 'open_opportunities_count' in data
    assert 'open_opportunities_value' in data
    assert 'today_tasks_count' in data
    assert 'today_tasks' in data
    assert 'uncontacted_leads_count' in data
    assert 'uncontacted_leads' in data
    assert 'member_rankings' not in data
    assert 'total_forecast_weighted' not in data

def test_team_manager_dashboard():
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

    assert 'open_opportunities_count' in data
    assert 'today_tasks_count' in data
    assert 'uncontacted_leads_count' in data
    assert 'member_rankings' in data
    assert isinstance(data['member_rankings'], list)
    assert 'stagnant_opportunities_count' in data
    assert 'stagnant_opportunities' in data
    assert 'overdue_tasks_count' in data
    assert 'overdue_tasks' in data
    assert 'total_forecast_weighted' not in data

def test_director_admin_dashboard():
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

    assert 'total_forecast_weighted' in data
    assert data['total_forecast_weighted'] >= 0
    assert 'total_quota_target' in data
    assert 'overall_attainment_rate' in data
    assert 'pipeline_by_stage' in data
    assert len(data['pipeline_by_stage']) >= 4
    stages = [item['stage'] for item in data['pipeline_by_stage']]
    assert 'PROSPECTING' in stages
    assert 'CLOSED_WON' in stages
    assert 'closed_won_by_month' in data
    assert isinstance(data['closed_won_by_month'], list)

def test_dashboard_load_time_under_two_seconds():
    token = get_auth_token('admin@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/sales-dashboard', headers=headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res['load_time_seconds'] < 2.0
