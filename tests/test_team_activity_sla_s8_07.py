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

def test_team_member_activities_and_weekly_breakdown():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['team_id'] == 'TEAM_NORTH'
    assert data['total_calls'] >= 0
    assert data['total_meetings'] >= 0
    assert data['total_quotes_sent'] >= 0
    assert isinstance(data['members'], list)

def test_team_member_sla_response_rate():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert 0.0 <= data['overall_sla_rate'] <= 100.0
    for m in data['members']:
        assert m['total_leads_assigned'] >= 0
        assert 0.0 <= m['sla_response_rate'] <= 100.0

def test_export_team_activity_sla_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla/export-excel?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO HOẠT ĐỘNG VÀ NĂNG SUẤT' in content
