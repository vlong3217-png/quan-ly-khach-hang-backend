import io
import pytest
import openpyxl
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    yield
    reset_fake_users()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}



def create_test_excel(rows) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Email (*)", "Họ và tên (*)", "Mật khẩu (*)", "Vai trò", "Team ID"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_download_template_admin_success():
    """Admin có thể tải tệp mẫu Excel thành công."""
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/users/template", headers=admin_headers)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["content-type"]
    assert "attachment; filename=user_import_template.xlsx" in res.headers["content-disposition"]
    assert len(res.content) > 1000


def test_download_template_unauthorized_returns_401():
    """Không có token -> HTTP 401."""
    res = client.get("/users/template")
    assert res.status_code == 401


def test_download_template_non_admin_returns_403():
    """User hoặc Manager không phải Admin -> HTTP 403."""
    user_headers = get_auth_headers("user1@gmail.com")
    res = client.get("/users/template", headers=user_headers)
    assert res.status_code == 403


def test_preview_import_invalid_file_extension():
    """Tải lên file không phải excel -> HTTP 400."""
    admin_headers = get_auth_headers("admin@gmail.com")
    files = {"file": ("test.txt", b"plain text", "text/plain")}
    res = client.post("/users/import-preview", files=files, headers=admin_headers)
    assert res.status_code == 400
    assert "Định dạng tệp không được hỗ trợ" in res.json()["detail"]


def test_preview_import_with_valid_and_invalid_rows():
    """AC S2-01: Xem trước và báo lỗi chi tiết theo từng dòng."""
    admin_headers = get_auth_headers("admin@gmail.com")

    test_rows = [
        # Row 1: Valid USER
        ["user_valid_1@example.com", "Nguyễn Văn Hợp Lệ", "Pass@1234", "USER", 1],
        # Row 2: Invalid Email
        ["invalid_email_format", "Lê Văn Sai Email", "Pass@1234", "USER", 1],
        # Row 3: Short password
        ["user_short_pass@example.com", "Trần Thị Ngắn", "123", "USER", 1],
        # Row 4: Existing email in DB
        ["admin@gmail.com", "Admin Đã Có", "Pass@1234", "USER", 1],
        # Row 5: MANAGER missing team_id (S1-09 rule)
        ["manager_no_team@example.com", "Quản Lý Thiếu Team", "Pass@1234", "MANAGER", ""],
        # Row 6: Valid MANAGER with team_id
        ["manager_valid@example.com", "Quản Lý Chuẩn", "Pass@1234", "MANAGER", 2],
    ]

    excel_file = create_test_excel(test_rows)
    files = {"file": ("users_test.xlsx", excel_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    res = client.post("/users/import-preview", files=files, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_rows"] == 6
    assert data["valid_rows_count"] == 2
    assert data["invalid_rows_count"] == 4

    # Kiểm tra dòng 1 hợp lệ
    row1 = next(r for r in data["rows"] if r["row_number"] == 2)  # excel row 2 (row 1 is header)
    assert row1["is_valid"] is True
    assert len(row1["errors"]) == 0

    # Kiểm tra dòng sai email
    row2 = next(r for r in data["rows"] if r["row_number"] == 3)
    assert row2["is_valid"] is False
    assert any("định dạng" in e.lower() for e in row2["errors"])

    # Kiểm tra dòng mật khẩu ngắn
    row3 = next(r for r in data["rows"] if r["row_number"] == 4)
    assert row3["is_valid"] is False
    assert any("6 ký tự" in e.lower() for e in row3["errors"])

    # Kiểm tra dòng email đã tồn tại
    row4 = next(r for r in data["rows"] if r["row_number"] == 5)
    assert row4["is_valid"] is False
    assert any("đã tồn tại" in e.lower() for e in row4["errors"])

    # Kiểm tra dòng MANAGER thiếu team
    row5 = next(r for r in data["rows"] if r["row_number"] == 6)
    assert row5["is_valid"] is False
    assert any("nhóm kinh doanh" in e.lower() for e in row5["errors"])


def test_execute_import_partial_success_and_skip_errors():
    """
    AC S2-01: Dòng lỗi bị bỏ qua, dòng hợp lệ vẫn được nhập, có báo cáo tổng kết.
    """
    admin_headers = get_auth_headers("admin@gmail.com")

    test_rows = [
        # Valid row 1
        ["import_success_1@example.com", "Nhân Viên Mới 1", "Pass@1234", "USER", 1],
        # Error row (empty full name)
        ["import_fail_noname@example.com", "", "Pass@1234", "USER", 1],
        # Valid row 2
        ["import_success_2@example.com", "Nhân Viên Mới 2", "Pass@1234", "USER", 2],
        # Error row (invalid role)
        ["import_fail_role@example.com", "Nhân Viên Sai Role", "Pass@1234", "SUPER_ADMIN", 1],
    ]

    excel_file = create_test_excel(test_rows)
    files = {"file": ("batch_users.xlsx", excel_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    res = client.post("/users/import", files=files, headers=admin_headers)
    assert res.status_code == 200
    summary = res.json()

    assert summary["total_rows"] == 4
    assert summary["imported_count"] == 2
    assert summary["skipped_count"] == 2

    # Kiểm tra trạng thái chi tiết
    success_items = [d for d in summary["details"] if d["status"] == "SUCCESS"]
    skipped_items = [d for d in summary["details"] if d["status"] == "SKIPPED"]
    assert len(success_items) == 2
    assert len(skipped_items) == 2

    # Kiểm tra user mới nhập có thể đăng nhập bình thường vào hệ thống
    login_res = client.post("/auth/login", json={"email": "import_success_1@example.com", "password": "Pass@1234"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
