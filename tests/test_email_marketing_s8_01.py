# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.email_marketing_service import reset_fake_email_data, FAKE_ACTIVITIES

client = TestClient(app)


def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_email_data()


def test_create_get_and_list_templates():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Tao mau email moi
    payload = {
        "name": "Mau gioi thieu khach hang moi",
        "subject": "XRito -m gui ban {{contact_name}}",
        "body": "Xinchao {{contact_name}}, chung toi tu {{company_name}}, gioi thieu tu {{owner_name}}.",
        "category": "MARKETING",
    }
    resp = client.post("/email-marketing/templates", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    template_id = data["id"]
    assert data["name"] == payload["name"]

    resp_get = client.get(f"/email-marketing/templates/{template_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == template_id

    resp_list = client.get("/email-marketing/templates", headers=headers)
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] >= 1


def test_update_and_delete_template():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create a dummy template first
    create_resp = client.post("/email-marketing/templates", json={
        "name": "Template TED",
        "subject": "Test subject",
        "body": "Content default",
    }, headers=headers)
    assert create_resp.status_code == 201
    tpl_id = create_resp.json()["id"]

    resp_up = client.put(f"/email-marketing/templates/{tpl_id}", json={
        "subject": "Tieude moi - {{contact_name}}",
        "body": "Noi dung moi voi {{product_name}}",
    }, headers=headers)
    assert resp_up.status_code == 200
    data = resp_up.json()
    assert data["subject"] == "Tieude moi - {{contact_name}}"

    resp_del = client.delete(f"/email-marketing/templates/{tpl_id}", headers=headers)
    assert resp_del.status_code == 200
    assert "deleted" in resp_del.json()["message"]


def test_send_email_success_and_log_timeline():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    send_request = {
        "customer_id": 1,
        "recipient_email": "nguyenvana@myaccount.com",
        "subject": "Chao mung {{contact_name}}",
        "body": "Xinchao {{contact_name}}, chung toi tu {{company_name}}, phu trach boi {{owner_name}}.",
        "variables": {
            "contact_name": "Pham Van Binh",
            "company_name": "Cong Ty Tan Phat",
            "owner_name": "Nguyen Trong Hieu"
        },
        "fail_silently": False,
    }
    resp = client.post("/email-marketing/send", json=send_request, headers=headers)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["status"] == "SENT"
    assert "Pham Van Binh" in data["subject"]
    assert "Cong Ty Tan Phat" in data["body"]
    assert "Nguyen Trong Hieu" in data["release_body"] if "release_body" in data else data["body"]

    recent_acts = [a for a in FAKE_ACTIVITIES if a.get("type") == "EMAIL"]
    assert len(recent_acts) >= 1


def test_send_email_fail_and_retry():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    send_req = {
        "customer_id": 1,
        "recipient_email": "fail_user.test@domain.com",
        "subject": "Chuc mung sinh nhat",
        "body": "Cung nhau dong hanh nhe",
        "fail_silently": True,
    }
    resp = client.post("/email-marketing/send", json=send_req, headers=headers)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["status"] == "FAILED"
    log_id = data["id"]

    resp_retry = client.post(f"/email-marketing/logs/{log_id}/retry", headers=headers)
    assert resp_retry.status_code == 200, resp_retry.text
    retry_data = resp_retry.json()
    assert retry_data["status"] == "SENT"
    assert retry_data["retry_count"] == 1
