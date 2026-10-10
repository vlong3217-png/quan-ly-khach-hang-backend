"""S5-06: API dự báo doanh số theo trọng số xác suất."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.services import sales_forecast_service

router = APIRouter(prefix="/sales-forecast", tags=["Sales Forecast"])


@router.get("")
def get_sales_forecast(
    owner_id: Optional[int] = Query(None, description="Lọc theo nhân viên phụ trách"),
    team_id: Optional[int] = Query(None, description="Lọc theo nhóm"),
    reference_date: Optional[date] = Query(None, description="Ngày tham chiếu (mặc định hôm nay)"),
    current_user: dict = Depends(get_current_user),
):
    return sales_forecast_service.build_sales_forecast(
        current_user,
        owner_id=owner_id,
        team_id=team_id,
        reference_date=reference_date,
    )
