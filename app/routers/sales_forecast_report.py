from fastapi import APIRouter, Depends, Query, Response
from app.core.dependencies import get_current_user
from app.schemas.sales_forecast_report import ForecastReportResponse
from app.services import sales_forecast_report_service as service

router = APIRouter(prefix="/sales-forecast-report", tags=["Sales Forecast & Progress Report"])

@router.get("", response_model=ForecastReportResponse)
def get_report(
    period_name: str = Query("2026-Q4"),
    page: Optional[int] = Query(None, ge=1, description="Trang danh sách nhân viên"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng nhân viên mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    data = service.get_forecast_progress_report(period_name=period_name)
    reps = data.get("breakdown_by_rep", [])
    total_reps = len(reps)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(total_reps / effective_limit)) if total_reps > 0 else 1

    paged_reps = reps[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    data["breakdown_by_rep"] = paged_reps
    data["page"] = effective_page
    data["limit"] = effective_limit
    data["total_pages"] = total_pages
    data["total_reps"] = total_reps
    return data

@router.get("/export-excel")
def export_excel(
    period_name: str = Query("2026-Q4"),
    current_user=Depends(get_current_user),
):
    excel_bytes = service.export_forecast_report_excel(period_name=period_name)
    headers = {
        "Content-Disposition": f"attachment; filename=bao_cao_du_bao_doanh_so_{period_name}.csv",
        "Content-Type": "text/csv; charset=utf-8-sig",
    }
    return Response(content=excel_bytes, headers=headers)