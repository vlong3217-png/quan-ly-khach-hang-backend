import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    yield
    reset_fake_users()


def get_auth_headers(email: str = "user1@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_sample_image(width: int = 500, height: int = 300, format: str = "PNG") -> bytes:
    img = Image.new("RGB", (width, height), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_upload_avatar_valid_image_success():
    """AC S2-03: Tải lên ảnh JPG/PNG hợp lệ -> cắt vuông và lưu thành công."""
    headers = get_auth_headers("user1@gmail.com")
    img_bytes = create_sample_image(600, 400, "PNG")

    files = {"file": ("avatar.png", img_bytes, "image/png")}
    res = client.post("/users/me/avatar", files=files, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["avatar_url"] is not None
    assert "/uploads/avatars/" in data["avatar_url"]

    # Kiểm tra truy cập tĩnh avatar
    avatar_res = client.get(data["avatar_url"])
    assert avatar_res.status_code == 200
    assert "image/png" in avatar_res.headers["content-type"]

    # Kiểm tra ảnh đã được cắt vuông và resize <= 256x256
    saved_img = Image.open(io.BytesIO(avatar_res.content))
    assert saved_img.size[0] == saved_img.size[1]  # Vuông
    assert saved_img.size[0] <= 256


def test_upload_avatar_jpeg_format_success():
    """AC S2-03: Hỗ trợ tệp JPEG."""
    headers = get_auth_headers("user1@gmail.com")
    img_bytes = create_sample_image(300, 300, "JPEG")

    files = {"file": ("avatar.jpg", img_bytes, "image/jpeg")}
    res = client.post("/users/me/avatar", files=files, headers=headers)
    assert res.status_code == 200
    assert res.json()["avatar_url"] is not None


def test_upload_avatar_invalid_extension_rejected():
    """AC S2-03: Từ chối định dạng khác ngoài JPG/PNG (ví dụ: pdf, gif, txt)."""
    headers = get_auth_headers("user1@gmail.com")
    files = {"file": ("document.pdf", b"%PDF-1.4 mock pdf", "application/pdf")}
    res = client.post("/users/me/avatar", files=files, headers=headers)
    assert res.status_code == 400
    assert "JPG, JPEG hoặc PNG" in res.json()["detail"]


def test_upload_avatar_exceed_max_size_2mb():
    """AC S2-03: Từ chối ảnh có dung lượng > 2MB."""
    headers = get_auth_headers("user1@gmail.com")
    # Tạo nội dung lớn hơn 2MB (2.1 MB)
    large_bytes = b"0" * (2 * 1024 * 1024 + 1024)
    files = {"file": ("large_image.png", large_bytes, "image/png")}
    res = client.post("/users/me/avatar", files=files, headers=headers)
    assert res.status_code == 400
    assert "vượt quá giới hạn tối đa" in res.json()["detail"]


def test_delete_avatar_success():
    """Kiểm tra xóa ảnh đại diện đưa avatar_url về null."""
    headers = get_auth_headers("user1@gmail.com")
    # Tải lên trước
    img_bytes = create_sample_image(200, 200, "PNG")
    client.post("/users/me/avatar", files={"file": ("avatar.png", img_bytes, "image/png")}, headers=headers)

    # Xóa
    del_res = client.delete("/users/me/avatar", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["avatar_url"] is None
