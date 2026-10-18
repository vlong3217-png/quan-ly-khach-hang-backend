import io
import csv
from typing import Optional, List, Dict, Any

def get_lead_source_and_campaign_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    sources: List[Dict[str, Any]] = []
    campaigns: List[Dict[str, Any]] = []

    tot_leads = sum(s.get("total_leads", 0) for s in sources)
    tot_acc = sum(s.get("accepted_leads", 0) for s in sources)
    tot_conv = sum(s.get("converted_opportunities", 0) for s in sources)
    tot_rev = sum(s.get("closed_won_value", 0.0) for s in sources)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_leads": tot_leads,
        "overall_acceptance_rate": round((tot_acc / tot_leads) * 100, 2) if tot_leads else 0.0,
        "overall_conversion_rate": round((tot_conv / tot_leads) * 100, 2) if tot_leads else 0.0,
        "total_revenue_generated": tot_rev,
        "source_metrics": sources,
        "campaign_metrics": campaigns,
    }

def export_lead_effectiveness_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bytes:
    data = get_lead_source_and_campaign_report(start_date=start_date, end_date=end_date)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BÁO CÁO HIỆU QUẢ TỪNG NGUỒN LEAD VÀ CHIẾN DỊCH MARKETING", f"Khoảng thời gian: {start_date or 'Tất cả'} đến {end_date or 'Hiện tại'}"])
    writer.writerow([])
    writer.writerow(["1. HIỆU QUẢ THEO TỪNG NGUỒN LEAD"])
    writer.writerow(["Nguồn Lead", "Tổng số Lead", "Số Lead được nhận", "Tỷ lệ được nhận (%)", "Cơ hội chuyển đổi", "Tỷ lệ chuyển đổi (%)", "Doanh thu chốt (VND)"])
    for s in data.get("source_metrics", []):
        writer.writerow([
            s.get("source_name", ""),
            s.get("total_leads", 0),
            s.get("accepted_leads", 0),
            f"{s.get('acceptance_rate', 0.0)}%",
            s.get("converted_opportunities", 0),
            f"{s.get('conversion_rate', 0.0)}%",
            s.get("closed_won_value", 0.0),
        ])

    writer.writerow([])
    writer.writerow(["2. HIỆU QUẢ THEO CHIẾN DỊCH"])
    writer.writerow(["Mã CD", "Tên chiến dịch", "Kênh tiếp thị", "Tổng Lead", "Lead được nhận", "Tỷ lệ nhận (%)", "Cơ hội", "Tỷ lệ chuyển đổi (%)", "Doanh thu chốt (VND)"])
    for c in data.get("campaign_metrics", []):
        writer.writerow([
            c.get("campaign_id", ""),
            c.get("campaign_name", ""),
            c.get("channel", ""),
            c.get("total_leads", 0),
            c.get("accepted_leads", 0),
            f"{c.get('acceptance_rate', 0.0)}%",
            c.get("converted_opportunities", 0),
            f"{c.get('conversion_rate', 0.0)}%",
            c.get("closed_won_value", 0.0),
        ])

    return output.getvalue().encode("utf-8-sig")
