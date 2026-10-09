"""
Lead API Router for S4-02 & S4-04:
- Manual lead creation & CRUD with mandatory source (S4-02)
- Excel import template, preview with row-level validation, commit (S4-02)
- Duplicate detection by email, phone, company (S4-04)
- Attach to existing customer (S4-04)
- Lead merge preserving activity history and snapshot (S4-04)
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.core.dependencies import get_current_user
from app.schemas.lead import (
    LeadAttachToCustomerRequest,
    LeadCreate,
    LeadDuplicateCheckResponse,
    LeadImportCommitRequest,
    LeadImportCommitResponse,
    LeadImportPreviewResponse,
    LeadListResponse,
    LeadMergePreviewResponse,
    LeadMergeRequest,
    LeadResponse,
    LeadUpdate,
)
from app.services import lead_service

router = APIRouter(
    prefix="/leads",
    tags=["Leads"],
)


@router.get("", response_model=LeadListResponse)
def get_leads_list(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: NEW, CONTACTED, QUALIFIED, UNQUALIFIED, CONVERTED"),
    source: Optional[str] = Query(None, description="Lọc theo nguồn lead"),
    campaign_id: Optional[int] = Query(None, description="Lọc theo ID chiến dịch"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên, sđt, email, công ty"),
    include_merged: bool = Query(False, description="Bao gồm cả lead đã gộp"),
    current_user: dict = Depends(get_current_user),
):
    """Xem danh sách lead."""
    leads = lead_service.list_leads(
        status_filter=status,
        source_filter=source,
        campaign_id=campaign_id,
        search=search,
        include_merged=include_merged,
    )
    return {
        "total": len(leads),
        "leads": leads,
    }


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_new_lead(
    payload: LeadCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-02: Nhập tay một lead từ sự kiện hoặc danh thiếp.
    Mọi lead nhập vào đều bắt buộc có nguồn.
    """
    new_lead = lead_service.create_lead(payload.model_dump(), current_user)
    return new_lead


@router.get("/import/template")
def download_lead_template(
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-02: Tải file mẫu Excel (.xlsx) chuẩn hóa để nhập hàng loạt.
    """
    content = lead_service.generate_lead_import_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=KhachHang_Lead_Template.xlsx"
        },
    )


@router.post("/import/preview", response_model=LeadImportPreviewResponse)
async def preview_lead_excel(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-02: Tải tệp Excel lên, xem trước và báo lỗi chi tiết theo từng dòng.
    Kiểm tra nguồn bắt buộc, định dạng email/SĐT, và phát hiện trùng lặp.
    """
    file_bytes = await file.read()
    preview_res = lead_service.preview_import_leads_excel(file_bytes, current_user)
    return preview_res


@router.post("/import/commit", response_model=LeadImportCommitResponse)
def commit_lead_excel_import(
    payload: LeadImportCommitRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-02: Xác nhận nhập hàng loạt vào hệ thống với tùy chọn xử lý trùng (SKIP, UPDATE, IMPORT_ANYWAY).
    """
    res = lead_service.commit_import_leads(
        rows=[r.model_dump() for r in payload.rows],
        duplicate_handling=payload.duplicate_handling.upper(),
        current_user=current_user,
    )
    return res


@router.post("/check-duplicates", response_model=LeadDuplicateCheckResponse)
def check_lead_duplicates_api(
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    exclude_lead_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-04: Kiểm tra trùng lặp theo email, số điện thoại và tên công ty trước khi tạo/nhập.
    """
    return lead_service.check_lead_duplicates(
        email=email,
        phone=phone,
        company_name=company_name,
        exclude_lead_id=exclude_lead_id,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead_detail(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem thông tin chi tiết của một Lead."""
    lead = lead_service.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead_info(
    lead_id: int,
    payload: LeadUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật thông tin Lead."""
    updated = lead_service.update_lead(lead_id, payload.model_dump(exclude_unset=True), current_user)
    return updated


@router.delete("/{lead_id}")
def delete_lead_api(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xóa Lead."""
    success = lead_service.delete_lead(lead_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id} để xóa",
        )
    return {"message": f"Đã xóa thành công lead ID {lead_id}"}


@router.get("/{lead_id}/duplicates", response_model=LeadDuplicateCheckResponse)
def get_duplicates_for_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-04: Phát hiện trùng lặp cho Lead hiện tại theo email, SĐT, tên công ty.
    Gợi ý cả khách hàng đã có trong hệ thống nếu trùng.
    """
    return lead_service.find_lead_duplicates(lead_id)


@router.post("/{lead_id}/attach-to-customer", response_model=LeadResponse)
def attach_lead_to_customer_api(
    lead_id: int,
    payload: LeadAttachToCustomerRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-04: Lead trùng với khách hàng đã có được gợi ý gắn thẳng vào khách hàng đó.
    Tự động tạo Contact mới thuộc khách hàng nếu create_contact=True.
    """
    res = lead_service.attach_lead_to_customer(
        lead_id=lead_id,
        customer_id=payload.customer_id,
        create_contact=payload.create_contact,
        current_user=current_user,
    )
    return res


@router.post("/merge-preview", response_model=LeadMergePreviewResponse)
def preview_lead_merge(
    payload: LeadMergeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-04: Xem trước so sánh hai lead và các hoạt động sẽ chuyển giao trước khi gộp.
    """
    return lead_service.preview_merge_leads(payload.primary_lead_id, payload.secondary_lead_id)


@router.post("/merge", response_model=LeadResponse)
def merge_two_leads(
    payload: LeadMergeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S4-04: Gộp giữ nguyên lịch sử của cả hai bản ghi.
    - Chuyển giao toàn bộ hoạt động (Activities) sang Lead chính.
    - Lưu snapshot JSON của Lead phụ vào bảng LeadMergeHistory.
    - Đổi trạng thái Lead phụ thành MERGED để ẩn khỏi danh sách gọi.
    """
    res = lead_service.merge_leads(
        primary_id=payload.primary_lead_id,
        secondary_id=payload.secondary_lead_id,
        chosen_fields=payload.chosen_fields,
        current_user=current_user,
    )
    return res


@router.post("/{lead_id}/convert")
def convert_lead_to_opportunity_or_customer(
    lead_id: int,
    opportunity_title: Optional[str] = Query(None),
    opportunity_value: Optional[float] = Query(0.0),
    current_user: dict = Depends(get_current_user),
):
    """
    Chuyển đổi Lead thành Khách hàng & Cơ hội, kế thừa chiến dịch (campaign_id) đã sinh ra lead.
    """
    lead = lead_service.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )

    # 1. Nếu chưa có customer_id, tạo Customer mới từ Lead
    from app.services import customer_service, opportunity_service

    cust_id = lead.get("customer_id")
    if not cust_id:
        cust_payload = {
            "name": lead.get("company_name") or lead.get("name"),
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "address": lead.get("address"),
            "status": "PROSPECT",
        }
        new_cust = customer_service.create_customer(cust_payload, current_user)
        cust_id = new_cust["id"]
        lead_service.attach_lead_to_customer(lead_id, cust_id, create_contact=True, current_user=current_user)

    # 2. Tạo Opportunity kế thừa campaign_id từ Lead
    opp_title = opportunity_title or f"Cơ hội từ Lead: {lead['name']}"
    opp_data = {
        "title": opp_title,
        "value": float(opportunity_value or 0.0),
        "stage": "PROSPECTING",
        "customer_id": cust_id,
        "campaign_id": lead.get("campaign_id"),
        "lead_id": lead_id,
        "team_id": current_user.get("team_id"),
    }
    created_opp = opportunity_service.create_opportunity_record(opp_data, current_user)

    # Đổi trạng thái Lead thành CONVERTED
    lead_service.update_lead(lead_id, {"status": "CONVERTED"}, current_user)

    return {
        "message": "Chuyển đổi Lead thành công",
        "lead_id": lead_id,
        "customer_id": cust_id,
        "opportunity": created_opp,
    }
