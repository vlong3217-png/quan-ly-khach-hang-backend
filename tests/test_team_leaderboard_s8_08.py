# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.team_leaderboard_service import reset_leaderboard_config

client = TestClient(app)

def get_auth_token(email: str = 'user@gmail.com', password: str = '123456') -> str:
    response = client.post(
        '/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200, response.text
    return response.json()['access_token']

@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_leaderboard_config()

def test_leaderboard_rankings_and_quota_progress():
    token = get_auth_token('user@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-leaderboard?period_name=2026-10', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['is_feature_enabled'] is True
    assert isinstance(data['rankings'], list)

def test_employee_only_sees_own_team_rankings():
    token = get_auth_token('user@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-leaderboard?period_name=2026-10', headers=headers)
    assert resp.status_code == 200
    rankings = resp.json()['rankings']
    assert isinstance(rankings, list)

def test_toggle_leaderboard_feature_configuration():
    token = get_auth_token('admin@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    off_resp = client.put('/team-leaderboard/config', json={'is_feature_enabled': False}, headers=headers)
    assert off_resp.status_code == 200
    assert off_resp.json()['is_feature_enabled'] is False

    resp_when_off = client.get('/team-leaderboard?period_name=2026-10', headers=headers)
    assert resp_when_off.status_code == 200
    data_off = resp_when_off.json()
    assert data_off['is_feature_enabled'] is False
    assert len(data_off['rankings']) == 0

    on_resp = client.put('/team-leaderboard/config', json={'is_feature_enabled': True}, headers=headers)
    assert on_resp.status_code == 200
    assert on_resp.json()['is_feature_enabled'] is True
