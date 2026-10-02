from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
)
from app.services.auth_service import login_user

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
            detail="T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"
        )

    result = login_user(
        identifier=identifier,
        password=request.password
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"
        )

    return {
        "success": True,
        "access_token": result["access_token"],
        "token_type": "bearer",
        "user": result["user"]
    }
