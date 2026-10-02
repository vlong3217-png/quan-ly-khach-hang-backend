from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from app.services.auth_service import (
    login_user,
    get_current_user,
    change_password,
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
