# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users

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

# ==============================================================================
# 1. AC 1: Lọc theo khoảng thời gian, loại hoạt động, thành viên
# ==============================================================================

def test_team_activity_audit_filtering():
    token = get_auth_token('manager@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    # 1. Lọc theo loại hoạt động (CALL)
    resp_call = client.get('/team-activity-audit?activity_type=CALL', headers=headers)
    assert resp_call.status_code == 200, resp_call.text
    calls = resp_call.json()['activities']
    assert len(calls) >= 1
    for c in calls:
        assert c['type'] == 'CALL'

    # 2. Lọc theo thành viên (user_id = 3)
    resp_user = client.get('/team-activity-audit?user_id=3', headers=headers)
    assert resp_user.status_code == 200
    user_acts = resp_user.json()['activities']
    assert len(user_acts) >= 1
    for a in user_acts:
        assert a['owner_id'] == 3

    # 3. Lọc theo khoảng thời gian
    resp_date = client.get('/team-activity-audit?start_date=2026-10-01&end_date=2026-10-31', headers=headers)
    assert resp_date.status_code == 200
    date_acts = resp_date.json()['activities']
    assert len(date_acts) >= 1

# ==============================================================================
# 2. AC 2: Hiển thị tổng số hoạt động theo từng thành viên
# ==============================================================================

def test_member_activity_summaries():
    token = get_auth_token('manager@gmail.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-audit', headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data['total_activities'] >= 5
    summaries = data['member_summaries']
    assert len(summaries) >= 2

    # Kiểm tra cấu trúc tổng kết của thành viên
    for s in summaries:
        assert s['user_id'] > 0
        assert s['user_name'] != ''
        assert s['total_activities'] == (s['call_count'] + s['meeting_count'] + s['email_count'] + s['task_count'])
        assert s['total_activities'] > 0