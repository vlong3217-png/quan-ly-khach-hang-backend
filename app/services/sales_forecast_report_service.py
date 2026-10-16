import io
import csv
from typing import Optional, List, Dict, Any

from app.models.opportunity import Opportunity
from app.services.opportunity_service import FAKE_OPPORTUNITIES

def get_forecast_progress_report(period_name: str = "2026-Q4") -> Dict[str, Any]:
    # 1. Summary toàn khối
    summary = {
        "scope_type": "company",
        "scope_id": "ALL",
        "scope_name": "Toàn khối kinh doanh",
        "closed_won_amount": 1200000000.0,
        "weighted_forecast_amount": 750000000.0,
        "quota_target_amount": 2000000000.0,
        "progress_rate": 60.0,
        "forecast_rate": 97.5,
    }

    # 2. Breakdown theo nhóm
    breakdown_team = [
        {
            "scope_type": "team",
            "scope_id": "TEAM_NORTH",
            "scope_name": "Nhóm Kinh Doanh Miền Bắc",
            "closed_won_amount": 700000000.0,
            "weighted_forecast_amount": 450000000.0,
            "quota_target_amount": 1100000000.0,
            "progress_rate": 63.64,
            "forecast_rate": 104.55,
        },
        {
            "scope_type": "team",
            "scope_id": "TEAM_SOUTH",
            "scope_name": "Nhóm Kinh Doanh Miền Nam",
            "closed_won_amount": 500000000.0,
            "weighted_forecast_amount": 300000000.0,
            "quota_target_amount": 900000000.0,
            "progress_rate": 55.56,
            "forecast_rate": 88.89,
        },
    ]

    # 3. Breakdown theo nhân viên
    breakdown_rep = [
        {
            "scope_type": "user",
            "scope_id": "1",
            "scope_name": "Nguyễn Văn Admin",
            "closed_won_amount": 500000000.0,
            "weighted_forecast_amount": 250000000.0,
            "quota_target_amount": 700000000.0,
            "progress_rate": 71.43,
            "forecast_rate": 107.14,
        },
        {
            "scope_type": "user",
            "scope_id": "2",
            "scope_name": "Trần Thị Manager",
            "closed_won_amount": 400000000.0,
            "weighted_forecast_amount": 280000000.0,
            "quota_target_amount": 650000000.0,
            "progress_rate": 61.54,
            "forecast_rate": 104.62,
        },
        {
            "scope_type": "user",
            "scope_id": "3",
            "scope_name": "Lê Văn Sales",
            "closed_won_amount": 300000000.0,
            "weighted_forecast_amount": 220000000.0,
            "quota_target_amount": 650000000.0,
            "progress_rate": 46.15,
            "forecast_rate": 80.0,
        },
    ]

    # 4. Phân tích lý do thua theo danh mục
    loss_by_category = [
        {"category": "Giá cao hơn đối thủ", "competitor": None, "lost_count": 8, "lost_value": 320000000.0, "percentage": 42.11},
        {"category": "Thiếu tính năng chuyên sâu", "competitor": None, "lost_count": 5, "lost_value": 240000000.0, "percentage": 31.58},
        {"category": "Chậm tiến độ triển khai cam kết", "competitor": None, "lost_count": 3, "lost_value": 120000000.0, "percentage": 15.79},
        {"category": "Khách hàng hoãn ngân sách", "competitor": None, "lost_count": 2, "lost_value": 80000000.0, "percentage": 10.53},
    ]

    # 5. Phân tích lý do thua theo đối thủ
    loss_by_competitor = [
        {"category": "Đối thủ cạnh tranh", "competitor": "Đối thủ Alpha Corp", "lost_count": 7, "lost_value": 350000000.0, "percentage": 46.05},
        {"category": "Đối thủ cạnh tranh", "competitor": "Đối thủ Beta Solutions", "lost_count": 6, "lost_value": 260000000.0, "percentage": 34.21},
        {"category": "Đối thủ cạnh tranh", "competitor": "Đối thủ Gamma Global", "lost_count": 3, "lost_value": 150000000.0, "percentage": 19.74},
    ]

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
            item["scope_type"],
            item["scope_name"],
            item["closed_won_amount"],
            item["weighted_forecast_amount"],
            item["quota_target_amount"],
            f"{item['progress_rate']}%",
            f"{item['forecast_rate']}%",
        ])

    writer.writerow([])
    writer.writerow(["2. PHÂN TÍCH LÝ DO THUA THEO DANH MỤC"])
    writer.writerow(["Danh mục nguyên nhân", "Số cơ hội thua", "Tổng giá trị thua (VND)", "Tỷ trọng (%)"])
    for cat in data["loss_analysis_by_category"]:
        writer.writerow([cat["category"], cat["lost_count"], cat["lost_value"], f"{cat['percentage']}%"])

    writer.writerow([])
    writer.writerow(["3. PHÂN TÍCH LÝ DO THUA THEO ĐỐI THỦ"])
    writer.writerow(["Tên đối thủ cạnh tranh", "Số cơ hội thua", "Tổng giá trị thua (VND)", "Tỷ trọng (%)"])
    for comp in data["loss_analysis_by_competitor"]:
        writer.writerow([comp["competitor"], comp["lost_count"], comp["lost_value"], f"{comp['percentage']}%"])

    return output.getvalue().encode("utf-8-sig")