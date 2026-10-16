# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.opportunity_service import reset_fake_opportunities

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
    reset_fake_opportunities()

# ==============================================================================
# 1. AC 1: Xuất theo bộ lọc đang áp dụng và gồm cả trường tuỳ chỉnh (Custom fields)
# ==============================================================================

def test_export_opportunities_with_filters_and_custom_fields():
    token = get_auth_token('manager@gmail.com') # Role: MANAGER
    headers = {'Authorization': f'Bearer {token}'}

    # Xuất cơ hội có áp dụng bộ lọc stage=PROSPECTING
    resp = client.get('/opportunities/export-excel?stage=PROSPECTING&include_custom_fields=true', headers=headers)
    assert resp.status_code == 200, resp.text
    assert 'attachment;' in resp.headers.get('content-disposition', '')

    content = resp.content.decode('utf-8-sig')
    lines = content.strip().split('\r\n')
    header_line = lines[0].split(',')

    # Có trường thông tin cơ bản
    assert 'ID' in header_line
    assert 'Tiêu đề cơ hội' in header_line
    assert 'Giai đoạn (Stage)' in header_line

    # Gồm cả trường tuỳ chỉnh
    assert 'Lĩnh vực kinh doanh' in header_line
    assert 'Mức độ ưu tiên' in header_line
    assert 'Kênh tiếp cận' in header_line

    # Dữ liệu xuất ra chỉ chứa stage PROSPECTING
    if len(lines) > 1:
        for data_row in lines[1:]:
            assert 'PROSPECTING' in data_row

# ==============================================================================
# 2. AC 2: Không xuất giá vốn và biên lợi nhuận cho người không có quyền (User thường)
# ==============================================================================

def test_export_opportunities_restricted_cost_and_margin_for_unauthorized():
    # 1. User thường (role: USER) -> Không thấy Giá vốn và Biên lợi nhuận
    user_token = get_auth_token('user@gmail.com')
    user_headers = {'Authorization': f'Bearer {user_token}'}

    resp_user = client.get('/opportunities/export-excel', headers=user_headers)
    assert resp_user.status_code == 200
    user_content = resp_user.content.decode('utf-8-sig')
    user_headers_line = user_content.strip().split('\r\n')[0]

    assert 'Giá vốn (COGS)' not in user_headers_line
    assert 'Lợi nhuận gộp' not in user_headers_line
    assert 'Biên lợi nhuận (%)' not in user_headers_line

    # 2. Người có quyền (role: MANAGER hoặc ADMIN) -> Thấy đầy đủ Giá vốn & Biên lợi nhuận
    mgr_token = get_auth_token('manager@gmail.com')
    mgr_headers = {'Authorization': f'Bearer {mgr_token}'}

    resp_mgr = client.get('/opportunities/export-excel', headers=mgr_headers)
    assert resp_mgr.status_code == 200
    mgr_content = resp_mgr.content.decode('utf-8-sig')
    mgr_headers_line = mgr_content.strip().split('\r\n')[0]

    assert 'Giá vốn (COGS)' in mgr_headers_line
    assert 'Lợi nhuận gộp (Gross Profit)' in mgr_headers_line
    assert 'Biên lợi nhuận (%)' in mgr_headers_line