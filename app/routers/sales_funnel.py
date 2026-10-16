from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.dependencies import get_current_user
from app.schemas.sales_funnel import SalesFunnelResponse
from app.services import sales_funnel_service as service

router = APIRouter(prefix="/sales-funnel", tags=["Sales Funnel & Conversion"])

@router.get("", response_model=SalesFunnelResponse)
def get_funnel_report(
    team_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    return service.get_sales_funnel_and_conversion_report(
        team_id=team_id,
        user_id=user_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
    )