import io
import csv
from typing import Optional, List, Dict, Any
from app.services.opportunity_service import FAKE_OPPORTUNITIES

PRIVILEGED_ROLES = ["ADMIN", "DIRECTOR", "MANAGER", "LEADER", "FINANCE"]

def export_opportunities_excel(
    current_user: Dict[str, Any],
    stage: Optional[str] = None,
    customer_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    search: Optional[str] = None,
    include_custom_fields: bool = True,
) -> bytes:
    role = (current_user.get("role") or "USER").upper()
    can_view_margins = role in PRIVILEGED_ROLES

    # Lọc theo bộ lọc áp dụng
    filtered = list(FAKE_OPPORTUNITIES)
    if stage:
        filtered = [o for o in filtered if o.get("stage") == stage]
    if customer_id:
        filtered = [o for o in filtered if o.get("customer_id") == customer_id]
    if owner_id:
        filtered = [o for o in filtered if o.get("owner_id") == owner_id]
    if campaign_id:
        filtered = [o for o in filtered if o.get("campaign_id") == campaign_id]
    if search:
        s_low = search.lower()
        filtered = [o for o in filtered if s_low in str(o.get("title", "")).lower() or s_low in str(o.get("description", "")).lower()]

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "ID",
        "Tiêu đề cơ hội",
        "Giai đoạn (Stage)",
        "Giá trị cơ hội (VND)",
        "Xác suất (%)",
        "Ngày dự kiến đóng",
        "Mã khách hàng",
        "Người phụ trách ID",
    ]

    # Phân quyền: Chỉ cấp quản lý/giám đốc/tài chính mới thấy Giá vốn và Biên lợi nhuận
    if can_view_margins:
        headers.extend(["Giá vốn (COGS)", "Lợi nhuận gộp (Gross Profit)", "Biên lợi nhuận (%)"])

    # Bao gồm cả trường tuỳ chỉnh (Custom fields)
    if include_custom_fields:
        headers.extend(["Lĩnh vực kinh doanh", "Mức độ ưu tiên", "Kênh tiếp cận"])

    writer.writerow(headers)

    for o in filtered:
        val = float(o.get("value") or 0.0)
        cost = round(val * 0.65, 2)
        profit = round(val - cost, 2)
        margin_pct = round((profit / val) * 100, 2) if val > 0 else 0.0

        row = [
            o.get("id"),
            o.get("title"),
            o.get("stage"),
            val,
            o.get("probability", 50),
            o.get("expected_closing_date", "2026-11-30"),
            o.get("customer_id"),
            o.get("owner_id"),
        ]

        if can_view_margins:
            row.extend([cost, profit, f"{margin_pct}%"])

        if include_custom_fields:
            # Custom fields mô phỏng
            custom_data = o.get("custom_fields") or {}
            industry = custom_data.get("industry") or "Công nghệ & Phần mềm"
            priority = custom_data.get("priority") or "Cao"
            channel = custom_data.get("channel") or "Đối tác phân phối"
            row.extend([industry, priority, channel])

        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")