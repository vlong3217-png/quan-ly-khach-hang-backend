"""
PDF Template Service with dual-mode (MySQL Database persistence & in-memory fallback) (S7-05).
Manages dynamic configurable PDF templates for quotes and contracts.
"""

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.pdf_template import PDFTemplateModel


INITIAL_PDF_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Mẫu Báo giá Doanh nghiệp Chuẩn 2026",
        "template_type": "QUOTE",
        "is_default": True,
        "is_active": True,
        "company_name": "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM",
        "company_tax_code": "0109888999",
        "company_address": "Tòa nhà Technosoft, Phố Duy Tân, Cầu Giấy, Hà Nội",
        "company_phone": "1900 6868 - 024.3795.8888",
        "company_email": "sales@crmvietnam.vn",
        "company_website": "https://crmvietnam.vn",
        "company_bank_info": "Số TK: 19036888999018 - Techcombank Chi nhánh Thăng Long - Chủ TK: CÔNG TY CP CÔNG NGHỆ CRM VIỆT NAM",
        "logo_url": None,
        "primary_color": "#1E40AF",  # Xanh dương nhận diện thương hiệu
        "secondary_color": "#F3F4F6",
        "header_title": "BÁO GIÁ THƯƠNG MẠI",
        "terms_and_conditions": "1. Báo giá có hiệu lực trong vòng 30 ngày kể từ ngày ban hành.\n2. Giá trên đã bao gồm chi phí cài đặt và đào tạo người dùng cơ bản.\n3. Phương thức thanh toán chuyển khoản theo thông tin ngân hàng ở trên.",
        "footer_text": "Trân trọng cảm ơn Quý khách hàng đã quan tâm đến giải pháp của chúng tôi!",
        "signature_customer_label": "ĐẠI DIỆN KHÁCH HÀNG",
        "signature_company_label": "ĐẠI DIỆN CÔNG TY BÁO GIÁ",
        "created_at": "2026-01-01T08:00:00",
        "updated_at": "2026-01-01T08:00:00",
    },
    {
        "id": 2,
        "name": "Mẫu Báo giá Đối tác VIP & Dự án Lớn",
        "template_type": "QUOTE",
        "is_default": False,
        "is_active": True,
        "company_name": "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM",
        "company_tax_code": "0109888999",
        "company_address": "Tầng 18, Keangnam Landmark 72, Nam Từ Liêm, Hà Nội",
        "company_phone": "1900 6868 (Ext: 102)",
        "company_email": "vip.sales@crmvietnam.vn",
        "company_website": "https://crmvietnam.vn",
        "company_bank_info": "Số TK: 0011004888888 - Vietcombank Sở Giao Dịch - Chủ TK: CÔNG TY CP CÔNG NGHỆ CRM VIỆT NAM",
        "logo_url": None,
        "primary_color": "#0D9488",  # Xanh ngọc Teal sang trọng
        "secondary_color": "#F0FDFA",
        "header_title": "BẢNG CHÀO GIÁ DỰ ÁN ĐẶC BIỆT",
        "terms_and_conditions": "1. Chính sách chiết khấu đối tác chiến lược áp dụng theo thỏa thuận khung.\n2. Bảo hành kỹ thuật 24/7 trong 12 tháng đầu tiên.",
        "footer_text": "Cam kết chất lượng dịch vụ và bảo mật thông tin tuyệt đối.",
        "signature_customer_label": "XÁC NHẬN CỦA ĐỐI TÁC",
        "signature_company_label": "BAN TỔNG GIÁM ĐỐC",
        "created_at": "2026-01-02T08:00:00",
        "updated_at": "2026-01-02T08:00:00",
    },
    {
        "id": 3,
        "name": "Mẫu Hợp đồng Kinh tế Tiêu chuẩn 2026",
        "template_type": "CONTRACT",
        "is_default": True,
        "is_active": True,
        "company_name": "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM",
        "company_tax_code": "0109888999",
        "company_address": "Tòa nhà Technosoft, Phố Duy Tân, Cầu Giấy, Hà Nội",
        "company_phone": "1900 6868 - 024.3795.8888",
        "company_email": "legal@crmvietnam.vn",
        "company_website": "https://crmvietnam.vn",
        "company_bank_info": "Số TK: 19036888999018 - Techcombank Chi nhánh Thăng Long - Chủ TK: CÔNG TY CP CÔNG NGHỆ CRM VIỆT NAM",
        "logo_url": None,
        "primary_color": "#1E3A8A",  # Xanh Navy đậm tính pháp lý
        "secondary_color": "#EFF6FF",
        "header_title": "HỢP ĐỒNG KINH TẾ DỊCH VỤ PHẦN MỀM",
        "terms_and_conditions": "1. Hợp đồng có hiệu lực kể từ ngày ký.\n2. Hai bên cam kết thực hiện đúng các điều khoản thanh toán và bàn giao theo quy định của pháp luật.\n3. Mọi tranh chấp phát sinh sẽ được giải quyết trước tiên thông qua thương lượng hòa giải.",
        "footer_text": "Hợp đồng được lập thành 02 bản có giá trị pháp lý như nhau, mỗi bên giữ 01 bản.",
        "signature_customer_label": "ĐẠI DIỆN BÊN A (KHÁCH HÀNG)",
        "signature_company_label": "ĐẠI DIỆN BÊN B (NHÀ CUNG CẤP)",
        "created_at": "2026-01-03T08:00:00",
        "updated_at": "2026-01-03T08:00:00",
    },
]

FAKE_PDF_TEMPLATES: List[Dict[str, Any]] = copy.deepcopy(INITIAL_PDF_TEMPLATES)


def reset_fake_pdf_templates() -> None:
    global FAKE_PDF_TEMPLATES
    FAKE_PDF_TEMPLATES = copy.deepcopy(INITIAL_PDF_TEMPLATES)


def get_all_templates(
    template_type: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = True,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Lấy danh sách các mẫu PDF có trong hệ thống."""
    results = list(FAKE_PDF_TEMPLATES)

    if template_type:
        tt = template_type.upper().strip()
        results = [t for t in results if str(t.get("template_type", "")).upper() == tt]

    if active_only:
        results = [t for t in results if t.get("is_active", True)]

    if search and search.strip():
        kw = search.lower().strip()
        results = [
            t for t in results
            if kw in str(t.get("name", "")).lower()
            or kw in str(t.get("company_name", "")).lower()
            or kw in str(t.get("header_title", "")).lower()
        ]

    # Sắp xếp mặc định lên đầu, sau đó theo ID
    results.sort(key=lambda x: (not x.get("is_default", False), x.get("id", 0)))
    return results


def get_template_by_id(template_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết một mẫu cấu hình theo ID."""
    for t in FAKE_PDF_TEMPLATES:
        if t.get("id") == template_id:
            return t
    return None


def get_default_template(template_type: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Lấy mẫu mặc định cho loại tài liệu tương ứng (QUOTE hoặc CONTRACT)."""
    tt = template_type.upper().strip()
    for t in FAKE_PDF_TEMPLATES:
        if str(t.get("template_type", "")).upper() == tt and t.get("is_default"):
            return t

    # Nếu không có mẫu nào đánh dấu default, lấy mẫu đầu tiên cùng loại
    for t in FAKE_PDF_TEMPLATES:
        if str(t.get("template_type", "")).upper() == tt:
            return t

    # Fallback mẫu đầu tiên
    return FAKE_PDF_TEMPLATES[0] if FAKE_PDF_TEMPLATES else INITIAL_PDF_TEMPLATES[0]


def create_template(data: dict, db: Optional[Session] = None) -> Dict[str, Any]:
    """Tạo mới một mẫu cấu hình PDF (S7-05 AC 2)."""
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên mẫu không được để trống",
        )

    template_type = (data.get("template_type") or "QUOTE").upper().strip()
    if template_type not in ("QUOTE", "CONTRACT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loại mẫu không hợp lệ (chỉ chấp nhận QUOTE hoặc CONTRACT)",
        )

    new_id = (max(t["id"] for t in FAKE_PDF_TEMPLATES) + 1) if FAKE_PDF_TEMPLATES else 1
    is_default = bool(data.get("is_default", False))

    if is_default:
        for t in FAKE_PDF_TEMPLATES:
            if str(t.get("template_type", "")).upper() == template_type:
                t["is_default"] = False

    now_iso = datetime.now().isoformat()
    new_tmpl = {
        "id": new_id,
        "name": name,
        "template_type": template_type,
        "is_default": is_default,
        "is_active": bool(data.get("is_active", True)),
        "company_name": data.get("company_name") or "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM",
        "company_tax_code": data.get("company_tax_code") or "0109888999",
        "company_address": data.get("company_address") or "Hà Nội",
        "company_phone": data.get("company_phone") or "1900 6868",
        "company_email": data.get("company_email") or "sales@crmvietnam.vn",
        "company_website": data.get("company_website") or "https://crmvietnam.vn",
        "company_bank_info": data.get("company_bank_info"),
        "logo_url": data.get("logo_url"),
        "primary_color": data.get("primary_color") or "#1E40AF",
        "secondary_color": data.get("secondary_color") or "#F3F4F6",
        "header_title": data.get("header_title") or ("BÁO GIÁ THƯƠNG MẠI" if template_type == "QUOTE" else "HỢP ĐỒNG KINH TẾ"),
        "terms_and_conditions": data.get("terms_and_conditions") or "",
        "footer_text": data.get("footer_text") or "",
        "signature_customer_label": data.get("signature_customer_label") or "ĐẠI DIỆN KHÁCH HÀNG",
        "signature_company_label": data.get("signature_company_label") or "ĐẠI DIỆN CÔNG TY",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    FAKE_PDF_TEMPLATES.append(new_tmpl)

    if db is not None:
        try:
            if is_default:
                db.query(PDFTemplateModel).filter(
                    PDFTemplateModel.template_type == template_type
                ).update({"is_default": False})

            db_tmpl = PDFTemplateModel(**{k: v for k, v in new_tmpl.items() if k != "id"})
            db.add(db_tmpl)
            db.commit()
            db.refresh(db_tmpl)
            new_tmpl["id"] = db_tmpl.id
        except Exception:
            if db:
                db.rollback()

    return new_tmpl


def update_template(template_id: int, data: dict, db: Optional[Session] = None) -> Dict[str, Any]:
    """Cập nhật thông tin cấu hình mẫu PDF (AC 2)."""
    tmpl = get_template_by_id(template_id, db=db)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mẫu PDF để cập nhật",
        )

    t_type = (data.get("template_type") or tmpl.get("template_type", "QUOTE")).upper().strip()

    if data.get("is_default"):
        for t in FAKE_PDF_TEMPLATES:
            if str(t.get("template_type", "")).upper() == t_type and t.get("id") != template_id:
                t["is_default"] = False

    for k, v in data.items():
        if v is not None and k not in ("id", "created_at"):
            tmpl[k] = v

    tmpl["updated_at"] = datetime.now().isoformat()

    if db is not None:
        try:
            db_tmpl = db.query(PDFTemplateModel).filter(PDFTemplateModel.id == template_id).first()
            if db_tmpl:
                if data.get("is_default"):
                    db.query(PDFTemplateModel).filter(
                        PDFTemplateModel.template_type == t_type,
                        PDFTemplateModel.id != template_id,
                    ).update({"is_default": False})

                for k, v in data.items():
                    if v is not None and hasattr(db_tmpl, k):
                        setattr(db_tmpl, k, v)
                db.commit()
        except Exception:
            if db:
                db.rollback()

    return tmpl


def set_default_template(template_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
    """Thiết lập một mẫu làm mặc định cho loại tài liệu của nó."""
    tmpl = get_template_by_id(template_id, db=db)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mẫu PDF",
        )

    t_type = str(tmpl.get("template_type", "QUOTE")).upper()
    for t in FAKE_PDF_TEMPLATES:
        if str(t.get("template_type", "")).upper() == t_type:
            t["is_default"] = (t.get("id") == template_id)

    tmpl["is_default"] = True
    tmpl["updated_at"] = datetime.now().isoformat()

    if db is not None:
        try:
            db.query(PDFTemplateModel).filter(
                PDFTemplateModel.template_type == t_type
            ).update({"is_default": False})
            db.query(PDFTemplateModel).filter(
                PDFTemplateModel.id == template_id
            ).update({"is_default": True})
            db.commit()
        except Exception:
            if db:
                db.rollback()

    return tmpl


def delete_template(template_id: int, db: Optional[Session] = None) -> bool:
    """Xóa mẫu cấu hình PDF (AC 2). Chặn xóa mẫu đang là mặc định."""
    global FAKE_PDF_TEMPLATES
    tmpl = get_template_by_id(template_id, db=db)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mẫu PDF để xóa",
        )

    if tmpl.get("is_default"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa mẫu đang được thiết lập làm mặc định. Vui lòng đặt mẫu khác làm mặc định trước khi xóa.",
        )

    FAKE_PDF_TEMPLATES = [t for t in FAKE_PDF_TEMPLATES if t.get("id") != template_id]

    if db is not None:
        try:
            db.query(PDFTemplateModel).filter(PDFTemplateModel.id == template_id).delete()
            db.commit()
        except Exception:
            if db:
                db.rollback()

    return True
