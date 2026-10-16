"""
PDF Templates API Router (S7-05: Dynamic PDF Templates Management).
Allows managing branded PDF templates for Quotes and Contracts without hardcoding.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.schemas.pdf_template import (
    PDFTemplateCreate,
    PDFTemplateListResponse,
    PDFTemplateResponse,
    PDFTemplateUpdate,
)
from app.services.pdf_template_service import (
    create_template,
    delete_template,
    get_all_templates,
    get_template_by_id,
    set_default_template,
    update_template,
)
from app.services.pdf_generator_service import generate_quote_pdf, generate_contract_pdf

router = APIRouter(
    prefix="/pdf-templates",
    tags=["PDF Templates"],
)


@router.get("", response_model=PDFTemplateListResponse)
def list_pdf_templates(
    template_type: Optional[str] = Query(None, description="Lọc theo loại mẫu: QUOTE (Báo giá) hoặc CONTRACT (Hợp đồng)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên mẫu hoặc tên công ty"),
    active_only: bool = Query(True, description="Chỉ lấy các mẫu đang kích hoạt"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các mẫu PDF có thể cấu hình trong hệ thống (S7-05 AC 2)."""
    templates = get_all_templates(
        template_type=template_type,
        search=search,
        active_only=active_only,
        db=db,
    )
    return {
        "total": len(templates),
        "templates": templates,
    }


@router.get("/{template_id}", response_model=PDFTemplateResponse)
def get_pdf_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xem chi tiết cấu hình nhận diện thương hiệu của một mẫu PDF."""
    tmpl = get_template_by_id(template_id, db=db)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mẫu PDF",
        )
    return tmpl


@router.post("", response_model=PDFTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_pdf_template(
    payload: PDFTemplateCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"], detail="Chỉ Quản trị viên hoặc Quản lý mới có quyền tạo mẫu PDF")),
    db: Session = Depends(get_db),
):
    """Tạo mới một mẫu cấu hình PDF nhận diện thương hiệu (S7-05 AC 2)."""
    return create_template(payload.model_dump(), db=db)


@router.put("/{template_id}", response_model=PDFTemplateResponse)
def update_pdf_template(
    template_id: int,
    payload: PDFTemplateUpdate,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"], detail="Chỉ Quản trị viên hoặc Quản lý mới có quyền chỉnh sửa mẫu PDF")),
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin nhận diện thương hiệu, màu sắc, điều khoản của mẫu PDF."""
    update_data = payload.model_dump(exclude_unset=True)
    return update_template(template_id, update_data, db=db)


@router.post("/{template_id}/set-default", response_model=PDFTemplateResponse)
def set_default_pdf_template(
    template_id: int,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"], detail="Chỉ Quản trị viên hoặc Quản lý mới có quyền đổi mẫu mặc định")),
    db: Session = Depends(get_db),
):
    """Thiết lập một mẫu làm mẫu mặc định khi xuất PDF."""
    return set_default_template(template_id, db=db)


@router.delete("/{template_id}")
def delete_pdf_template(
    template_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá mẫu PDF")),
    db: Session = Depends(get_db),
):
    """Xóa mẫu cấu hình PDF (không cho xóa mẫu đang là mặc định)."""
    delete_template(template_id, db=db)
    return {"message": f"Đã xóa mẫu PDF ID {template_id}"}


@router.get("/{template_id}/preview")
def preview_pdf_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xem trước mẫu PDF với dữ liệu mẫu (mock data)."""
    tmpl = get_template_by_id(template_id, db=db)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mẫu PDF để xem trước",
        )

    t_type = str(tmpl.get("template_type", "QUOTE")).upper()
    sample_items = [
        {
            "product_id": 1,
            "product_code": "PROD-SAMPLE-01",
            "product_name": "Phần mềm Quản lý Khách hàng Doanh nghiệp (CRM)",
            "unit": "Gói bản quyền",
            "quantity": 1,
            "unit_price": 50000000.0,
            "discount_type": "PERCENT",
            "discount_value": 10.0,
            "line_discount_amount": 5000000.0,
            "vat_rate": 10,
            "line_total": 49500000.0,
        },
        {
            "product_id": 2,
            "product_code": "SRV-SAMPLE-02",
            "product_name": "Dịch vụ Đào tạo chuyển giao & Hỗ trợ kỹ thuật 24/7",
            "unit": "Tháng",
            "quantity": 3,
            "unit_price": 3000000.0,
            "discount_type": "PERCENT",
            "discount_value": 0.0,
            "line_discount_amount": 0.0,
            "vat_rate": 10,
            "line_total": 9900000.0,
        }
    ]

    if t_type == "CONTRACT":
        sample_contract = {
            "id": 999,
            "contract_number": "HD-DEMO-2026",
            "title": "Hợp đồng Cung cấp Giải pháp Phần mềm Mẫu",
            "customer_name": "CÔNG TY TNHH KHÁCH HÀNG MẪU",
            "signed_date": "2026-10-16",
            "effective_date": "2026-10-16",
            "expiration_date": "2027-10-16",
            "items": sample_items,
            "subtotal": 59000000.0,
            "total_discount_amount": 5000000.0,
            "vat_amount": 5400000.0,
            "grand_total": 59400000.0,
            "payment_terms": "Thanh toán 50% khi ký hợp đồng, 50% sau khi nghiệm thu.",
            "delivery_terms": "Triển khai trong vòng 10 ngày làm việc.",
        }
        pdf_bytes = generate_contract_pdf(sample_contract, tmpl)
        filename = f"Preview_Hop_Dong_{tmpl['id']}.pdf"
    else:
        sample_quote = {
            "id": 999,
            "quote_number": "BG-DEMO-2026",
            "title": "Báo giá Dịch vụ Phần mềm Mẫu",
            "customer_name": "CÔNG TY TNHH KHÁCH HÀNG MẪU",
            "opportunity_title": "Dự án Nâng cấp Hệ thống CRM Toàn diện",
            "status": "APPROVED",
            "valid_until": "2026-11-16",
            "items": sample_items,
            "subtotal": 59000000.0,
            "total_discount_amount": 5000000.0,
            "vat_amount": 5400000.0,
            "grand_total": 59400000.0,
            "payment_terms": "Thanh toán chuyển khoản 100% trong vòng 15 ngày.",
            "delivery_terms": "Giao hàng qua email và bàn giao tài liệu trực tiếp.",
            "created_at": "2026-10-16T08:00:00",
        }
        pdf_bytes = generate_quote_pdf(sample_quote, tmpl)
        filename = f"Preview_Bao_Gia_{tmpl['id']}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
