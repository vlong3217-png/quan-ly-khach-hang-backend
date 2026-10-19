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


