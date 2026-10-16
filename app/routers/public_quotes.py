"""
Public Quotes API router (S7-06 AC 1, AC 2, AC 3, AC 4).
Allows customers to view quotes via a secure unique share token and submit decisions (ACCEPT / REJECT) with feedback.
Does not require internal authentication.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.quote import (
    PublicQuoteDetailResponse,
    PublicQuoteResponseRequest,
    PublicQuoteResponseResult,
)
from app.services.quote_service import (
    get_quote_by_share_token,
    customer_respond_quote,
)

router = APIRouter(
    prefix="/public/quotes",
    tags=["Public Quotes"],
)


@router.get("/{share_token}", response_model=PublicQuoteDetailResponse)
def get_public_quote(
    share_token: str,
    mark_viewed: bool = Query(True, description="Đánh dấu đã xem nếu chưa hết hạn"),
    db: Session = Depends(get_db),
):
    """
    Xem chi tiết báo giá công khai qua liên kết bảo mật (S7-06 AC 1 & AC 2):
    - Liên kết chỉ dùng cho đúng báo giá đó.
    - Đánh dấu thời điểm và số lần khách xem (viewed_at, view_count, chuyển status sang VIEWED).
    - Tự động kiểm tra hạn hiệu lực (chuyển sang EXPIRED nếu quá hạn).
    """
    return get_quote_by_share_token(share_token=share_token, mark_viewed=mark_viewed, db=db)


@router.post("/{share_token}/respond", response_model=PublicQuoteResponseResult)
def respond_public_quote(
    share_token: str,
    payload: PublicQuoteResponseRequest,
    db: Session = Depends(get_db),
):
    """
    Khách hàng phản hồi Chấp nhận hoặc Từ chối báo giá (S7-06 AC 2 & AC 3):
    - Bấm Chấp nhận (ACCEPT) hoặc Từ chối (REJECT).
    - Có ô ghi ý kiến phản hồi (customer_feedback).
    - Cập nhật tức thì trạng thái báo giá và ghi nhận vào dòng thời gian của Cơ hội.
    - Chặn phản hồi nếu báo giá đã hết hạn hiệu lực (EXPIRED).
    """
    return customer_respond_quote(
        share_token=share_token,
        action=payload.action.value,
        feedback=payload.customer_feedback,
        responder_name=payload.responder_name,
        db=db,
    )
