import io
import csv
from typing import Optional, List, Dict, Any

def get_lead_source_and_campaign_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    sources = [
        {
            "source_name": "Facebook Ads",
            "total_leads": 120,
            "accepted_leads": 102,
            "acceptance_rate": 85.0,
            "converted_opportunities": 34,
            "conversion_rate": 28.33,
            "closed_won_value": 450000000.0,
        },
        {
            "source_name": "Google Search / SEO",
            "total_leads": 95,
            "accepted_leads": 88,
            "acceptance_rate": 92.63,
            "converted_opportunities": 38,
            "conversion_rate": 40.0,
            "closed_won_value": 680000000.0, # Nguồn chất lượng cao nhất
        },
        {
            "source_name": "Hội thảo / Triển lãm",
            "total_leads": 60,
            "accepted_leads": 54,
            "acceptance_rate": 90.0,
            "converted_opportunities": 22,
            "conversion_rate": 36.67,
            "closed_won_value": 390000000.0,
        },
        {
            "source_name": "Giới thiệu (Referral)",
            "total_leads": 40,
            "accepted_leads": 39,
            "acceptance_rate": 97.5,
            "converted_opportunities": 25,
            "conversion_rate": 62.5,
            "closed_won_value": 520000000.0,
        },
        {
            "source_name": "Cold Calling / Email",
            "total_leads": 80,
            "accepted_leads": 44,
            "acceptance_rate": 55.0,
            "converted_opportunities": 8,
            "conversion_rate": 10.0,
            "closed_won_value": 90000000.0,
        },
    ]

    campaigns = [
        {
            "campaign_id": 1,
            "campaign_name": "Chiến dịch Chuyển đổi số Doanh nghiệp 2026",
            "channel": "EVENT",
            "total_leads": 60,
            "accepted_leads": 54,
            "acceptance_rate": 90.0,
            "converted_opportunities": 22,
            "conversion_rate": 36.67,
            "closed_won_value": 390000000.0,
        },
        {
            "campaign_id": 2,
            "campaign_name": "Chương trình Khuyến mãi Mùa Thu 2026",
            "channel": "ONLINE",
            "total_leads": 150,
            "accepted_leads": 130,
            "acceptance_rate": 86.67,
            "converted_opportunities": 45,
            "conversion_rate": 30.0,
            "closed_won_value": 580000000.0,
        },
    ]

    tot_leads = sum(s["total_leads"] for s in sources)
    tot_acc = sum(s["accepted_leads"] for s in sources)
    tot_conv = sum(s["converted_opportunities"] for s in sources)
    tot_rev = sum(s["closed_won_value"] for s in sources)

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
    for s in data["source_metrics"]:
        writer.writerow([
            s["source_name"],
            s["total_leads"],
            s["accepted_leads"],
            f"{s['acceptance_rate']}%",
            s["converted_opportunities"],
            f"{s['conversion_rate']}%",
            s["closed_won_value"],
        ])

    writer.writerow([])
    writer.writerow(["2. HIỆU QUẢ THEO CHIẾN DỊCH"])
    writer.writerow(["Mã CD", "Tên chiến dịch", "Kênh tiếp thị", "Tổng Lead", "Lead được nhận", "Tỷ lệ nhận (%)", "Cơ hội", "Tỷ lệ chuyển đổi (%)", "Doanh thu chốt (VND)"])
    for c in data["campaign_metrics"]:
        writer.writerow([
            c["campaign_id"],
            c["campaign_name"],
            c["channel"],
            c["total_leads"],
            c["accepted_leads"],
            f"{c['acceptance_rate']}%",
            c["converted_opportunities"],
            f"{c['conversion_rate']}%",
            c["closed_won_value"],
        ])

    return output.getvalue().encode("utf-8-sig")