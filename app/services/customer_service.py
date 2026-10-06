"""
Customer service with enterprise customer data, duplicate tax code validation and data scope filtering (S3-01).
"""

import copy
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status

from app.core.dependencies import DataScope
from app.services import auth_service

INITIAL_CUSTOMERS = [
    {
        "id": 1,
        "name": "Công ty Cổ phần Công nghệ ABC",
        "tax_code": "0101234567",
        "industry": "Công nghệ thông tin",
        "company_size": "100 - 500 nhân sự",
        "website": "https://abc-tech.vn",
        "address": "Tầng 5, Tòa nhà Keangnam, Cầu Giấy, Hà Nội",
        "status": "CUSTOMER",
        "email": "contact@abc-tech.vn",
        "phone": "02431234567",
        "company": "Công ty Cổ phần Công nghệ ABC",
        "owner_id": 1,   # Owned by Admin (User 1)
        "team_id": 1,     # Team A
        "created_at": datetime(2026, 1, 10, 8, 30, 0),
    },
    {
        "id": 2,
        "name": "Công ty TNHH Giải pháp Phần mềm XYZ",
        "tax_code": "0309876543",
        "industry": "Tài chính - Ngân hàng",
        "company_size": "50 - 100 nhân sự",
        "website": "https://xyz-solutions.com",
        "address": "Quận 1, TP. Hồ Chí Minh",
        "status": "IN_TRANSACTION",
        "email": "sales@xyz-solutions.com",
        "phone": "02839876543",
        "company": "Công ty TNHH Giải pháp Phần mềm XYZ",
        "owner_id": 2,   # Owned by Manager (User 2, Team A)
        "team_id": 1,     # Team A
        "created_at": datetime(2026, 2, 1, 9, 0, 0),
    },
    {
        "id": 3,
        "name": "Công ty Tập đoàn Xây dựng DEF",
        "tax_code": "0104567890",
        "industry": "Bất động sản & Xây dựng",
        "company_size": "Trên 500 nhân sự",
        "website": "https://defgroup.vn",
        "address": "Hai Bà Trưng, Hà Nội",
        "status": "PROSPECT",
        "email": "info@defgroup.vn",
        "phone": "02434567890",
        "company": "Công ty Tập đoàn Xây dựng DEF",
        "owner_id": 3,   # Owned by User 1 (User 3, Team A)
        "team_id": 1,     # Team A
        "created_at": datetime(2026, 2, 15, 10, 15, 0),
    },
    {
        "id": 4,
        "name": "Công ty Cổ phần Bán lẻ GHI",
        "tax_code": "0305678901",
        "industry": "Bán lẻ & Tiêu dùng",
        "company_size": "100 - 500 nhân sự",
        "website": "https://ghi-retail.com",
        "address": "Bình Thạnh, TP. Hồ Chí Minh",
        "status": "PROSPECT",
        "email": "support@ghi-retail.com",
        "phone": "02835678901",
        "company": "Công ty Cổ phần Bán lẻ GHI",
        "owner_id": 4,   # Owned by User 2 (User 4, Team B)
        "team_id": 2,     # Team B
        "created_at": datetime(2026, 3, 1, 14, 0, 0),
    },
    {
        "id": 5,
        "name": "Công ty Nông nghiệp Sạch JKL",
        "tax_code": None,  # Có thể chưa có MST
        "industry": "Nông nghiệp",
        "company_size": "Dưới 50 nhân sự",
        "website": None,
        "address": "Đà Lạt, Lâm Đồng",
        "status": "DISCONTINUED",
        "email": "jkl-farm@example.com",
        "phone": "02633890123",
        "company": "Công ty Nông nghiệp Sạch JKL",
        "owner_id": 4,   # Owned by User 2 (User 4, Team B)
        "team_id": 2,     # Team B
        "created_at": datetime(2026, 3, 5, 16, 20, 0),
    },
]

FAKE_CUSTOMERS = copy.deepcopy(INITIAL_CUSTOMERS)


def reset_fake_customers() -> None:
    """Reset customer data back to initial state (useful for tests)."""
    global FAKE_CUSTOMERS
    FAKE_CUSTOMERS = copy.deepcopy(INITIAL_CUSTOMERS)


def _enrich_customer_names(customer: dict) -> dict:
    """Bổ sung owner_name, team_name và parent_company_name cho customer response."""
    c = copy.deepcopy(customer)
    owner = auth_service.get_user_by_id(c.get("owner_id"))
    c["owner_name"] = owner["full_name"] if owner else None

    team = auth_service.get_team_by_id(c.get("team_id"))
    c["team_name"] = team["name"] if team else None

    parent_id = c.get("parent_company_id")
    if parent_id:
        parent = next((p for p in FAKE_CUSTOMERS if p["id"] == parent_id), None)
        c["parent_company_name"] = parent["name"] if parent else None
    else:
        c["parent_company_name"] = None

    return c



def get_raw_customer_by_id(customer_id: int) -> Optional[dict]:
    """Find a customer by ID without scope filter (returns raw dict or None)."""
    for c in FAKE_CUSTOMERS:
        if c["id"] == customer_id:
            return _enrich_customer_names(c)
    return None


get_customer_by_id = get_raw_customer_by_id



def get_customers_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    status_filter: Optional[str] = None,
    industry_filter: Optional[str] = None,
    company_size_filter: Optional[str] = None,
    address_filter: Optional[str] = None,
    owner_id_filter: Optional[int] = None,
) -> tuple[int, list[dict]]:
    """
    AC S3-01 & S3-07:
    - Nhân viên (USER) chỉ thấy khách hàng mình sở hữu (owner_id == user_id).
    - Trưởng nhóm (MANAGER) thấy toàn bộ khách hàng của nhóm (team_id == user_team_id).
    - Quản trị viên (ADMIN) thấy tất cả.
    - Tìm kiếm và lọc đa điều kiện: ngành nghề, quy mô, địa chỉ/khu vực, người phụ trách, trạng thái.
    """
    if scope == DataScope.ALL:
        results = list(FAKE_CUSTOMERS)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            results = list(FAKE_CUSTOMERS)
        else:
            results = [c for c in FAKE_CUSTOMERS if c.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        results = [c for c in FAKE_CUSTOMERS if c.get("owner_id") == user_id]

    if status_filter:
        sf = status_filter.strip().upper()
        results = [c for c in results if str(c.get("status", "")).upper() == sf]

    if industry_filter:
        ind = industry_filter.strip().lower()
        results = [c for c in results if ind in str(c.get("industry") or "").lower()]

    if company_size_filter:
        cs = company_size_filter.strip().lower()
        results = [c for c in results if cs in str(c.get("company_size") or "").lower()]

    if address_filter:
        addr = address_filter.strip().lower()
        results = [c for c in results if addr in str(c.get("address") or "").lower()]

    if owner_id_filter is not None:
        results = [c for c in results if c.get("owner_id") == owner_id_filter]

    if search:
        s = search.lower().strip()
        results = [
            c for c in results
            if s in c.get("name", "").lower()
            or s in (c.get("tax_code") or "").lower()
            or s in (c.get("email") or "").lower()
            or s in (c.get("company") or "").lower()
            or s in (c.get("phone") or "").lower()
            or s in (c.get("industry") or "").lower()
        ]

    total = len(results)


    # Áp dụng phân trang nếu có skip / limit
    if skip is not None and limit is not None:
        paged_results = results[skip : skip + limit]
    elif limit is not None:
        paged_results = results[:limit]
    elif skip is not None:
        paged_results = results[skip:]
    else:
        paged_results = results

    enriched_paged = [_enrich_customer_names(c) for c in paged_results]
    return total, enriched_paged


def validate_tax_code_uniqueness(tax_code: Optional[str], exclude_id: Optional[int] = None) -> None:
    """AC S3-01: Mã số thuế nếu có thì phải là duy nhất."""
    if not tax_code or not tax_code.strip():
        return
    clean_tax = tax_code.strip()
    for c in FAKE_CUSTOMERS:
        if exclude_id and c["id"] == exclude_id:
            continue
        if c.get("tax_code") and c["tax_code"].strip().lower() == clean_tax.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã số thuế '{clean_tax}' đã tồn tại cho khách hàng '{c['name']}'",
            )


def create_customer_record(data: dict, current_user: dict) -> dict:
    """
    AC S3-01: Khai báo tên công ty, mã số thuế, ngành nghề, quy mô, website, địa chỉ, người sở hữu.
    """
    tax_code = data.get("tax_code")
    validate_tax_code_uniqueness(tax_code)

    # Xác định người sở hữu (owner_id)
    owner_id = data.get("owner_id")
    if owner_id is not None:
        owner_user = auth_service.get_user_by_id(owner_id)
        if not owner_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Người sở hữu với ID {owner_id} không tồn tại",
            )
        team_id = data.get("team_id") or owner_user.get("team_id")
    else:
        owner_id = current_user["id"]
        team_id = data.get("team_id") or current_user.get("team_id")

    new_id = (max(c["id"] for c in FAKE_CUSTOMERS) + 1) if FAKE_CUSTOMERS else 1
    new_customer = {
        "id": new_id,
        "name": data["name"].strip(),
        "tax_code": tax_code.strip() if tax_code else None,
        "industry": data.get("industry"),
        "company_size": data.get("company_size"),
        "website": data.get("website"),
        "address": data.get("address"),
        "status": data.get("status", "PROSPECT"),
        "parent_company_id": data.get("parent_company_id"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "company": data.get("company") or data["name"].strip(),
        "owner_id": owner_id,
        "team_id": team_id,
        "created_at": datetime.utcnow(),
    }
    FAKE_CUSTOMERS.append(new_customer)
    return _enrich_customer_names(new_customer)


def update_customer_record(
    customer_id: int,
    data: dict,
) -> Optional[dict]:
    """Cập nhật thông tin khách hàng kèm kiểm tra trùng MST."""
    customer = None
    for c in FAKE_CUSTOMERS:
        if c["id"] == customer_id:
            customer = c
            break
    if customer is None:
        return None

    if "tax_code" in data and data["tax_code"] is not None:
        validate_tax_code_uniqueness(data["tax_code"], exclude_id=customer_id)

    if "owner_id" in data and data["owner_id"] is not None:
        owner_user = auth_service.get_user_by_id(data["owner_id"])
        if not owner_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Người sở hữu với ID {data['owner_id']} không tồn tại",
            )

    for key, value in data.items():
        if value is not None and key != "id":
            customer[key] = value

    return _enrich_customer_names(customer)


def delete_customer_record(customer_id: int) -> bool:
    """Delete a customer by ID."""
    global FAKE_CUSTOMERS
    initial_len = len(FAKE_CUSTOMERS)
    FAKE_CUSTOMERS = [c for c in FAKE_CUSTOMERS if c["id"] != customer_id]
    return len(FAKE_CUSTOMERS) < initial_len


CUSTOMER_ATTACHMENTS: List[dict] = [
    {
        "id": 1,
        "customer_id": 1,
        "filename": "hop_dong_nguyen_tac_2026.pdf",
        "file_url": "/uploads/documents/hop_dong_nguyen_tac_2026.pdf",
        "file_size_bytes": 1048576,
        "uploaded_by": "admin",
        "created_at": datetime(2026, 1, 15, 10, 0, 0),
    },
    {
        "id": 2,
        "customer_id": 1,
        "filename": "giay_phep_kinh_doanh.pdf",
        "file_url": "/uploads/documents/giay_phep_kinh_doanh.pdf",
        "file_size_bytes": 524288,
        "uploaded_by": "admin",
        "created_at": datetime(2026, 1, 10, 8, 45, 0),
    },
]


def add_customer_attachment(customer_id: int, filename: str, file_url: str, file_size_bytes: int, uploaded_by: str) -> dict:
    new_id = max([a["id"] for a in CUSTOMER_ATTACHMENTS], default=0) + 1
    item = {
        "id": new_id,
        "customer_id": customer_id,
        "filename": filename,
        "file_url": file_url,
        "file_size_bytes": file_size_bytes,
        "uploaded_by": uploaded_by,
        "created_at": datetime.now(),
    }
    CUSTOMER_ATTACHMENTS.append(item)
    return item


def get_customer_360(customer_id: int) -> Optional[dict]:
    """Tổng hợp Customer 360 View toàn diện."""
    customer = get_customer_by_id(customer_id)
    if not customer:
        return None

    # 1. Contacts
    from app.services import contact_service
    contacts = contact_service.list_contacts(customer_id=customer_id)

    # 2. Opportunities (Open vs Won/Lost)
    from app.services import opportunity_service
    all_opps = opportunity_service.FAKE_OPPORTUNITIES
    cust_opps = [o for o in all_opps if o.get("customer_id") == customer_id]
    
    open_stages = ["PROSPECTING", "QUALIFICATION", "PROPOSAL", "NEGOTIATION"]
    closed_stages = ["CLOSED_WON", "CLOSED_LOST"]

    open_opps = [o for o in cust_opps if o.get("stage") in open_stages]
    closed_opps = [o for o in cust_opps if o.get("stage") in closed_stages]

    total_won_value = sum(float(o.get("value", 0)) for o in closed_opps if o.get("stage") == "CLOSED_WON")
    total_open_value = sum(float(o.get("value", 0)) for o in open_opps)

    # 3. Activities timeline
    from app.services import activity_service
    all_activities = activity_service.FAKE_ACTIVITIES
    cust_activities = [a for a in all_activities if a.get("customer_id") == customer_id]
    # Sắp xếp timeline theo id giảm dần
    cust_activities.sort(key=lambda x: x.get("id", 0), reverse=True)

    # 4. Attachments
    attachments = [a for a in CUSTOMER_ATTACHMENTS if a.get("customer_id") == customer_id]

    return {
        "customer": customer,
        "contacts": contacts,
        "open_opportunities": open_opps,
        "closed_opportunities": closed_opps,
        "activities_timeline": cust_activities,
        "attachments": attachments,
        "total_won_value": total_won_value,
        "total_open_value": total_open_value,
        "churn_risk": False,
    }


def _normalize_str(s: Optional[str]) -> str:
    if not s:
        return ""
    import re
    # Lowercase and remove punctuation/extra spaces
    s = s.lower().strip()
    s = re.sub(r"[,\.\-_/\\]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def find_duplicate_customers(customer_id: int) -> List[dict]:
    """
    AC S3-04: Phát hiện trùng dựa trên:
    - Trùng Mã số thuế (tax_code)
    - Tên doanh nghiệp tương tự (chứa nhau hoặc độ tương đồng cao)
    - Trùng website (domain) hoặc email/phone
    """
    target = get_customer_by_id(customer_id)
    if not target:
        return []

    duplicates = []
    target_name_norm = _normalize_str(target.get("name"))
    target_tax = target.get("tax_code")
    target_website = _normalize_str(target.get("website"))
    target_phone = target.get("phone")

    for c in FAKE_CUSTOMERS:
        if c["id"] == customer_id:
            continue

        reasons = []
        score = 0.0

        # 1. Tax code match (100% confidence)
        if target_tax and c.get("tax_code") and target_tax == c.get("tax_code"):
            reasons.append(f"Trùng mã số thuế: {target_tax}")
            score = max(score, 1.0)

        # 2. Website match
        c_web = _normalize_str(c.get("website"))
        if target_website and c_web and (target_website in c_web or c_web in target_website):
            reasons.append(f"Trùng hoặc tương đồng website: {c.get('website')}")
            score = max(score, 0.9)

        # 3. Phone match
        if target_phone and c.get("phone") and target_phone == c.get("phone"):
            reasons.append(f"Trùng số điện thoại: {target_phone}")
            score = max(score, 0.85)

        # 4. Name similarity
        c_name_norm = _normalize_str(c.get("name"))
        if target_name_norm and c_name_norm:
            # Check if name contains each other (e.g. 'công ty cổ phần abc' and 'công ty abc')
            words_target = set(target_name_norm.split())
            words_c = set(c_name_norm.split())
            common_words = words_target.intersection(words_c)
            total_words = words_target.union(words_c)
            jaccard = len(common_words) / len(total_words) if total_words else 0

            if jaccard >= 0.5 or (target_name_norm in c_name_norm) or (c_name_norm in target_name_norm):
                reasons.append(f"Tên doanh nghiệp tương tự ({int(jaccard * 100)}% từ khóa trùng khớp)")
                score = max(score, min(0.95, round(jaccard, 2)))

        if reasons:
            duplicates.append({
                "customer": _enrich_customer_names(c),
                "match_reasons": reasons,
                "confidence_score": score,
            })

    # Sắp xếp confidence_score giảm dần
    duplicates.sort(key=lambda x: x["confidence_score"], reverse=True)
    return duplicates


def merge_customers(
    primary_id: int,
    secondary_id: int,
    chosen_fields: Optional[dict] = None,
    current_user_username: str = "manager",
) -> dict:
    """
    AC S3-04: Gộp hai khách hàng:
    - Giữ lại hồ sơ chính (primary_id).
    - Chuyển toàn bộ contacts, opportunities, activities từ secondary sang primary.
    - Cập nhật các trường thông tin được chọn (chosen_fields).
    - Xóa hoặc vô hiệu hóa hồ sơ phụ (secondary_id).
    """
    if primary_id == secondary_id:
        raise ValueError("Hồ sơ chính và hồ sơ phụ không thể trùng nhau")

    primary = None
    secondary = None
    for c in FAKE_CUSTOMERS:
        if c["id"] == primary_id:
            primary = c
        elif c["id"] == secondary_id:
            secondary = c

    if not primary:
        raise ValueError(f"Không tìm thấy hồ sơ chính ID #{primary_id}")
    if not secondary:
        raise ValueError(f"Không tìm thấy hồ sơ phụ ID #{secondary_id}")

    # 1. Cập nhật các trường được chọn vào primary
    if chosen_fields:
        for k, v in chosen_fields.items():
            if v is not None and k not in ("id", "created_at"):
                primary[k] = v

    # 2. Chuyển Contacts từ secondary sang primary
    from app.services import contact_service
    for contact in contact_service.FAKE_CONTACTS:
        if contact.get("customer_id") == secondary_id:
            contact["customer_id"] = primary_id
            contact["history"].append({
                "action": "MERGE",
                "from_customer_id": secondary_id,
                "to_customer_id": primary_id,
                "note": f"Gộp khách hàng #{secondary_id} vào #{primary_id}",
                "performed_by": current_user_username,
                "timestamp": datetime.now(),
            })

    # 3. Chuyển Opportunities từ secondary sang primary
    from app.services import opportunity_service
    for opp in opportunity_service.FAKE_OPPORTUNITIES:
        if opp.get("customer_id") == secondary_id:
            opp["customer_id"] = primary_id

    # 4. Chuyển Activities từ secondary sang primary
    from app.services import activity_service
    for act in activity_service.FAKE_ACTIVITIES:
        if act.get("customer_id") == secondary_id:
            act["customer_id"] = primary_id

    # 5. Chuyển Attachments từ secondary sang primary
    for att in CUSTOMER_ATTACHMENTS:
        if att.get("customer_id") == secondary_id:
            att["customer_id"] = primary_id

    # 6. Xóa secondary khỏi danh sách khách hàng
    delete_customer_record(secondary_id)

    return _enrich_customer_names(primary)


def get_company_group_tree(parent_id: int) -> Optional[dict]:
    """
    AC S3-05: Sơ đồ phân cấp công ty mẹ - công ty con / chi nhánh
    và tổng hợp hợp đồng/cơ hội toàn tập đoàn.
    """
    parent = get_customer_by_id(parent_id)
    if not parent:
        return None

    from app.services import opportunity_service
    all_opps = opportunity_service.FAKE_OPPORTUNITIES

    # Tìm các công ty con trực tiếp
    children = [c for c in FAKE_CUSTOMERS if c.get("parent_company_id") == parent_id]
    
    subsidiary_summaries = []
    total_group_won = sum(float(o.get("value", 0)) for o in all_opps if o.get("customer_id") == parent_id and o.get("stage") == "CLOSED_WON")
    total_group_open = sum(float(o.get("value", 0)) for o in all_opps if o.get("customer_id") == parent_id and o.get("stage") in ("PROSPECTING", "QUALIFICATION", "PROPOSAL", "NEGOTIATION"))

    for child in children:
        c_id = child["id"]
        c_won = sum(float(o.get("value", 0)) for o in all_opps if o.get("customer_id") == c_id and o.get("stage") == "CLOSED_WON")
        c_open = sum(float(o.get("value", 0)) for o in all_opps if o.get("customer_id") == c_id and o.get("stage") in ("PROSPECTING", "QUALIFICATION", "PROPOSAL", "NEGOTIATION"))
        
        total_group_won += c_won
        total_group_open += c_open

        subsidiary_summaries.append({
            "id": c_id,
            "name": child["name"],
            "tax_code": child.get("tax_code"),
            "status": child.get("status", "PROSPECT"),
            "total_won_value": c_won,
            "total_open_value": c_open,
        })

    return {
        "parent": parent,
        "subsidiaries": subsidiary_summaries,
        "total_group_won_value": total_group_won,
        "total_group_open_value": total_group_open,
        "total_members": len(subsidiary_summaries) + 1,
    }


def generate_customer_template_excel() -> bytes:
    """AC S3-06: Tải tệp Excel mẫu chứa các cột tiêu chuẩn để import."""
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "KhachHang_Template"

    headers = [
        "Tên khách hàng (*)",
        "Mã số thuế",
        "Ngành nghề",
        "Quy mô",
        "Website",
        "Địa chỉ",
        "Số điện thoại",
        "Email",
        "Trạng thái (PROSPECT/CUSTOMER)",
    ]
    ws.append(headers)

    # Style header
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Sample rows
    sample_rows = [
        [
            "Công ty Cổ phần Thép Đông Nam",
            "0109998881",
            "Sản xuất & Chế tạo",
            "100 - 500 nhân sự",
            "https://dongnamsteel.vn",
            "KCN Phố Nối A, Hưng Yên",
            "02213888999",
            "contact@dongnamsteel.vn",
            "PROSPECT",
        ],
        [
            "Công ty Dịch vụ Vận tải Hải Vân",
            "0307776662",
            "Logistics & Vận tải",
            "50 - 100 nhân sự",
            "https://haivanlogistics.com",
            "Hải An, Hải Phòng",
            "02253666777",
            "info@haivanlogistics.com",
            "CUSTOMER",
        ],
    ]
    for row in sample_rows:
        ws.append(row)

    # Auto width
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def preview_customer_import_excel(file_content: bytes) -> dict:
    """AC S3-06: Xem trước dữ liệu, phát hiện lỗi từng dòng, kiểm tra trùng MST."""
    import io
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active

    preview_rows = []
    seen_tax_codes_in_file = set()

    # Tìm index của các cột từ dòng 1
    header_cells = [c.value for c in ws[1]]
    
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):  # Dòng trống hoàn toàn
            continue

        name = str(row[0]).strip() if row[0] is not None else None
        tax_code = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
        industry = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
        company_size = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
        website = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
        address = str(row[5]).strip() if len(row) > 5 and row[5] is not None else None
        phone = str(row[6]).strip() if len(row) > 6 and row[6] is not None else None
        email = str(row[7]).strip() if len(row) > 7 and row[7] is not None else None
        status_val = str(row[8]).strip() if len(row) > 8 and row[8] is not None else "PROSPECT"

        errors = []
        if not name:
            errors.append("Tên công ty/khách hàng không được để trống")

        is_duplicate = False
        duplicate_reasons = []
        existing_id = None

        if tax_code:
            # Kiểm tra trùng với file
            if tax_code in seen_tax_codes_in_file:
                is_duplicate = True
                duplicate_reasons.append("Trùng MST với dòng khác trong chính tệp này")
            seen_tax_codes_in_file.add(tax_code)

            # Kiểm tra trùng với hệ thống
            existing = next((c for c in FAKE_CUSTOMERS if c.get("tax_code") == tax_code), None)
            if existing:
                is_duplicate = True
                duplicate_reasons.append(f"Trùng MST với khách hàng #{existing['id']} ({existing['name']}) trên hệ thống")
                existing_id = existing["id"]

        preview_rows.append({
            "row_number": row_idx,
            "name": name,
            "tax_code": tax_code,
            "industry": industry,
            "company_size": company_size,
            "website": website,
            "address": address,
            "status": status_val,
            "phone": phone,
            "email": email,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "is_duplicate": is_duplicate,
            "duplicate_reasons": duplicate_reasons,
            "existing_customer_id": existing_id,
        })

    valid_count = sum(1 for r in preview_rows if r["is_valid"] and not r["is_duplicate"])
    invalid_count = sum(1 for r in preview_rows if not r["is_valid"])
    dup_count = sum(1 for r in preview_rows if r["is_duplicate"])

    return {
        "total_rows": len(preview_rows),
        "valid_rows_count": valid_count,
        "invalid_rows_count": invalid_count,
        "duplicate_rows_count": dup_count,
        "rows": preview_rows,
    }


def commit_customer_import(
    rows: List[dict],
    duplicate_handling: str = "SKIP",
    current_user: dict = None,
) -> dict:
    """AC S3-06: Thực hiện import vào hệ thống theo tùy chọn SKIP hoặc UPDATE."""
    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    messages = []

    user_id = current_user["id"] if current_user else 1
    user_team = current_user.get("team_id") if current_user else 1

    for row in rows:
        if not row.get("is_valid", True) or not row.get("name"):
            failed += 1
            messages.append(f"Dòng {row.get('row_number')}: Dữ liệu không hợp lệ, bỏ qua")
            continue

        existing_id = row.get("existing_customer_id")
        tax_code = row.get("tax_code")

        # Kiểm tra lại xem có trùng với DB không
        existing_cust = None
        if existing_id:
            existing_cust = next((c for c in FAKE_CUSTOMERS if c["id"] == existing_id), None)
        elif tax_code:
            existing_cust = next((c for c in FAKE_CUSTOMERS if c.get("tax_code") == tax_code), None)

        if existing_cust:
            if duplicate_handling.upper() == "UPDATE":
                # Cập nhật thông tin khách hàng hiện tại
                for field in ["name", "industry", "company_size", "website", "address", "phone", "email", "status"]:
                    if row.get(field):
                        existing_cust[field] = row[field]
                updated += 1
                messages.append(f"Dòng {row.get('row_number')}: Cập nhật khách hàng #{existing_cust['id']} ({existing_cust['name']})")
            else:
                # Bỏ qua dòng trùng
                skipped += 1
                messages.append(f"Dòng {row.get('row_number')}: Trùng MST {tax_code}, bỏ qua theo cài đặt SKIP")
        else:
            # Thêm mới
            new_id = (max(c["id"] for c in FAKE_CUSTOMERS) + 1) if FAKE_CUSTOMERS else 1
            new_c = {
                "id": new_id,
                "name": row["name"],
                "tax_code": tax_code,
                "industry": row.get("industry"),
                "company_size": row.get("company_size"),
                "website": row.get("website"),
                "address": row.get("address"),
                "status": row.get("status") or "PROSPECT",
                "phone": row.get("phone"),
                "email": row.get("email"),
                "company": row["name"],
                "owner_id": user_id,
                "team_id": user_team,
                "created_at": datetime.now(),
            }
            FAKE_CUSTOMERS.append(new_c)
            inserted += 1
            messages.append(f"Dòng {row.get('row_number')}: Tạo mới thành công khách hàng #{new_id} ({row['name']})")

    return {
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "failed_count": failed,
        "messages": messages,
    }


FAKE_SAVED_FILTERS: List[dict] = [
    {
        "id": 1,
        "user_id": 1,
        "name": "Khách hàng công nghệ tiềm năng",
        "filter_criteria": {
            "industry": "Công nghệ thông tin",
            "status": "PROSPECT",
        },
        "created_at": datetime(2026, 1, 15, 8, 0, 0),
    }
]


def list_saved_filters(user_id: int) -> List[dict]:
    return [f for f in FAKE_SAVED_FILTERS if f["user_id"] == user_id]


def create_saved_filter(user_id: int, name: str, filter_criteria: dict) -> dict:
    new_id = max([f["id"] for f in FAKE_SAVED_FILTERS], default=0) + 1
    item = {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "filter_criteria": filter_criteria,
        "created_at": datetime.now(),
    }
    FAKE_SAVED_FILTERS.append(item)
    return item


def delete_saved_filter(filter_id: int, user_id: int) -> bool:
    for i, f in enumerate(FAKE_SAVED_FILTERS):
        if f["id"] == filter_id and f["user_id"] == user_id:
            FAKE_SAVED_FILTERS.pop(i)
            return True
    return False





