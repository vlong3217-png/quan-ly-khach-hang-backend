"""
Campaign API Router for S4-03:
- Declare campaigns with budget, running time, channel
- Campaign metrics: total leads, total opportunities, closed-won value, ROI
- Overall summary report
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignMetricsResponse,
    CampaignResponse,
    CampaignSummaryReportResponse,
    CampaignUpdate,
)
from app.schemas.lead import LeadResponse
from app.services import campaign_service

router = APIRouter(
    prefix="/campaigns",
    tags=["Campaigns"],
)


@router.get("", response_model=CampaignListResponse)
def get_campaigns_list(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: PLANNING, ACTIVE, COMPLETED, PAUSED, CANCELLED"),
    channel: Optional[str] = Query(None, description="Lọc theo kênh: EVENT, WORKSHOP, FACEBOOK_ADS, GOOGLE_ADS..."),
    search: Optional[str] = Query(None, description="Tìm theo tên, mã hoặc mô tả"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng chiến dịch mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    """AC S4-03: Xem danh sách chiến dịch tiếp thị."""
    import math

    all_campaigns = campaign_service.list_campaigns(
        status_filter=status,
        channel_filter=channel,
        search=search,
    )
    total = len(all_campaigns)

    effective_limit = limit if limit is not None else 20
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_campaigns[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "total": total,
        "campaigns": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_new_campaign(
    payload: CampaignCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-03: Khai báo chiến dịch với ngân sách, thời gian chạy, kênh.
    """
    new_camp = campaign_service.create_campaign(payload.model_dump(), current_user)
    return new_camp


@router.get("/metrics/summary", response_model=CampaignSummaryReportResponse)
def get_all_campaigns_summary(
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-03: Báo cáo tổng thể hiệu quả tất cả chiến dịch: tổng ngân sách, chi phí, leads, opps, doanh thu đã chốt, ROI trung bình.
    """
    return campaign_service.get_campaigns_summary_report()


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_detail(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem thông tin chi tiết một chiến dịch."""
    camp = campaign_service.get_campaign_by_id(campaign_id)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy chiến dịch ID {campaign_id}",
        )
    return camp


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign_info(
    campaign_id: int,
    payload: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật chiến dịch."""
    updated = campaign_service.update_campaign(campaign_id, payload.model_dump(exclude_unset=True), current_user)
    return updated


@router.delete("/{campaign_id}")
def delete_campaign_api(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xóa chiến dịch."""
    success = campaign_service.delete_campaign(campaign_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy chiến dịch ID {campaign_id} để xóa",
        )
    return {"message": f"Đã xóa thành công chiến dịch ID {campaign_id}"}


@router.get("/{campaign_id}/metrics", response_model=CampaignMetricsResponse)
def get_single_campaign_metrics(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-03: Xem được số lead, số cơ hội và giá trị đã chốt của từng chiến dịch.
    Đo lường chính xác hiệu quả doanh thu và ROI so với ngân sách bỏ ra.
    """
    return campaign_service.get_campaign_metrics(campaign_id)


@router.get("/{campaign_id}/leads", response_model=List[LeadResponse])
def get_campaign_leads_endpoint(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-03: Xem danh sách lead sinh ra từ chiến dịch.
    """
    camp = campaign_service.get_campaign_by_id(campaign_id)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy chiến dịch ID {campaign_id}",
        )
    return campaign_service.get_campaign_leads(campaign_id)
