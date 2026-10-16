import io
import csv
from typing import Optional, List, Dict, Any

def get_team_activity_and_sla_report(
    team_id: str = "TEAM_NORTH",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    members = [
        {
            "user_id": 1,
            "user_name": "Nguyễn Văn Admin",
            "team_id": team_id,
            "call_count": 48,
            "meeting_count": 16,
            "quote_count": 12,
            "total_activities": 76,
            "weekly_breakdown": [
                {"week_label": "Tuần 40", "call_count": 12, "meeting_count": 4, "quote_count": 3, "total": 19},
                {"week_label": "Tuần 41", "call_count": 14, "meeting_count": 5, "quote_count": 4, "total": 23},
                {"week_label": "Tuần 42", "call_count": 11, "meeting_count": 3, "quote_count": 2, "total": 16},
                {"week_label": "Tuần 43", "call_count": 11, "meeting_count": 4, "quote_count": 3, "total": 18},
            ],
            "total_leads_assigned": 25,
            "leads_responded_in_sla": 23,
            "sla_response_rate": 92.0,
        },
        {
            "user_id": 2,
            "user_name": "Trần Thị Manager",
            "team_id": team_id,
            "call_count": 36,
            "meeting_count": 20,
            "quote_count": 15,
            "total_activities": 71,
            "weekly_breakdown": [
                {"week_label": "Tuần 40", "call_count": 9, "meeting_count": 5, "quote_count": 4, "total": 18},
                {"week_label": "Tuần 41", "call_count": 10, "meeting_count": 6, "quote_count": 4, "total": 20},
                {"week_label": "Tuần 42", "call_count": 8, "meeting_count": 4, "quote_count": 3, "total": 15},
                {"week_label": "Tuần 43", "call_count": 9, "meeting_count": 5, "quote_count": 4, "total": 18},
            ],
            "total_leads_assigned": 20,
            "leads_responded_in_sla": 19,
            "sla_response_rate": 95.0,
        },
        {
            "user_id": 3,
            "user_name": "Lê Văn Sales",
            "team_id": team_id,
            "call_count": 25,
            "meeting_count": 8,
            "quote_count": 5,
            "total_activities": 38,
            "weekly_breakdown": [
                {"week_label": "Tuần 40", "call_count": 6, "meeting_count": 2, "quote_count": 1, "total": 9},
                {"week_label": "Tuần 41", "call_count": 7, "meeting_count": 2, "quote_count": 2, "total": 11},
                {"week_label": "Tuần 42", "call_count": 6, "meeting_count": 2, "quote_count": 1, "total": 9},
                {"week_label": "Tuần 43", "call_count": 6, "meeting_count": 2, "quote_count": 1, "total": 9},
            ],
            "total_leads_assigned": 22,
            "leads_responded_in_sla": 15,
            "sla_response_rate": 68.18, # Thành viên cần kèm cặp thêm do SLA và năng suất thấp
        },
    ]

    tot_calls = sum(m["call_count"] for m in members)
    tot_meets = sum(m["meeting_count"] for m in members)
    tot_quotes = sum(m["quote_count"] for m in members)
    tot_leads = sum(m["total_leads_assigned"] for m in members)
    tot_sla_resp = sum(m["leads_responded_in_sla"] for m in members)
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

    for m in data["members"]:
        writer.writerow([
            m["user_id"],
            m["user_name"],
            m["call_count"],
            m["meeting_count"],
            m["quote_count"],
            m["total_activities"],
            m["total_leads_assigned"],
            m["leads_responded_in_sla"],
            f"{m['sla_response_rate']}%",
        ])

    writer.writerow([])
    writer.writerow(["2. CHI TIẾT HOẠT ĐỘNG THEO TUẦN CỦA TỪNG THÀNH VIÊN"])
    writer.writerow(["Thành viên", "Tuần", "Cuộc gọi", "Cuộc gặp", "Báo giá gửi đi", "Tổng"])
    for m in data["members"]:
        for w in m["weekly_breakdown"]:
            writer.writerow([m["user_name"], w["week_label"], w["call_count"], w["meeting_count"], w["quote_count"], w["total"]])

    return output.getvalue().encode("utf-8-sig")