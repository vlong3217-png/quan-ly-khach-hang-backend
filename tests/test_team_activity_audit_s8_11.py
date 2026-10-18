# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.activity_service import FAKE_ACTIVITIES

client = TestClient(app)

def get_auth_token(email: str = 'manager@gmail.com', password: str = '123456') -> str:
    response = client.post(
        '/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200, response.text
    return response.json()['access_token']

@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    FAKE_ACTIVITIES.clear()

def test_team_activity_audit_filtering():
    token = get_auth_token('manager@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    # Test baseline clean state
    resp = client.get('/team-activity-audit', headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()['total_activities'] >= 0

    # Test with seeded items in test scope
    FAKE_ACTIVITIES.extend([
        {"id": 1, "title": "Gọi tư vấn", "type": "CALL", "customer_id": 1, "owner_id": 1, "status": "COMPLETED", "created_at": "2026-10-10T09:00:00"},
        {"id": 2, "title": "Gặp trao đổi", "type": "MEETING", "customer_id": 1, "owner_id": 3, "status": "COMPLETED", "created_at": "2026-10-12T14:30:00"},
    ])

    resp_call = client.get('/team-activity-audit?activity_type=CALL', headers=headers)
    assert resp_call.status_code == 200
    calls = resp_call.json()['activities']
    assert len(calls) == 1
    assert calls[0]['type'] == 'CALL'

    resp_user = client.get('/team-activity-audit?user_id=3', headers=headers)
    assert resp_user.status_code == 200
    user_acts = resp_user.json()['activities']
    assert len(user_acts) == 1
    assert user_acts[0]['owner_id'] == 3

    FAKE_ACTIVITIES.clear()

def test_member_activity_summaries():
    token = get_auth_token('manager@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-audit', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['total_activities'] >= 0
    assert isinstance(data['member_summaries'], list)
