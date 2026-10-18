import io
import csv
from typing import Optional, List, Dict, Any

from app.models.opportunity import Opportunity
from app.services.opportunity_service import FAKE_OPPORTUNITIES

def get_forecast_progress_report(period_name: str = "2026-Q4") -> Dict[str, Any]:
    # Summary toan khoi
    summary = {
        "scope_type": "company",
        "scope_id": "ALL",
        "scope_name": "Toàn khối kinh doanh",
        "closed_won_amount": 0.0,
        "weighted_forecast_amount": 0.0,
        "quota_target_amount": 0.0,
        "progress_rate": 0.0,
        "forecast_rate": 0.0,
    }

    breakdown_team: List[Dict[str, Any]] = []
    breakdown_rep: List[Dict[str, Any]] = []
    loss_by_category: List[Dict[str, Any]] = []
    loss_by_competitor: List[Dict[str, Any]] = []

    return {
        "period_name": period_name,
        "summary": summary,
        "breakdown_by_team": breakdown_team,
        "breakdown_by_rep": breakdown_rep,
        "loss_analysis_by_category": loss_by_category,
        "loss_analysis_by_competitor": loss_by_competitor,
    }

def export_forecast_report_excel(period_name: str = "2026-Q4") -> bytes:
    data = get_forecast_progress_report(period_name)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BÁO CÁO DỰ BÁO DOANH SỐ VÀ TIẾN ĐỘ CHỈ TIÊU", f"Kỳ: {period_name}"])
    writer.writerow([])
    writer.writerow(["1. TỔNG HỢP TIẾN ĐỘ TOÀN KHỐI VÀ THEO NHÓM/NHÂN VIÊN"])
    writer.writerow(["Phân loại", "Đối tượng", "Doanh số đã chốt (VND)", "Dự báo trọng số (VND)", "Chỉ tiêu (VND)", "Tiến độ đã chốt (%)", "Tỷ lệ dự phóng (%)"])

    all_items = [data["summary"]] + data["breakdown_by_team"] + data["breakdown_by_rep"]
    for item in all_items:
        writer.writerow([
            item.get("scope_type", ""),
            item.get("scope_name", ""),
            item.get("closed_won_amount", 0.0),
            item.get("weighted_forecast_amount", 0.0),
            item.get("quota_target_amount", 0.0),
            f"{item.get('progress_rate', 0.0)}%",
            f"{item.get('forecast_rate', 0.0)}%",
        ])

    writer.writerow([])
    writer.writerow(["2. PHÂN TÍCH LÝ DO THUA THEO DANH MỤC"])
    writer.writerow(["Danh mục nguyên nhân", "Số cơ hội thua", "Tổng giá trị thua (VND)", "Tỷ trọng (%)"])
    for cat in data["loss_analysis_by_category"]:
        writer.writerow([cat.get("category", ""), cat.get("lost_count", 0), cat.get("lost_value", 0.0), f"{cat.get('percentage', 0.0)}%"])

    writer.writerow([])
    writer.writerow(["3. PHÂN TÍCH LÝ DO THUA THEO ĐỐI THỦ"])
    writer.writerow(["Tên đối thủ cạnh tranh", "Số cơ hội thua", "Tổng giá trị thua (VND)", "Tỷ trọng (%)"])
    for comp in data["loss_analysis_by_competitor"]:
        writer.writerow([comp.get("competitor", ""), comp.get("lost_count", 0), comp.get("lost_value", 0.0), f"{comp.get('percentage', 0.0)}%"])

    return output.getvalue().encode("utf-8-sig")
