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
# 1. AC 1: Số cuộc gọi, cuộc gặp, báo giá gửi đi theo từng thành viên và theo tuần
# ==============================================================================

def test_team_member_activities_and_weekly_breakdown():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data['team_id'] == 'TEAM_NORTH'
    assert data['total_calls'] > 0
    assert data['total_meetings'] > 0
    assert data['total_quotes_sent'] > 0

    members = data['members']
    assert len(members) >= 3

    for m in members:
        assert m['call_count'] > 0
        assert m['meeting_count'] > 0
        assert m['quote_count'] > 0
        assert m['total_activities'] == (m['call_count'] + m['meeting_count'] + m['quote_count'])

        # Chi tiet theo tuan
        weeks = m['weekly_breakdown']
        assert len(weeks) >= 4
        for w in weeks:
            assert 'Tuần' in w['week_label']
            assert w['total'] == (w['call_count'] + w['meeting_count'] + w['quote_count'])

# ==============================================================================
# 2. AC 2: Tỷ lệ lead được phản hồi trong SLA
# ==============================================================================

def test_team_member_sla_response_rate():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert 0.0 <= data['overall_sla_rate'] <= 100.0
    for m in data['members']:
        assert m['total_leads_assigned'] > 0
        assert m['leads_responded_in_sla'] <= m['total_leads_assigned']
        assert 0.0 <= m['sla_response_rate'] <= 100.0

    # Phat hien thanh vien co SLA thap de kem cap
    low_sla_members = [m for m in data['members'] if m['sla_response_rate'] < 70.0]
    assert len(low_sla_members) >= 1
    assert low_sla_members[0]['user_id'] == 3 # Le Van Sales

# ==============================================================================
# 3. AC 3: Xuất Excel
# ==============================================================================

def test_export_team_activity_sla_excel():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/team-activity-sla/export-excel?team_id=TEAM_NORTH', headers=headers)
    assert resp.status_code == 200
    assert 'attachment;' in resp.headers.get('content-disposition', '')
    content = resp.content.decode('utf-8-sig')
    assert 'BÁO CÁO HOẠT ĐỘNG VÀ NĂNG SUẤT' in content
    assert 'Tỷ lệ đáp ứng SLA' in content
    assert 'CHI TIẾT HOẠT ĐỘNG THEO TUẦN' in content