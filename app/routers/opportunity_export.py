from fastapi import APIRouter, Depends, Query, Response
from typing import Optional
from app.core.dependencies import get_current_user
from app.services import opportunity_export_service as export_service

router = APIRouter(prefix="/opportunities", tags=["Opportunities Export"])

@router.get("/export-excel")
def export_opportunities(
    stage: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    owner_id: Optional[int] = Query(None),
    campaign_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    include_custom_fields: bool = Query(True),
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {
        "id": getattr(current_user, "id", 1),
        "role": getattr(current_user, "role", "USER"),
    }
    excel_bytes = export_service.export_opportunities_excel(
        current_user=user_dict,
        stage=stage,
        customer_id=customer_id,
        owner_id=owner_id,
        campaign_id=campaign_id,
        search=search,
        include_custom_fields=include_custom_fields,
    )
    headers = {
        "Content-Disposition": "attachment; filename=danh_sach_co_hoi_ban_hang.csv",
        "Content-Type": "text/csv; charset=utf-8-sig",
    }
    return Response(content=excel_bytes, headers=headers)