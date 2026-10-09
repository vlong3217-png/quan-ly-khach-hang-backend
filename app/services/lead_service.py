"""
Lead Service for S4-02 and S4-04:
- Manual lead creation with mandatory source (S4-02)
- Excel batch import with template, preview, row-level error reporting (S4-02)
- Duplicate detection by email, phone, company (S4-04)
- Suggest attach to existing customers (S4-04)
- Lead merge preserving activity history and snapshot (S4-04)
"""

import copy
import io
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.lead import Lead as LeadModel, LeadMergeHistory as LeadMergeHistoryModel
from app.models.customer import Customer as CustomerModel
from app.services import customer_service, auth_service
from app.services.activity_service import FAKE_ACTIVITIES

INITIAL_LEADS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Trần Văn Hùng",
        "company_name": "Công ty TNHH SmartTech",
        "title": "Trưởng phòng CNTT",
        "email": "hung.tran@smarttech.vn",
        "phone": "0912345678",
        "address": "Cầu Giấy, Hà Nội",
        "source": "Hội thảo",
        "campaign_id": 1,
        "customer_id": None,
        "status": "NEW",
        "notes": "Gặp mặt tại hội thảo chuyển đổi số",
        "merged_into_id": None,
        "owner_id": 1,
        "team_id": 1,
        "created_at": datetime(2026, 3, 1, 9, 0, 0),
        "updated_at": None,
    },
    {
        "id": 2,
        "name": "Nguyễn Thị Mai",
        "company_name": "Tập đoàn Đại Nam",
        "title": "Giám đốc Marketing",
        "email": "mai.nguyen@dainam.com",
        "phone": "0987654321",
        "address": "Quận 1, TP. Hồ Chí Minh",
        "source": "Sự kiện",
        "campaign_id": 1,
        "customer_id": None,
        "status": "CONTACTED",
        "notes": "Nhận danh thiếp tại Tech Expo",
        "merged_into_id": None,
        "owner_id": 2,
        "team_id": 1,
        "created_at": datetime(2026, 3, 2, 14, 30, 0),
        "updated_at": None,
    },
    {
        "id": 3,
        "name": "Lê Hoàng Long",
        "company_name": "Công ty Cổ phần VinaLogistics",
        "title": "Phó Giám đốc Điều hành",
        "email": "long.le@vinalogistics.vn",
        "phone": "0903456789",
        "address": "Hải Phòng",
        "source": "Danh thiếp",
        "campaign_id": None,
        "customer_id": None,
        "status": "QUALIFIED",
        "notes": "Trao đổi danh thiếp tại gala doanh nhân",
        "merged_into_id": None,
        "owner_id": 3,
        "team_id": 1,
        "created_at": datetime(2026, 3, 5, 11, 15, 0),
        "updated_at": None,
    },
]

FAKE_LEADS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_LEADS)
FAKE_LEAD_MERGE_HISTORIES: List[Dict[str, Any]] = []


def reset_fake_leads() -> None:
    global FAKE_LEADS, FAKE_LEAD_MERGE_HISTORIES
    FAKE_LEADS = copy.deepcopy(INITIAL_LEADS)
    FAKE_LEAD_MERGE_HISTORIES = []

    # Đồng bộ với SQLite nếu DB có sẵn
    try:
        db: Session = SessionLocal()
        try:
            db.query(LeadMergeHistoryModel).delete()
            db.query(LeadModel).delete()
            for l in INITIAL_LEADS:
                lead_m = LeadModel(
                    id=l["id"],
                    name=l["name"],
                    company_name=l.get("company_name"),
                    title=l.get("title"),
                    email=l.get("email"),
                    phone=l.get("phone"),
                    address=l.get("address"),
                    source=l["source"],
                    campaign_id=l.get("campaign_id"),
                    customer_id=l.get("customer_id"),
                    status=l.get("status", "NEW"),
                    notes=l.get("notes"),
                    merged_into_id=l.get("merged_into_id"),
                    owner_id=l.get("owner_id", 1),
                    team_id=l.get("team_id"),
                    created_at=l.get("created_at"),
                )
                db.add(lead_m)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


# ==============================================================================
# Helper Functions: Normalization & Matching
# ==============================================================================

def normalize_phone(phone: Optional[str]) -> str:
    """Chuẩn hóa số điện thoại: chỉ giữ lại chữ số, chuyển +84 thành 0."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    return digits


def normalize_email(email: Optional[str]) -> str:
    """Chuẩn hóa email: viết thường, loại bỏ khoảng trắng."""
    if not email:
        return ""
    return str(email).strip().lower()


def normalize_company(name: Optional[str]) -> str:
    """Chuẩn hóa tên công ty, loại bỏ loại hình doanh nghiệp phổ biến."""
    if not name:
        return ""
    s = str(name).lower().strip()
    s = re.sub(r"[,\.\-_/\\()]+", " ", s)
    legal_terms = [
        r"\bcông ty\b", r"\bcty\b", r"\bcổ phần\b", r"\bcp\b",
        r"\btrách nhiệm hữu hạn\b", r"\btnhh\b", r"\bmtv\b",
        r"\bjsc\b", r"\bltd\b", r"\binc\b", r"\bcorp\b", r"\btập đoàn\b", r"\bgroup\b"
    ]
    for term in legal_terms:
        s = re.sub(term, " ", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _is_valid_email_format(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def _is_valid_phone_format(phone: str) -> bool:
    norm = normalize_phone(phone)
    return len(norm) in (10, 11)


def _enrich_lead_display(lead: dict) -> dict:
    """Bổ sung owner_name, campaign_name, customer_name cho hiển thị."""
    enriched = dict(lead)
    owner = auth_service.get_user_by_id(enriched.get("owner_id"))
    enriched["owner_name"] = owner.get("full_name") if owner else None

    # Tên khách hàng nếu có
    if enriched.get("customer_id"):
        cust = customer_service.get_customer_by_id(enriched["customer_id"])
        enriched["customer_name"] = cust.get("name") if cust else None
    else:
        enriched["customer_name"] = None

    # Tên chiến dịch nếu có
    from app.services import campaign_service
    if enriched.get("campaign_id"):
        camp = campaign_service.get_campaign_by_id(enriched["campaign_id"])
        enriched["campaign_name"] = camp.get("name") if camp else None
    else:
        enriched["campaign_name"] = None

    return enriched


# ==============================================================================
# S4-02: Lead CRUD & Manual Creation
# ==============================================================================

def create_lead(data: dict, current_user: dict) -> dict:
    """
    AC S4-02: Nhập tay một lead từ sự kiện hoặc danh thiếp.
    MỌI LEAD NHẬP VÀO ĐỀU BẮT BUỘC CÓ NGUỒN (source).
    """
    source = data.get("source")
    if not source or not str(source).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mọi lead nhập vào đều bắt buộc có nguồn (source)",
        )

    name = data.get("name")
    if not name or not str(name).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Họ và tên lead là bắt buộc",
        )

    new_id = (max((l["id"] for l in FAKE_LEADS), default=0) + 1) if FAKE_LEADS else 1
    new_lead = {
        "id": new_id,
        "name": str(name).strip(),
        "company_name": data.get("company_name", "").strip() if data.get("company_name") else None,
        "title": data.get("title", "").strip() if data.get("title") else None,
        "email": normalize_email(data.get("email")) or None,
        "phone": data.get("phone", "").strip() if data.get("phone") else None,
        "address": data.get("address", "").strip() if data.get("address") else None,
        "source": str(source).strip(),
        "campaign_id": data.get("campaign_id"),
        "customer_id": data.get("customer_id"),
        "status": data.get("status", "NEW"),
        "notes": data.get("notes"),
        "merged_into_id": None,
        "owner_id": data.get("owner_id") or current_user.get("id", 1),
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    FAKE_LEADS.append(new_lead)

    # Lưu vào DB nếu có
    try:
        db: Session = SessionLocal()
        try:
            lead_model = LeadModel(
                id=new_lead["id"],
                name=new_lead["name"],
                company_name=new_lead["company_name"],
                title=new_lead["title"],
                email=new_lead["email"],
                phone=new_lead["phone"],
                address=new_lead["address"],
                source=new_lead["source"],
                campaign_id=new_lead["campaign_id"],
                customer_id=new_lead["customer_id"],
                status=new_lead["status"],
                notes=new_lead["notes"],
                merged_into_id=None,
                owner_id=new_lead["owner_id"],
                team_id=new_lead["team_id"],
            )
            db.add(lead_model)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return _enrich_lead_display(new_lead)


def get_lead_by_id(lead_id: int) -> Optional[dict]:
    for l in FAKE_LEADS:
        if l["id"] == lead_id:
            return _enrich_lead_display(l)
    return None


def list_leads(
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    campaign_id: Optional[int] = None,
    search: Optional[str] = None,
    include_merged: bool = False,
) -> List[dict]:
    results = list(FAKE_LEADS)

    if not include_merged:
        results = [l for l in results if l.get("status") != "MERGED"]

    if status_filter:
        s_val = status_filter.upper().strip()
        results = [l for l in results if l.get("status") == s_val]

    if source_filter:
        src = source_filter.lower().strip()
        results = [l for l in results if src in (l.get("source") or "").lower()]

    if campaign_id is not None:
        results = [l for l in results if l.get("campaign_id") == campaign_id]

    if search:
        q = search.lower().strip()
        results = [
            l for l in results
            if q in (l.get("name") or "").lower()
            or q in (l.get("email") or "").lower()
            or q in (l.get("phone") or "").lower()
            or q in (l.get("company_name") or "").lower()
        ]

    results.sort(key=lambda x: x["id"], reverse=True)
    return [_enrich_lead_display(l) for l in results]


def update_lead(lead_id: int, data: dict, current_user: dict) -> dict:
    lead = None
    for l in FAKE_LEADS:
        if l["id"] == lead_id:
            lead = l
            break

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )

    if "source" in data:
        source_val = data["source"]
        if source_val is not None and not str(source_val).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nguồn lead không được để trống",
            )
        lead["source"] = str(source_val).strip()

    if "name" in data and data["name"] is not None:
        if not str(data["name"]).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Họ và tên lead không được để trống",
            )
        lead["name"] = str(data["name"]).strip()

    for k, v in data.items():
        if k not in ("id", "source", "name") and v is not None:
            lead[k] = v

    lead["updated_at"] = datetime.now(timezone.utc)

    # Đồng bộ DB
    try:
        db: Session = SessionLocal()
        try:
            m = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
            if m:
                for k, v in lead.items():
                    if hasattr(m, k) and k != "id":
                        setattr(m, k, v)
                db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return _enrich_lead_display(lead)


def delete_lead(lead_id: int) -> bool:
    global FAKE_LEADS
    initial_len = len(FAKE_LEADS)
    FAKE_LEADS = [l for l in FAKE_LEADS if l["id"] != lead_id]

    try:
        db: Session = SessionLocal()
        try:
            m = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
            if m:
                db.delete(m)
                db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return len(FAKE_LEADS) < initial_len


# ==============================================================================
# S4-02: Excel Template, Preview & Batch Import
# ==============================================================================

def generate_lead_import_template() -> bytes:
    """
    AC S4-02: Tải tệp mẫu Excel chuẩn hóa cho việc nhập lead hàng loạt.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lead_Template"

    headers = [
        "Họ và tên (*)",
        "Nguồn lead (*)",
        "Số điện thoại",
        "Email",
        "Tên công ty",
        "Chức vụ",
        "Địa chỉ",
        "Ghi chú",
        "Mã chiến dịch",
    ]

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # 2 dòng dữ liệu mẫu
    sample_rows = [
        [
            "Trần Quốc Bảo",
            "Hội thảo Chuyển đổi số 2026",
            "0981234567",
            "bao.tran@techvn.com",
            "Công ty Cổ phần Công nghệ ABC",
            "Trưởng phòng CNTT",
            "Cầu Giấy, Hà Nội",
            "Gặp gỡ và trao đổi danh thiếp tại hội thảo",
            "CAMP-2026-EXPO",
        ],
        [
            "Lê Thu Hà",
            "Sự kiện Networking",
            "0977654321",
            "ha.le@asiatrading.vn",
            "Công ty TNHH Thương mại Châu Á",
            "Giám đốc Kinh doanh",
            "Quận 1, TP. Hồ Chí Minh",
            "Quan tâm phần mềm CRM",
            "",
        ],
    ]

    for row in sample_rows:
        ws.append(row)

    # Điều chỉnh độ rộng cột
    column_widths = [22, 26, 16, 26, 32, 22, 28, 38, 18]
    for i, width in enumerate(column_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def preview_import_leads_excel(file_bytes: bytes, current_user: dict) -> dict:
    """
    AC S4-02: Xem trước và báo lỗi theo từng dòng.
    Kiểm tra bắt buộc có nguồn, kiểm tra định dạng email/SĐT, kiểm tra trùng lặp.
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tệp không đúng định dạng Excel (.xlsx): {str(e)}",
        )

    ws = wb.active
    rows_data: List[dict] = []
    duplicate_count = 0
    invalid_count = 0

    from app.services import campaign_service

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        raw_name = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
        raw_source = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        raw_phone = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        raw_email = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
        raw_company = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
        raw_title = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""
        raw_address = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
        raw_notes = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
        raw_camp_code = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""

        errors: List[str] = []
        is_duplicate = False
        duplicate_reasons: List[str] = []
        existing_lead_id = None
        existing_customer_id = None
        campaign_id = None

        # 1. Bắt buộc: Họ và tên
        if not raw_name:
            errors.append("Họ và tên lead là bắt buộc (cột 1)")

        # 2. Bắt buộc: Nguồn lead (AC S4-02)
        if not raw_source:
            errors.append("Nguồn lead là bắt buộc (cột 2)")

        # 3. Kiểm tra định dạng Email nếu có
        if raw_email and not _is_valid_email_format(raw_email):
            errors.append("Email không đúng định dạng")

        # 4. Kiểm tra định dạng SĐT nếu có
        if raw_phone and not _is_valid_phone_format(raw_phone):
            errors.append("Số điện thoại không hợp lệ (phải gồm 10-11 chữ số)")

        # 5. Map Campaign Code nếu có
        if raw_camp_code:
            camp = campaign_service.get_campaign_by_code(raw_camp_code)
            if camp:
                campaign_id = camp["id"]
            else:
                errors.append(f"Không tìm thấy chiến dịch với mã '{raw_camp_code}'")

        # 6. Kiểm tra trùng lặp (với Lead hiện có & Customer hiện có)
        dup_check = check_lead_duplicates(
            email=raw_email,
            phone=raw_phone,
            company_name=raw_company,
        )
        if dup_check["has_duplicates"]:
            is_duplicate = True
            for m in dup_check["matching_leads"]:
                duplicate_reasons.extend(m["match_reasons"])
                if not existing_lead_id:
                    existing_lead_id = m["lead"]["id"]
            for m in dup_check["matching_customers"]:
                duplicate_reasons.extend(m["match_reasons"])
                if not existing_customer_id:
                    existing_customer_id = m["customer"]["id"]

        is_valid = len(errors) == 0
        if not is_valid:
            invalid_count += 1
        if is_duplicate:
            duplicate_count += 1

        rows_data.append({
            "row_number": row_idx,
            "name": raw_name or None,
            "source": raw_source or None,
            "phone": raw_phone or None,
            "email": raw_email or None,
            "company_name": raw_company or None,
            "title": raw_title or None,
            "address": raw_address or None,
            "notes": raw_notes or None,
            "campaign_code": raw_camp_code or None,
            "campaign_id": campaign_id,
            "is_valid": is_valid,
            "errors": errors,
            "is_duplicate": is_duplicate,
            "duplicate_reasons": list(set(duplicate_reasons)),
            "existing_lead_id": existing_lead_id,
            "existing_customer_id": existing_customer_id,
        })

    return {
        "total_rows": len(rows_data),
        "valid_rows_count": len([r for r in rows_data if r["is_valid"]]),
        "invalid_rows_count": invalid_count,
        "duplicate_rows_count": duplicate_count,
        "rows": rows_data,
    }


def commit_import_leads(
    rows: List[dict],
    duplicate_handling: str,
    current_user: dict,
) -> dict:
    """
    AC S4-02: Nhập hàng loạt vào hệ thống theo lựa chọn xử lý trùng (SKIP, UPDATE, IMPORT_ANYWAY).
    """
    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    result_leads = []

    for r in rows:
        if not r.get("is_valid", True):
            failed += 1
            continue

        is_dup = r.get("is_duplicate", False)

        if is_dup:
            if duplicate_handling == "SKIP":
                skipped += 1
                continue
            elif duplicate_handling == "UPDATE" and r.get("existing_lead_id"):
                up_id = r["existing_lead_id"]
                update_payload = {
                    "name": r.get("name"),
                    "source": r.get("source"),
                    "phone": r.get("phone"),
                    "email": r.get("email"),
                    "company_name": r.get("company_name"),
                    "title": r.get("title"),
                    "address": r.get("address"),
                    "notes": r.get("notes"),
                    "campaign_id": r.get("campaign_id"),
                }
                up_res = update_lead(up_id, update_payload, current_user)
                updated += 1
                result_leads.append(up_res)
                continue

        # Thêm mới
        lead_payload = {
            "name": r.get("name"),
            "source": r.get("source"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "company_name": r.get("company_name"),
            "title": r.get("title"),
            "address": r.get("address"),
            "notes": r.get("notes"),
            "campaign_id": r.get("campaign_id"),
            "customer_id": r.get("existing_customer_id"),
            "status": "NEW",
        }
        new_lead = create_lead(lead_payload, current_user)
        inserted += 1
        result_leads.append(new_lead)

    return {
        "total_rows": len(rows),
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "failed_count": failed,
        "leads": result_leads,
    }


# ==============================================================================
# S4-04: Duplicate Detection, Attach to Customer & Merge Leads
# ==============================================================================

def check_lead_duplicates(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    exclude_lead_id: Optional[int] = None,
) -> dict:
    """
    AC S4-04: Phát hiện trùng theo email, số điện thoại và tên công ty.
    Đồng thời tìm kiếm trùng lặp với Khách hàng (Customer) đã có.
    """
    matching_leads: List[dict] = []
    matching_customers: List[dict] = []

    norm_target_email = normalize_email(email)
    norm_target_phone = normalize_phone(phone)
    norm_target_company = normalize_company(company_name)

    # 1. So sánh với danh sách Leads
    for l in FAKE_LEADS:
        if l.get("status") == "MERGED":
            continue
        if exclude_lead_id and l["id"] == exclude_lead_id:
            continue

        reasons = []
        score = 0.0

        # Match email
        l_email = normalize_email(l.get("email"))
        if norm_target_email and l_email and norm_target_email == l_email:
            reasons.append(f"Trùng email: {l.get('email')}")
            score = max(score, 1.0)

        # Match phone
        l_phone = normalize_phone(l.get("phone"))
        if norm_target_phone and l_phone and norm_target_phone == l_phone:
            reasons.append(f"Trùng số điện thoại: {l.get('phone')}")
            score = max(score, 0.95)

        # Match company
        l_comp = normalize_company(l.get("company_name"))
        if norm_target_company and l_comp:
            if norm_target_company == l_comp:
                reasons.append(f"Trùng tên công ty: {l.get('company_name')}")
                score = max(score, 0.9)
            elif norm_target_company in l_comp or l_comp in norm_target_company:
                reasons.append(f"Tên công ty tương tự: {l.get('company_name')}")
                score = max(score, 0.75)

        if reasons:
            matching_leads.append({
                "confidence_score": score,
                "match_reasons": reasons,
                "lead": _enrich_lead_display(l),
            })

    # 2. So sánh với Khách hàng đã có trong hệ thống (S4-04)
    customers = customer_service.FAKE_CUSTOMERS
    for c in customers:
        reasons = []
        score = 0.0

        c_email = normalize_email(c.get("email"))
        if norm_target_email and c_email and norm_target_email == c_email:
            reasons.append(f"Trùng email với Khách hàng #{c['id']} ({c.get('name')})")
            score = max(score, 1.0)

        c_phone = normalize_phone(c.get("phone"))
        if norm_target_phone and c_phone and norm_target_phone == c_phone:
            reasons.append(f"Trùng số điện thoại với Khách hàng #{c['id']} ({c.get('name')})")
            score = max(score, 0.95)

        c_name = normalize_company(c.get("name") or c.get("company"))
        if norm_target_company and c_name:
            if norm_target_company == c_name:
                reasons.append(f"Trùng tên công ty với Khách hàng #{c['id']} ({c.get('name')})")
                score = max(score, 0.9)
            elif norm_target_company in c_name or c_name in norm_target_company:
                reasons.append(f"Tên công ty tương tự Khách hàng #{c['id']} ({c.get('name')})")
                score = max(score, 0.75)

        if reasons:
            matching_customers.append({
                "confidence_score": score,
                "match_reasons": reasons,
                "customer": customer_service._enrich_customer_names(c),
            })

    matching_leads.sort(key=lambda x: x["confidence_score"], reverse=True)
    matching_customers.sort(key=lambda x: x["confidence_score"], reverse=True)

    has_dups = bool(matching_leads or matching_customers)
    return {
        "has_duplicates": has_dups,
        "matching_leads": matching_leads,
        "matching_customers": matching_customers,
    }


def find_lead_duplicates(lead_id: int) -> dict:
    """AC S4-04: Tra cứu trùng lặp cho một Lead cụ thể."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )

    return check_lead_duplicates(
        email=lead.get("email"),
        phone=lead.get("phone"),
        company_name=lead.get("company_name"),
        exclude_lead_id=lead_id,
    )


def attach_lead_to_customer(
    lead_id: int,
    customer_id: int,
    create_contact: bool = True,
    current_user: Optional[dict] = None,
) -> dict:
    """
    AC S4-04: Lead trùng với khách hàng đã có được gợi ý gắn thẳng vào khách hàng đó.
    Tự động tạo Contact mới thuộc Customer nếu create_contact=True.
    """
    lead = None
    for l in FAKE_LEADS:
        if l["id"] == lead_id:
            lead = l
            break

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )

    cust = customer_service.get_customer_by_id(customer_id)
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng ID {customer_id}",
        )

    lead["customer_id"] = customer_id
    lead["status"] = "CONVERTED"
    lead["updated_at"] = datetime.now(timezone.utc)

    # Nếu tùy chọn tạo người liên hệ
    created_contact = None
    if create_contact:
        from app.services import contact_service
        contact_payload = {
            "customer_id": customer_id,
            "name": lead["name"],
            "phone": lead.get("phone"),
            "email": lead.get("email"),
            "position": lead.get("title") or "Người liên hệ từ Lead",
            "decision_role": "INFLUENCER",
            "is_primary": False,
            "notes": f"Được chuyển đổi từ Lead #{lead_id} (Nguồn: {lead.get('source')})",
        }
        created_contact = contact_service.create_contact(contact_payload, current_user or {"full_name": "Admin"})

    # Đồng bộ DB
    try:
        db: Session = SessionLocal()
        try:
            m = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
            if m:
                m.customer_id = customer_id
                m.status = "CONVERTED"
                db.commit()
        finally:
            db.close()
    except Exception:
        pass

    enriched = _enrich_lead_display(lead)
    enriched["created_contact"] = created_contact
    return enriched


def preview_merge_leads(primary_id: int, secondary_id: int) -> dict:
    """
    AC S4-04: API xem trước so sánh hai lead và số lượng hoạt động sẽ chuyển.
    """
    primary = get_lead_by_id(primary_id)
    secondary = get_lead_by_id(secondary_id)

    if not primary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead chính ID {primary_id}",
        )
    if not secondary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead phụ ID {secondary_id}",
        )

    if primary_id == secondary_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể gộp một lead với chính nó",
        )

    # Đếm số activities gắn với secondary_lead
    acts_count = len([a for a in FAKE_ACTIVITIES if a.get("lead_id") == secondary_id])

    comparison_fields = [
        {"field": "name", "label": "Họ và tên", "primary": primary.get("name"), "secondary": secondary.get("name")},
        {"field": "company_name", "label": "Công ty", "primary": primary.get("company_name"), "secondary": secondary.get("company_name")},
        {"field": "title", "label": "Chức danh", "primary": primary.get("title"), "secondary": secondary.get("title")},
        {"field": "email", "label": "Email", "primary": primary.get("email"), "secondary": secondary.get("email")},
        {"field": "phone", "label": "Số điện thoại", "primary": primary.get("phone"), "secondary": secondary.get("phone")},
        {"field": "source", "label": "Nguồn lead", "primary": primary.get("source"), "secondary": secondary.get("source")},
        {"field": "address", "label": "Địa chỉ", "primary": primary.get("address"), "secondary": secondary.get("address")},
        {"field": "notes", "label": "Ghi chú", "primary": primary.get("notes"), "secondary": secondary.get("notes")},
    ]

    return {
        "primary": primary,
        "secondary": secondary,
        "comparison_fields": comparison_fields,
        "activities_to_transfer": acts_count,
    }


def merge_leads(
    primary_id: int,
    secondary_id: int,
    chosen_fields: Optional[dict] = None,
    current_user: Optional[dict] = None,
) -> dict:
    """
    AC S4-04: Gộp giữ nguyên lịch sử của cả hai bản ghi.
    - Chuyển giao toàn bộ hoạt động (Activities) sang Primary Lead.
    - Lưu snapshot của Secondary Lead vào LeadMergeHistory.
    - Đổi status Secondary Lead = MERGED để ẩn khỏi danh sách gọi, tránh trùng lặp cuộc gọi.
    """
    primary = None
    secondary = None
    for l in FAKE_LEADS:
        if l["id"] == primary_id:
            primary = l
        if l["id"] == secondary_id:
            secondary = l

    if not primary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead chính ID {primary_id}",
        )
    if not secondary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead phụ ID {secondary_id}",
        )
    if primary_id == secondary_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể gộp một lead với chính nó",
        )

    # 1. Chụp snapshot bản ghi secondary trước khi gộp
    snapshot_data = copy.deepcopy(secondary)
    # Convert datetime sang str để serialize JSON an toàn
    for k, v in snapshot_data.items():
        if isinstance(v, datetime):
            snapshot_data[k] = v.isoformat()

    user_name = current_user.get("full_name") or current_user.get("email") if current_user else "Admin"

    merge_history_item = {
        "id": len(FAKE_LEAD_MERGE_HISTORIES) + 1,
        "primary_lead_id": primary_id,
        "secondary_lead_id": secondary_id,
        "secondary_lead_name": secondary.get("name"),
        "secondary_snapshot": json.dumps(snapshot_data, ensure_ascii=False),
        "merged_by": user_name,
        "merged_at": datetime.now(timezone.utc),
    }
    FAKE_LEAD_MERGE_HISTORIES.append(merge_history_item)

    # 2. Áp dụng chosen_fields vào primary nếu có
    if chosen_fields:
        for f, val in chosen_fields.items():
            if val is not None and f not in ("id", "created_at"):
                primary[f] = val
    else:
        # Tự động điền các trường còn thiếu của primary từ secondary
        for k in ("company_name", "title", "email", "phone", "address", "notes", "campaign_id"):
            if not primary.get(k) and secondary.get(k):
                primary[k] = secondary.get(k)

    # Nối thêm ghi chú gộp vào primary notes
    merge_note = f"\n[Gộp lead từ #{secondary_id} ({secondary.get('name')}) vào lúc {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}]"
    primary["notes"] = (primary.get("notes") or "") + merge_note
    primary["updated_at"] = datetime.now(timezone.utc)

    # 3. Chuyển toàn bộ hoạt động (Activities) sang primary_id
    for a in FAKE_ACTIVITIES:
        if a.get("lead_id") == secondary_id:
            a["lead_id"] = primary_id

    # 4. Đánh dấu secondary là MERGED
    secondary["status"] = "MERGED"
    secondary["merged_into_id"] = primary_id
    secondary["updated_at"] = datetime.now(timezone.utc)

    # 5. Lưu vào Database
    try:
        db: Session = SessionLocal()
        try:
            # Lưu history
            m_hist = LeadMergeHistoryModel(
                primary_lead_id=primary_id,
                secondary_lead_id=secondary_id,
                secondary_lead_name=merge_history_item["secondary_lead_name"],
                secondary_snapshot=merge_history_item["secondary_snapshot"],
                merged_by=user_name,
            )
            db.add(m_hist)

            # Cập nhật primary
            m_prim = db.query(LeadModel).filter(LeadModel.id == primary_id).first()
            if m_prim:
                for k, v in primary.items():
                    if hasattr(m_prim, k) and k != "id":
                        setattr(m_prim, k, v)

            # Cập nhật secondary
            m_sec = db.query(LeadModel).filter(LeadModel.id == secondary_id).first()
            if m_sec:
                m_sec.status = "MERGED"
                m_sec.merged_into_id = primary_id

            db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return _enrich_lead_display(primary)
