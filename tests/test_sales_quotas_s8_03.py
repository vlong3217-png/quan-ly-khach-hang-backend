# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.sales_quota_service import reset_fake_quotas

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
    reset_fake_quotas()

def test_create_monthly_and_quarterly_quotas():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    user_month_payload = {
        'quota_type': 'month',
        'period_name': '2026-11',
        'year': 2026,
        'period_number': 11,
        'target_type': 'user',
        'user_id': 3,
        'team_id': 'TEAM_NORTH',
        'target_amount': 50000000.0,
    }
    resp = client.post('/sales-quotas', json=user_month_payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data['target_amount'] == 50000000.0
    assert data['is_locked'] is False

    team_quarter_payload = {
        'quota_type': 'quarter',
        'period_name': '2026-Q4',
        'year': 2026,
        'period_number': 4,
        'target_type': 'team',
        'team_id': 'TEAM_NORTH',
        'target_amount': 300000000.0,
    }
    resp_team = client.post('/sales-quotas', json=team_quarter_payload, headers=headers)
    assert resp_team.status_code == 201, resp_team.text
    assert resp_team.json()['quota_type'] == 'quarter'
    assert resp_team.json()['target_type'] == 'team'

def test_team_quota_validation_warning_when_different():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-11',
        'year': 2026,
        'period_number': 11,
        'target_type': 'team',
        'team_id': 'TEAM_TECH',
        'target_amount': 100000000.0,
    }, headers=headers)

    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-11',
        'year': 2026,
        'period_number': 11,
        'target_type': 'user',
        'user_id': 1,
        'team_id': 'TEAM_TECH',
        'target_amount': 50000000.0,
    }, headers=headers)

    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-11',
        'year': 2026,
        'period_number': 11,
        'target_type': 'user',
        'user_id': 2,
        'team_id': 'TEAM_TECH',
        'target_amount': 40000000.0,
    }, headers=headers)

    val_resp = client.get('/sales-quotas/validate-team?team_id=TEAM_TECH&period_name=2026-11', headers=headers)
    assert val_resp.status_code == 200, val_resp.text
    val_data = val_resp.json()
    assert val_data['is_valid'] is False
    assert val_data['difference'] == 10000000.0
    assert 'Cảnh báo' in val_data['warning']

    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-11',
        'year': 2026,
        'period_number': 11,
        'target_type': 'user',
        'user_id': 3,
        'team_id': 'TEAM_TECH',
        'target_amount': 10000000.0,
    }, headers=headers)

    val_resp2 = client.get('/sales-quotas/validate-team?team_id=TEAM_TECH&period_name=2026-11', headers=headers)
    assert val_resp2.status_code == 200
    assert val_resp2.json()['is_valid'] is True
    assert val_resp2.json()['difference'] == 0.0

def test_locked_quota_requires_reason_and_records_audit():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-01',
        'year': 2026,
        'period_number': 1,
        'target_type': 'user',
        'user_id': 3,
        'team_id': 'TEAM_SOUTH',
        'target_amount': 60000000.0,
    }, headers=headers)
    assert resp.status_code == 201
    q_data = resp.json()
    assert q_data['is_locked'] is True
    quota_id = q_data['id']

    bad_resp = client.put(f'/sales-quotas/{quota_id}', json={'target_amount': 70000000.0}, headers=headers)
    assert bad_resp.status_code == 400
    assert 'phải có lý do' in bad_resp.json()['detail']

    good_resp = client.put(f'/sales-quotas/{quota_id}', json={
        'target_amount': 75000000.0,
        'reason': 'Dieu chinh chi tieu theo phe duyet so 45/QD-TGD',
    }, headers=headers)
    assert good_resp.status_code == 200
    assert good_resp.json()['target_amount'] == 75000000.0

    audit_resp = client.get(f'/sales-quotas/{quota_id}/audit-logs', headers=headers)
    assert audit_resp.status_code == 200
    audits = audit_resp.json()
    assert len(audits) >= 1
    assert 'Dieu chinh' in audits[0]['reason']
    assert audits[0]['old_target_amount'] == 60000000.0
    assert audits[0]['new_target_amount'] == 75000000.0

def test_sales_employee_only_sees_own_quota():
    admin_token = get_auth_token('admin@gmail.com')
    admin_headers = {'Authorization': f'Bearer {admin_token}'}

    # Chi tieu cho user_id = 1 (Admin) va user_id = 3 (User)
    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-12',
        'year': 2026,
        'period_number': 12,
        'target_type': 'user',
        'user_id': 1,
        'team_id': 'TEAM_NORTH',
        'target_amount': 80000000.0,
    }, headers=admin_headers)

    client.post('/sales-quotas', json={
        'quota_type': 'month',
        'period_name': '2026-12',
        'year': 2026,
        'period_number': 12,
        'target_type': 'user',
        'user_id': 3,
        'team_id': 'TEAM_NORTH',
        'target_amount': 120000000.0,
    }, headers=admin_headers)

    # Nhan vien login (user_id = 3, role = USER)
    user_token = get_auth_token('user@gmail.com')
    user_headers = {'Authorization': f'Bearer {user_token}'}

    resp = client.get('/sales-quotas?period_name=2026-12', headers=user_headers)
    assert resp.status_code == 200
    quotas = resp.json()['quotas']
    assert len(quotas) == 1
    assert quotas[0]['user_id'] == 3
    assert quotas[0]['target_amount'] == 120000000.0