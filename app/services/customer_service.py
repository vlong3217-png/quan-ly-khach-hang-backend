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
    """Bổ sung owner_name và team_name cho customer response."""
    c = copy.deepcopy(customer)
    owner = auth_service.get_user_by_id(c.get("owner_id"))
    c["owner_name"] = owner["full_name"] if owner else None

    team = auth_service.get_team_by_id(c.get("team_id"))
    c["team_name"] = team["name"] if team else None
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
) -> tuple[int, list[dict]]:
    """
    AC S3-01:
    - Nhân viên (USER) chỉ thấy khách hàng mình sở hữu (owner_id == user_id).
    - Trưởng nhóm (MANAGER) thấy toàn bộ khách hàng của nhóm (team_id == user_team_id).
    - Quản trị viên (ADMIN) thấy tất cả.
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


