from fastapi import APIRouter, Depends, Query, Response
from app.core.dependencies import get_current_user
from app.schemas.sales_forecast_report import ForecastReportResponse
from app.services import sales_forecast_report_service as service

router = APIRouter(prefix="/sales-forecast-report", tags=["Sales Forecast & Progress Report"])

@router.get("", response_model=ForecastReportResponse)
def get_report(
    period_name: str = Query("2026-Q4"),
    current_user=Depends(get_current_user),
):
    return service.get_forecast_progress_report(period_name=period_name)

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