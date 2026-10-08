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


def test_upload_avatar_fake_extension_rejected():
    """
    AC S2-03: Kiểm tra ảnh giả đuôi (file GIF hoặc Text đổi tên thành .png).
    Hệ thống phát hiện định dạng thực tế bằng Pillow và từ chối.
    """
    headers = get_auth_headers("user1@gmail.com")

    # 1. Ảnh GIF đổi tên thành .png
    gif_img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    gif_img.save(buf, format="GIF")
    fake_png_bytes = buf.getvalue()

    res_gif = client.post(
        "/users/me/avatar",
        files={"file": ("fake_image.png", fake_png_bytes, "image/png")},
        headers=headers,
    )
    assert res_gif.status_code == 400
    assert "Định dạng hình ảnh thực tế không hợp lệ" in res_gif.json()["detail"]

    # 2. File Text đổi đuôi thành .jpg
    text_bytes = b"Hello, I am a plain text file posing as an image"
    res_text = client.post(
        "/users/me/avatar",
        files={"file": ("fake_image.jpg", text_bytes, "image/jpeg")},
        headers=headers,
    )
    assert res_text.status_code == 400
    assert "không phải là hình ảnh hợp lệ" in res_text.json()["detail"]


def test_upload_avatar_corrupted_image_rejected():
    """AC S2-03: Kiểm tra file ảnh bị lỗi, hỏng dữ liệu."""
    headers = get_auth_headers("user1@gmail.com")
    corrupted_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\xff" * 50
    res = client.post(
        "/users/me/avatar",
        files={"file": ("corrupted.png", corrupted_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "không phải là hình ảnh hợp lệ" in res.json()["detail"]


def test_upload_avatar_pixel_dimensions_boundary():
    """AC S2-03: Giới hạn kích thước pixel tối thiểu (16x16) và tối đa (4096x4096)."""
    headers = get_auth_headers("user1@gmail.com")

    # Ảnh quá nhỏ (8x8 pixel)
    small_bytes = create_sample_image(8, 8, "PNG")
    res_small = client.post(
        "/users/me/avatar",
        files={"file": ("small.png", small_bytes, "image/png")},
        headers=headers,
    )
    assert res_small.status_code == 400
    assert "Kích thước ảnh quá nhỏ" in res_small.json()["detail"]

    # Ảnh quá lớn (>4096 pixel chiều dài)
    large_dim_bytes = create_sample_image(4500, 100, "PNG")
    res_large = client.post(
        "/users/me/avatar",
        files={"file": ("large_dim.png", large_dim_bytes, "image/png")},
        headers=headers,
    )
    assert res_large.status_code == 400
    assert "Kích thước ảnh quá lớn" in res_large.json()["detail"]


def test_upload_avatar_transparent_rgba_png_success():
    """AC S2-03: Hỗ trợ ảnh trong suốt (RGBA), bảo đảm hiển thị và thumbnail chuẩn."""
    headers = get_auth_headers("user1@gmail.com")
    rgba_img = Image.new("RGBA", (300, 300), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    rgba_img.save(buf, format="PNG")
    rgba_bytes = buf.getvalue()

    res = client.post(
        "/users/me/avatar",
        files={"file": ("transparent.png", rgba_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["avatar_url"] is not None


def test_upload_avatar_no_orphan_file_on_database_failure(monkeypatch):
    """
    AC S2-03: Đảm bảo lỗi ghi database không để lại file mồ côi trên máy chủ.
    """
    import os
    from sqlalchemy.orm import Session

    headers = get_auth_headers("user1@gmail.com")
    img_bytes = create_sample_image(200, 200, "PNG")

    # Giả lập lỗi ghi database
    def mock_commit(self):
        raise RuntimeError("Database commit error on avatar save")

    monkeypatch.setattr(Session, "commit", mock_commit)

    res = client.post(
        "/users/me/avatar",
        files={"file": ("test_orphan.png", img_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 500

    # Kiểm tra trong thư mục uploads/avatars không còn file test_orphan
    avatar_dir = os.path.join(os.getcwd(), "uploads", "avatars")
    if os.path.exists(avatar_dir):
        files_after = [f for f in os.listdir(avatar_dir) if "test_orphan" in f]
        assert len(files_after) == 0

