# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.notification_preference_service import reset_fake_preferences

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
    reset_fake_preferences()

def test_get_default_notification_preferences():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.get('/users/me/notification-preferences', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 'user_id' in data
    prefs = data['preferences']
    assert len(prefs) >= 4
    quote_pref = next((p for p in prefs if p['notification_type'] == 'QUOTE_APPROVAL_REQUIRED'), None)
    assert quote_pref is not None
    assert quote_pref['is_mandatory'] is True
    assert quote_pref['in_app_enabled'] is True
    assert quote_pref['email_enabled'] is True

def test_update_notification_preferences():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Cau hinh rieng cho cac kenh trong ung dung va email
    update_req = {
        'preferences': [
            {
                'notification_type': 'NEW_LEAD_ASSIGNED',
                'in_app_enabled': True,
                'email_enabled': False,
            },
            {
                'notification_type': 'ACTIVITY_REMINDER',
                'in_app_enabled': False,
                'email_enabled': False,
            },
        ]
    }
    resp = client.put('/users/me/notification-preferences', json=update_req, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    prefs = data['preferences']

    lead_pref = next((p for p in prefs if p['notification_type'] == 'NEW_LEAD_ASSIGNED'), None)
    assert lead_pref['in_app_enabled'] is True
    assert lead_pref['email_enabled'] is False

    act_pref = next((p for p in prefs if p['notification_type'] == 'ACTIVITY_REMINDER'), None)
    assert act_pref['in_app_enabled'] is False
    assert act_pref['email_enabled'] is False

def test_cannot_disable_mandatory_notifications():
    token = get_auth_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Khong duoc tat thong bao bat buoc (bao gia cho duyet)
    bad_req = {
        'preferences': [
            {
                'notification_type': 'QUOTE_APPROVAL_REQUIRED',
                'in_app_enabled': False,
                'email_enabled': False,
            }
        ]
    }
    resp = client.put('/users/me/notification-preferences', json=bad_req, headers=headers)
    assert resp.status_code == 400, resp.text
    assert 'không được tắt' in resp.json()['detail']
