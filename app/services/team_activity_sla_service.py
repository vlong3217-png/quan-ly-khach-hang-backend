import io
import csv
from typing import Optional, List, Dict, Any

def get_team_activity_and_sla_report(
    team_id: str = "TEAM_NORTH",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    members: List[Dict[str, Any]] = []

    tot_calls = sum(m.get("call_count", 0) for m in members)
    tot_meets = sum(m.get("meeting_count", 0) for m in members)
    tot_quotes = sum(m.get("quote_count", 0) for m in members)
    tot_leads = sum(m.get("total_leads_assigned", 0) for m in members)
    tot_sla_resp = sum(m.get("leads_responded_in_sla", 0) for m in members)
    overall_sla = round((tot_sla_resp / tot_leads) * 100, 2) if tot_leads else 0.0

    return {
        "team_id": team_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_calls": tot_calls,
        "total_meetings": tot_meets,
        "total_quotes_sent": tot_quotes,
        "overall_sla_rate": overall_sla,
        "members": members,
    }

def export_team_activity_sla_excel(team_id: str = "TEAM_NORTH") -> bytes:
    data = get_team_activity_and_sla_report(team_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BÁO CÁO HOẠT ĐỘNG VÀ NĂNG SUẤT NHÓM KINH DOANH", f"Nhóm: {team_id}"])
    writer.writerow([])
    writer.writerow(["1. TỔNG HỢP NĂNG SUẤT THÀNH VIÊN VÀ ĐÁP ỨNG SLA"])
    writer.writerow([
        "Mã NV", "Họ tên", "Số cuộc gọi", "Số cuộc gặp", "Số báo giá gửi đi", 
        "Tổng hoạt động", "Lead được giao", "Lead phản hồi đúng SLA", "Tỷ lệ đáp ứng SLA (%)"
    ])

    for m in data.get("members", []):
        writer.writerow([
            m.get("user_id"),
            m.get("user_name"),
            m.get("call_count", 0),
            m.get("meeting_count", 0),
            m.get("quote_count", 0),
            m.get("total_activities", 0),
            m.get("total_leads_assigned", 0),
            m.get("leads_responded_in_sla", 0),
            f"{m.get('sla_response_rate', 0.0)}%",
        ])

    writer.writerow([])
    writer.writerow(["2. CHI TIẾT HOẠT ĐỘNG THEO TUẦN CỦA TỪNG THÀNH VIÊN"])
    writer.writerow(["Thành viên", "Tuần", "Cuộc gọi", "Cuộc gặp", "Báo giá gửi đi", "Tổng"])
    for m in data.get("members", []):
        for w in m.get("weekly_breakdown", []):
            writer.writerow([m.get("user_name"), w.get("week_label"), w.get("call_count", 0), w.get("meeting_count", 0), w.get("quote_count", 0), w.get("total", 0)])

    return output.getvalue().encode("utf-8-sig")
