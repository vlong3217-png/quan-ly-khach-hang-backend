from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import create_access_token
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.auth_service import (
    login_user,
    get_current_user,
    change_password,
    revoke_token,
    create_password_reset_token,
    reset_password_with_token,
    is_test_environment,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(request: LoginRequest):
    identifier = request.get_identifier()
    if not identifier or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác"
        )

    result = login_user(
        identifier=identifier,
        password=request.password
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác"
        )

    return {
        "success": True,
        "access_token": result["access_token"],
        "token_type": "bearer",
        "user": result["user"]
    }


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
)
def change_password_endpoint(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    success, message = change_password(
        user=current_user,
        current_password=request.current_password,
        new_password=request.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return {
        "success": True,
        "message": message,
    }


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S1-02: Đăng xuất làm mất hiệu lực phiên ngay lập tức phía server.
    """
    token = credentials.credentials
    revoke_token(token)
    return {
        "success": True,
        "message": "Đăng xuất thành công, phiên làm việc đã bị hủy hiệu lực phía server",
    }


@router.post("/refresh")
def refresh_session(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S1-02: Phiên được gia hạn tự động khi còn hoạt động (Sliding session).
    """
    old_token = credentials.credentials
    revoke_token(old_token)
    new_token = create_access_token({
        "sub": current_user["email"],
        "id": current_user["id"],
        "role": current_user["role"],
    })
    return {
        "success": True,
        "access_token": new_token,
        "token_type": "bearer",
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "full_name": current_user["full_name"],
            "role": current_user["role"],
        },
    }


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def forgot_password_endpoint(request: ForgotPasswordRequest):
    """
    AC S1-03: Nhập email nhận được mã xác nhận OTP qua email có hiệu lực 30 phút.
    Email không tồn tại vẫn hiển thị cùng một thông báo an toàn.
    """
    token, user = create_password_reset_token(request.email)
    is_test = is_test_environment()
    return {
        "success": True,
        "message": "Nếu email tồn tại trong hệ thống, mã xác nhận đặt lại mật khẩu đã được gửi đến email của bạn. Vui lòng kiểm tra hộp thư (hoặc mục Spam).",
        "reset_token": token if (user and is_test) else None,
    }


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password_endpoint(request: ResetPasswordRequest):
    """
    AC S1-03: Đặt lại mật khẩu mới thông qua token hợp lệ.
    """
    success, message = reset_password_with_token(
        token=request.token,
        new_password=request.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return {
        "success": True,
        "message": message,
    }




@router.get(
    "/smtp-status",
    status_code=status.HTTP_200_OK,
)
def check_smtp_status():
    """Kiểm tra cấu hình SMTP (đã che mật khẩu)"""
    from app.core.email import get_smtp_config
    cfg = get_smtp_config()
    return {
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "sender": cfg["sender"],
        "has_password": bool(cfg["password"]),
        "use_tls": cfg["use_tls"],
        "use_ssl": cfg["use_ssl"],
        "is_configured": cfg["is_configured"],
    }


@router.get(
    "/test-send-email",
    status_code=status.HTTP_200_OK,
)
def test_send_email_endpoint(to_email: str = "vlong3217@gmail.com"):
    """Thử gửi email và trả về chi tiết kết quả hoặc lỗi cụ thể"""
    from app.core.email import send_password_reset_email, get_smtp_config
    cfg = get_smtp_config()
    ok, msg = send_password_reset_email(to_email, "888999")
    return {
        "success": ok,
        "detail": msg,
        "to_email": to_email,
        "smtp_host": cfg.get("host"),
        "smtp_port": cfg.get("port"),
        "smtp_user": cfg.get("user"),
        "use_tls": cfg.get("use_tls"),
        "use_ssl": cfg.get("use_ssl"),
    }


@router.get(
    "/test-smtp-ipv4",
    status_code=status.HTTP_200_OK,
)
def test_smtp_ipv4_endpoint():
    """Kiểm tra DNS IPv4 vs IPv6 và kết nối socket đến smtp.gmail.com"""
    import socket
    results = {}
    
    # 1. Thử resolve IPv4
    try:
        ipv4_addrs = socket.getaddrinfo("smtp.gmail.com", 587, socket.AF_INET, socket.SOCK_STREAM)
        results["ipv4_dns"] = [x[4][0] for x in ipv4_addrs]
    except Exception as e:
        results["ipv4_dns_error"] = str(e)

    # 2. Thử resolve IPv6
    try:
        ipv6_addrs = socket.getaddrinfo("smtp.gmail.com", 587, socket.AF_INET6, socket.SOCK_STREAM)
        results["ipv6_dns"] = [x[4][0] for x in ipv6_addrs]
    except Exception as e:
        results["ipv6_dns_error"] = str(e)

    # 3. Thử kết nối trực tiếp IPv4 socket port 587
    if "ipv4_dns" in results and results["ipv4_dns"]:
        target_ip = results["ipv4_dns"][0]
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, 587))
            banner = s.recv(1024).decode(errors="ignore")
            s.close()
            results["ipv4_connect_587"] = f"SUCCESS: {banner.strip()}"
        except Exception as e:
            results["ipv4_connect_587_error"] = str(e)

    # 4. Thử kết nối IPv4 socket port 465
    if "ipv4_dns" in results and results["ipv4_dns"]:
        target_ip = results["ipv4_dns"][0]
        try:
            import ssl
            ctx = ssl.create_default_context()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            ssl_sock = ctx.wrap_socket(s, server_hostname="smtp.gmail.com")
            ssl_sock.connect((target_ip, 465))
            banner = ssl_sock.recv(1024).decode(errors="ignore")
            ssl_sock.close()
            results["ipv4_connect_465"] = f"SUCCESS: {banner.strip()}"
        except Exception as e:
            results["ipv4_connect_465_error"] = str(e)

    return results
