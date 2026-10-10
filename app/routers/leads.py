"""
Unified Lead Router:
- S4-01: Public Web-to-Lead submission & Form Embed Codes
- S4-02: Manual lead creation with mandatory source & Excel batch import with template/preview/commit
- S4-04: Duplicate check, Attach to customer, Merge leads with history preservation
- S4-05: Lead scoring rules & classification
- S4-06: Lead allocation rules & assignment
- S4-07: Lead response & SLA deadline tracking
- S4-08: Lead conversion
- S4-09: Lead filters & saved filters
"""

from datetime import datetime
import html
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user, require_roles
from app.core.security import ALGORITHM, SECRET_KEY
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

security_optional = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> Optional[dict]:
    """Lấy thông tin người dùng hiện tại nếu có Authorization header."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
from app.schemas.lead import (
    BatchAllocationRunResponse,
    LeadAllocationLogResponse,
    LeadAllocationRuleCreate,
    LeadAllocationRuleResponse,
    LeadAllocationRuleUpdate,
    LeadAttachToCustomerRequest,
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadDuplicateCheckResponse,
    LeadFormCreate,
    LeadFormEmbedCodeResponse,
    LeadFormResponse,
    LeadImportCommitRequest,
    LeadImportCommitResponse,
    LeadImportPreviewResponse,
    LeadListResponse,
    LeadMergePreviewResponse,
    LeadMergeRequest,
    LeadRecalculateResponse,
    LeadRejectSchema,
    LeadResponse,
    LeadSavedFilterCreate,
    LeadSavedFilterResponse,
    LeadScoringRuleCreate,
    LeadScoringRuleResponse,
    LeadScoringRuleUpdate,
    LeadScoringSettingResponse,
    LeadScoringSettingUpdate,
    LeadUpdate,
    ManualAssignRequest,
    WebToLeadSubmitRequest,
    WebToLeadSubmitResponse,
)
from app.services import lead_service
from app.services.lead_service import (
    accept_lead,
    check_sla_violations,
    create_lead_saved_filter,
    delete_lead_saved_filter,
    get_lead_saved_filter_by_id,
    list_lead_saved_filters,
    reject_lead,
    convert_lead,
    create_allocation_rule,
    create_crm_lead,
    create_lead_form,
    create_scoring_rule,
    delete_allocation_rule,
    delete_scoring_rule,
    get_allocation_rule_by_id,
    get_lead_by_id,
    get_lead_form_by_key,
    get_lead_form_embed_code,
    get_or_create_scoring_settings,
    get_scoring_rule_by_id,
    list_allocation_logs,
    list_allocation_queue,
    list_allocation_rules,
    list_lead_forms,
    list_leads,
    list_scoring_rules,
    manual_assign_lead,
    process_web_to_lead_submission,
    recalculate_all_leads_scores,
    recalculate_single_lead_score,
    run_batch_lead_allocation,
    update_allocation_rule,
    update_crm_lead,
    update_scoring_rule,
    update_scoring_settings,
)

router = APIRouter(
    tags=["Leads"],
)


# ============================================================================
# 1. API PUBLIC TIẾP NHẬN LEAD TỪ BIỂU MẪU WEBSITE (S4-01)
# ============================================================================

@router.post(
    "/lead-forms/{form_key}/submit",
    response_model=WebToLeadSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nộp dữ liệu lead từ biểu mẫu website nhúng (Public Web-to-Lead)",
)
def submit_web_to_lead_endpoint(
    form_key: str,
    payload: WebToLeadSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    result = lead_service.process_web_to_lead_submission(
        form_key=form_key,
        payload=payload,
        client_ip=client_ip,
        db=db,
    )
    return result


@router.get(
    "/lead-forms/{form_key}/render",
    response_class=HTMLResponse,
    summary="Hiển thị trang giao diện biểu mẫu độc lập để nhúng iframe",
)
def render_lead_form_page(
    form_key: str,
    request: Request,
    db: Session = Depends(get_db),
):
    form = lead_service.get_lead_form_by_key(form_key, db=db)
    if not form or not form.is_active:
        return HTMLResponse("<h3>Biểu mẫu không khả dụng hoặc đã bị tắt.</h3>", status_code=404)

    base_url = str(request.base_url).rstrip("/")
    endpoint = f"{base_url}/lead-forms/{form.form_key}/submit"

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(form.name)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px; background: #f8fafc; }}
    .form-card {{ max-width: 480px; margin: 0 auto; background: #fff; padding: 24px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    h3 {{ margin-top: 0; color: #1e293b; }}
    .form-group {{ margin-bottom: 14px; }}
    label {{ display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px; color: #475569; }}
    input, textarea {{ width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px; }}
    button {{ width: 100%; padding: 10px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer; }}
    button:hover {{ background: #1d4ed8; }}
  </style>
</head>
<body>
  <div class="form-card">
    <h3>{html.escape(form.name)}</h3>
    <form action="{endpoint}" method="POST">
      <div class="form-group"><label>Họ và tên *</label><input type="text" id="full_name" name="full_name" required></div>
      <div class="form-group"><label>Email *</label><input type="email" id="email" name="email" required></div>
      <div class="form-group"><label>Số điện thoại</label><input type="tel" id="phone" name="phone"></div>
      <div class="form-group"><label>Công ty</label><input type="text" id="company" name="company"></div>
      <div class="form-group"><label>Nhu cầu quan tâm</label><textarea id="interest" name="interest" rows="3"></textarea></div>
      <input type="text" name="hp_website" style="display:none;" tabindex="-1" autocomplete="off">
      <button type="submit">Gửi thông tin</button>
    </form>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@router.post(
    "/lead-forms",
    response_model=LeadFormResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo biểu mẫu Web-to-Lead và sinh mã nhúng (S4-01)",
)
def create_lead_form_endpoint(
    payload: LeadFormCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER", "USER"])),
    db: Session = Depends(get_db),
):
    user_id = current_user.get("id")
    return lead_service.create_lead_form(payload=payload, user_id=user_id, db=db)


@router.get(
    "/lead-forms",
    response_model=List[LeadFormResponse],
    summary="Xem danh sách biểu mẫu Web-to-Lead đã tạo (S4-01)",
)
def list_lead_forms_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.list_lead_forms(db=db)


@router.get(
    "/lead-forms/{form_key}/embed-code",
    response_model=LeadFormEmbedCodeResponse,
    summary="Lấy chi tiết mã nhúng (S4-01)",
)
def get_lead_form_embed_code_endpoint(
    form_key: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url).rstrip("/")
    return lead_service.get_lead_form_embed_code(form_key=form_key, base_url=base_url, db=db)


# ============================================================================
# 2. CẤU HÌNH VÀ TÍNH ĐIỂM LEAD (S4-05)
# ============================================================================

@router.get(
    "/leads/scoring-settings",
    response_model=LeadScoringSettingResponse,
    summary="Xem cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh (S4-05)",
)
def get_scoring_settings_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.get_or_create_scoring_settings(db=db)


@router.put(
    "/leads/scoring-settings",
    response_model=LeadScoringSettingResponse,
    summary="Cập nhật cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh (S4-05)",
)
def update_scoring_settings_endpoint(
    payload: LeadScoringSettingUpdate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return lead_service.update_scoring_settings(
        hot_threshold=payload.hot_threshold,
        warm_threshold=payload.warm_threshold,
        db=db,
    )


@router.get(
    "/leads/scoring-rules",
    response_model=List[LeadScoringRuleResponse],
    summary="Xem danh sách các tiêu chí chấm điểm lead (S4-05)",
)
def list_scoring_rules_endpoint(
    active_only: bool = Query(False, description="Chỉ lấy các quy tắc đang active"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.list_scoring_rules(active_only=active_only, db=db)


@router.post(
    "/leads/scoring-rules",
    response_model=LeadScoringRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Khai báo tiêu chí chấm điểm mới (S4-05)",
)
def create_scoring_rule_endpoint(
    payload: LeadScoringRuleCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return lead_service.create_scoring_rule(payload=payload, db=db)


@router.put(
    "/leads/scoring-rules/{rule_id}",
    response_model=LeadScoringRuleResponse,
    summary="Chỉnh sửa tiêu chí chấm điểm (S4-05)",
)
def update_scoring_rule_endpoint(
    rule_id: int,
    payload: LeadScoringRuleUpdate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return lead_service.update_scoring_rule(rule_id=rule_id, payload=payload, db=db)


@router.delete(
    "/leads/scoring-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa tiêu chí chấm điểm (S4-05)",
)
def delete_scoring_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    success = lead_service.delete_scoring_rule(rule_id=rule_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tiêu chí chấm điểm với ID {rule_id}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/leads/recalculate-all-scores",
    summary="Tính lại điểm số cho toàn bộ khách hàng tiềm năng (S4-05)",
)
def recalculate_all_scores_endpoint(
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return lead_service.recalculate_all_leads_scores(db=db)


@router.post(
    "/leads/{lead_id}/recalculate-score",
    response_model=LeadRecalculateResponse,
    summary="Tính lại điểm và phân loại Nóng/Ấm/Lạnh cho một lead (S4-05)",
)
def recalculate_single_score_endpoint(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.recalculate_single_lead_score(lead_id=lead_id, db=db)


# ============================================================================
# 3. EXCEL IMPORT & TEMPLATE (S4-02)
# ============================================================================

@router.get(
    "/leads/import/template",
    summary="Tải file mẫu Excel (.xlsx) để nhập lead hàng loạt (S4-02)",
)
def download_lead_template(
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    content = lead_service.generate_lead_import_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=Mau_Nhap_Lead_S4_02.xlsx"
        },
    )


@router.post(
    "/leads/import/preview",
    response_model=LeadImportPreviewResponse,
    summary="Upload Excel, xem trước và báo lỗi chi tiết theo từng dòng (S4-02)",
)
async def preview_lead_excel(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    file_bytes = await file.read()
    return lead_service.preview_import_leads_excel(file_bytes, current_user)


@router.post(
    "/leads/import/commit",
    response_model=LeadImportCommitResponse,
    summary="Xác nhận lưu các dòng hợp lệ vào hệ thống (S4-02)",
)
def commit_lead_excel_import(
    payload: LeadImportCommitRequest,
    current_user: dict = Depends(get_current_user),
):
    return lead_service.commit_import_leads(
        rows=[r.model_dump() for r in payload.rows],
        duplicate_handling=payload.duplicate_handling.upper(),
        current_user=current_user,
    )


# ============================================================================
# 4. DUPLICATE CHECK, ATTACH TO CUSTOMER, MERGE (S4-04)
# ============================================================================

@router.post(
    "/leads/check-duplicates",
    response_model=LeadDuplicateCheckResponse,
    summary="Kiểm tra trùng lặp email, SĐT, công ty trước khi tạo/nhập (S4-04)",
)
def check_lead_duplicates_api(
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    exclude_lead_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.check_lead_duplicates(
        email=email,
        phone=phone,
        company_name=company_name,
        exclude_lead_id=exclude_lead_id,
        db=db,
    )


@router.get(
    "/leads/{lead_id}/duplicates",
    response_model=LeadDuplicateCheckResponse,
    summary="Phát hiện trùng lặp cho lead hiện tại và gợi ý khách hàng (S4-04)",
)
def get_duplicates_for_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.find_lead_duplicates(lead_id, db=db)


@router.post(
    "/leads/{lead_id}/attach-to-customer",
    response_model=LeadResponse,
    summary="Gợi ý & gắn lead vào khách hàng đã có trong hệ thống (S4-04)",
)
def attach_lead_to_customer_api(
    lead_id: int,
    payload: LeadAttachToCustomerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.attach_lead_to_customer(
        lead_id=lead_id,
        customer_id=payload.customer_id,
        create_contact=payload.create_contact,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/leads/merge-preview",
    response_model=LeadMergePreviewResponse,
    summary="Xem trước so sánh và hoạt động trước khi gộp 2 lead (S4-04)",
)
def preview_lead_merge(
    payload: LeadMergeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.preview_merge_leads(
        primary_id=payload.primary_lead_id,
        secondary_id=payload.secondary_lead_id,
        db=db,
    )


@router.post(
    "/leads/merge",
    response_model=LeadResponse,
    summary="Gộp 2 lead giữ nguyên lịch sử hoạt động và lưu snapshot (S4-04)",
)
def merge_two_leads(
    payload: LeadMergeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lead_service.merge_leads(
        primary_id=payload.primary_lead_id,
        secondary_id=payload.secondary_lead_id,
        chosen_fields=payload.chosen_fields,
        current_user=current_user,
        db=db,
    )





# ============================================================================
# 5. QUẢN LÝ DANH SÁCH LEAD (CRM LEADS - S4-02)
# ============================================================================

@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="Xem danh sách khách hàng tiềm năng (Leads)",
)
def list_leads_endpoint(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: NEW, IN_PROGRESS, QUALIFIED, DISQUALIFIED"),
    source: Optional[str] = Query(None, description="Lọc theo nguồn: Website Form, Google Ads, Hội thảo..."),
    grade: Optional[str] = Query(None, description="Lọc theo phân loại: HOT, WARM, COLD (S4-05)"),
    campaign_id: Optional[int] = Query(None, description="Lọc theo ID chiến dịch (S4-03)"),
    min_score: Optional[int] = Query(None, description="Lọc theo điểm tối thiểu (S4-05)"),
    owner_id: Optional[int] = Query(None, description="Lọc theo người phụ trách (S4-09)"),
    assigned_to: Optional[int] = Query(None, description="Lọc theo ID người được phân bổ (S4-09)"),
    is_overdue_sla: Optional[bool] = Query(None, description="Lọc theo lead quá hạn phản hồi SLA (S4-09)"),
    start_date: Optional[str] = Query(None, description="Khoảng thời gian: từ ngày (ISO format hoặc YYYY-MM-DD) (S4-09)"),
    end_date: Optional[str] = Query(None, description="Khoảng thời gian: đến ngày (ISO format hoặc YYYY-MM-DD) (S4-09)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email, SĐT, công ty"),
    sort_by: Optional[str] = Query(None, description="Sắp xếp: score_desc, score_asc, created_at_desc, created_at_asc, sla_deadline_asc"),
    include_merged: bool = Query(False, description="Bao gồm cả lead đã gộp (S4-04)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-09:
    - Danh sách lead với bộ lọc đa năng: trạng thái, nguồn, phân loại Nóng/Ấm/Lạnh, người phụ trách, khoảng thời gian.
    - Nhận diện nổi bật các lead quá SLA phản hồi (is_overdue_sla).
    - Áp dụng phạm vi dữ liệu Scope RBAC: Sales mở máy buổi sáng biết ngay hôm nay cần gọi ai.
    """
    parsed_start_date: Optional[datetime] = None
    if start_date:
        try:
            # Hỗ trợ cả trường hợp dấu + bị thay thế thành space trong query URL
            clean_start = start_date.replace(" ", "+")
            parsed_start_date = datetime.fromisoformat(clean_start)
        except Exception:
            try:
                parsed_start_date = datetime.strptime(start_date[:10], "%Y-%m-%d")
            except Exception:
                pass

    parsed_end_date: Optional[datetime] = None
    if end_date:
        try:
            clean_end = end_date.replace(" ", "+")
            parsed_end_date = datetime.fromisoformat(clean_end)
        except Exception:
            try:
                parsed_end_date = datetime.strptime(end_date[:10], "%Y-%m-%d")
            except Exception:
                pass

    total, items = lead_service.list_leads(
        status_filter=status,
        source_filter=source,
        grade_filter=grade,
        campaign_id=campaign_id,
        min_score=min_score,
        owner_id=owner_id,
        assigned_to=assigned_to,
        is_overdue_sla=is_overdue_sla,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        search=search,
        sort_by=sort_by,
        include_merged=include_merged,
        skip=skip,
        limit=limit,
        current_user=current_user,
        db=db,
    )
    serialized = [lead_service.lead_to_dict(it) for it in items]
    return {
        "total": total,
        "items": serialized,
        "leads": serialized,
    }


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo mới lead (Bắt buộc có nguồn - AC S4-02)",
)
def create_crm_lead_endpoint(
    payload: LeadCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_lead = lead_service.create_crm_lead(payload=payload, current_user=current_user, db=db)
    return lead_service.lead_to_dict(new_lead)


@router.put(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Cập nhật thông tin khách hàng tiềm năng",
)
def update_crm_lead_endpoint(
    lead_id: int,
    payload: LeadUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = lead_service.update_crm_lead(lead_id=lead_id, payload=payload, db=db, current_user=current_user)
    return lead_service.lead_to_dict(updated)


@router.delete(
    "/leads/{lead_id}",
    summary="Xóa khách hàng tiềm năng",
)
def delete_lead_endpoint(
    lead_id: int,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    success = lead_service.delete_lead(lead_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id} để xóa",
        )
    return {"message": f"Đã xóa thành công lead ID {lead_id}"}


# ============================================================================
# 6. PHÂN BỔ LEAD TỰ ĐỘNG (S4-06)
# ============================================================================

@router.get(
    "/leads/allocation-rules",
    response_model=List[LeadAllocationRuleResponse],
    summary="Xem danh sách quy tắc phân bổ lead tự động (S4-06)",
)
def list_allocation_rules_endpoint(
    active_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rules = lead_service.list_allocation_rules(active_only=active_only, db=db)
    results = []
    for r in rules:
        try:
            u_ids = json.loads(r.assignee_user_ids)
        except Exception:
            u_ids = []
        results.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "priority": r.priority,
            "criterion_type": r.criterion_type,
            "criterion_value": r.criterion_value,
            "allocation_method": r.allocation_method,
            "assignee_user_ids": u_ids,
            "last_assigned_index": r.last_assigned_index,
            "is_active": r.is_active,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        })
    return results


@router.post(
    "/leads/allocation-rules",
    response_model=LeadAllocationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo quy tắc phân bổ lead tự động mới (S4-06)",
)
def create_allocation_rule_endpoint(
    payload: LeadAllocationRuleCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    rule = lead_service.create_allocation_rule(payload=payload, db=db)
    try:
        u_ids = json.loads(rule.assignee_user_ids)
    except Exception:
        u_ids = []
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "priority": rule.priority,
        "criterion_type": rule.criterion_type,
        "criterion_value": rule.criterion_value,
        "allocation_method": rule.allocation_method,
        "assignee_user_ids": u_ids,
        "last_assigned_index": rule.last_assigned_index,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


@router.put(
    "/leads/allocation-rules/{rule_id}",
    response_model=LeadAllocationRuleResponse,
    summary="Chỉnh sửa quy tắc phân bổ lead (S4-06)",
)
def update_allocation_rule_endpoint(
    rule_id: int,
    payload: LeadAllocationRuleUpdate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    rule = lead_service.update_allocation_rule(rule_id=rule_id, payload=payload, db=db)
    try:
        u_ids = json.loads(rule.assignee_user_ids)
    except Exception:
        u_ids = []
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "priority": rule.priority,
        "criterion_type": rule.criterion_type,
        "criterion_value": rule.criterion_value,
        "allocation_method": rule.allocation_method,
        "assignee_user_ids": u_ids,
        "last_assigned_index": rule.last_assigned_index,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


@router.delete(
    "/leads/allocation-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa quy tắc phân bổ lead (S4-06)",
)
def delete_allocation_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    success = lead_service.delete_allocation_rule(rule_id=rule_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc phân bổ với ID {rule_id}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/leads/allocation-queue",
    response_model=LeadListResponse,
    summary="Xem hàng chờ phân bổ lead (S4-06)",
)
def get_allocation_queue_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    total, items = lead_service.list_allocation_queue(skip=skip, limit=limit, db=db)
    serialized = [lead_service.lead_to_dict(it) for it in items]
    return {
        "total": total,
        "items": serialized,
        "leads": serialized,
    }


@router.post(
    "/leads/{lead_id}/manual-assign",
    response_model=LeadResponse,
    summary="Trưởng nhóm phân bổ thủ công lead từ hàng chờ (S4-06)",
)
def manual_assign_lead_endpoint(
    lead_id: int,
    payload: ManualAssignRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    lead = lead_service.manual_assign_lead(
        lead_id=lead_id,
        owner_id=payload.owner_id,
        note=payload.note,
        current_user=current_user,
        db=db,
    )
    return lead_service.lead_to_dict(lead)


@router.post(
    "/leads/allocation/run-background",
    response_model=BatchAllocationRunResponse,
    summary="Chạy nền quy trình phân bổ tự động cho hàng chờ (S4-06)",
)
def run_background_allocation_endpoint(
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return lead_service.run_batch_lead_allocation(db=db)


@router.get(
    "/leads/allocation-logs",
    response_model=List[LeadAllocationLogResponse],
    summary="Xem lịch sử / nhật ký phân bổ lead (S4-06)",
)
def list_allocation_logs_endpoint(
    lead_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, items = lead_service.list_allocation_logs(lead_id=lead_id, skip=skip, limit=limit, db=db)
    return items


# ============================================================================
# BỘ LỌC LEAD ĐÃ LƯU (LEAD SAVED FILTERS - S4-09)
# (Đặt trước route /leads/{lead_id} để tránh lỗi parse path param)
# ============================================================================

@router.get(
    "/leads/saved-filters",
    response_model=List[LeadSavedFilterResponse],
    summary="Xem danh sách bộ lọc lead đã lưu của nhân viên (S4-09)",
)
def list_lead_saved_filters_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-09: Lấy danh sách các bộ lọc lead đã lưu để nhân viên mở máy buổi sáng là chọn ngay được.
    """
    filters = list_lead_saved_filters(user_id=current_user["id"], db=db)
    result = []
    for f in filters:
        try:
            criteria = json.loads(f.filter_criteria) if isinstance(f.filter_criteria, str) else f.filter_criteria
        except Exception:
            criteria = {}
        result.append(
            LeadSavedFilterResponse(
                id=f.id,
                user_id=f.user_id,
                name=f.name,
                filter_criteria=criteria,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
        )
    return result


@router.post(
    "/leads/saved-filters",
    response_model=LeadSavedFilterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lưu và đặt tên bộ lọc lead thường dùng (S4-09)",
)
def create_lead_saved_filter_endpoint(
    payload: LeadSavedFilterCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-09: Cho phép lưu và đặt tên các bộ lọc thường dùng (Ví dụ: 'Hôm nay cần gọi', 'Lead Nóng quá hạn').
    """
    saved = create_lead_saved_filter(
        user_id=current_user["id"],
        name=payload.name,
        filter_criteria=payload.filter_criteria,
        db=db,
    )
    try:
        criteria = json.loads(saved.filter_criteria) if isinstance(saved.filter_criteria, str) else saved.filter_criteria
    except Exception:
        criteria = payload.filter_criteria

    return LeadSavedFilterResponse(
        id=saved.id,
        user_id=saved.user_id,
        name=saved.name,
        filter_criteria=criteria,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


@router.delete(
    "/leads/saved-filters/{filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa bộ lọc lead đã lưu (S4-09)",
)
def delete_lead_saved_filter_endpoint(
    filter_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-09: Xóa bộ lọc lead đã lưu khi không còn nhu cầu sử dụng.
    """
    success = delete_lead_saved_filter(
        filter_id=filter_id,
        user_id=current_user["id"],
        db=db,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bộ lọc lead đã lưu với ID {filter_id}",
        )
    return None


@router.get(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Xem thông tin chi tiết một lead",
)
def get_lead_detail_endpoint(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = lead_service.get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )
    return lead_service.lead_to_dict(lead)


# ============================================================================
# 8. API CHUYỂN ĐỔI LEAD SANG KHÁCH HÀNG & CƠ HỘI (LEAD CONVERSION - S4-08)
# ============================================================================

@router.post(
    "/leads/{lead_id}/convert",
    response_model=LeadConvertResponse,
    status_code=status.HTTP_200_OK,
    summary="Chuyển đổi khách hàng tiềm năng thành Khách hàng và Cơ hội (S4-08)",
)
@router.post(
    "/api/v1/leads/{lead_id}/convert",
    response_model=LeadConvertResponse,
    status_code=status.HTTP_200_OK,
    summary="Chuyển đổi khách hàng tiềm năng thành Khách hàng và Cơ hội (S4-08)",
)
def convert_lead_endpoint(
    lead_id: int,
    payload: Optional[LeadConvertRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-08:
    - Chạy trong 1 database transaction:
      + Tạo Khách hàng (Customer) doanh nghiệp/cá nhân từ dữ liệu của Lead.
      + Tạo Người liên hệ (Contact) gắn với Customer vừa tạo.
      + Tạo Cơ hội (Opportunity) gắn với Customer và Contact đó.
    - Kế thừa toàn bộ thông tin từ Lead, không bắt người dùng nhập lại các thông tin đã có sẵn.
    - Cập nhật trạng thái Lead sang 'CONVERTED'.
    - Chặn chức năng chỉnh sửa đối với Lead đã chuyển đổi.
    - Di chuyển/liên kết toàn bộ lịch sử hoạt động (Activity/Interaction) của Lead sang Customer/Opportunity mới.
    - Validate quyền hạn và dữ liệu chặt chẽ.
    """
    return convert_lead(
        lead_id=lead_id,
        payload=payload,
        current_user=current_user,
        db=db,
    )


# ============================================================================
# 6. API TIẾP NHẬN, TỪ CHỐI & KIỂM TRA SLA PHẢN HỒI LEAD (S4-07)
# ============================================================================

@router.post(
    "/leads/{id}/accept",
    response_model=LeadResponse,
    summary="Tiếp nhận khách hàng tiềm năng (S4-07)",
)
def accept_lead_endpoint(
    id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Task S4-07: Tiếp nhận lead
    - Chuyển trạng thái sang IN_PROGRESS.
    - Gán người phụ trách nếu chưa có.
    """
    user_id = current_user.get("id") if current_user else None
    return accept_lead(lead_id=id, user_id=user_id, db=db)


@router.post(
    "/leads/{id}/reject",
    response_model=LeadResponse,
    summary="Từ chối tiếp nhận khách hàng tiềm năng kèm lý do (S4-07)",
)
def reject_lead_endpoint(
    id: int,
    payload: LeadRejectSchema,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Task S4-07: Từ chối tiếp nhận lead
    - Bắt buộc nhập lý do (reason).
    - Chuyển trạng thái sang UNASSIGNED.
    - Gán assigned_to = None, owner_id = None.
    - Lưu lý do từ chối (rejection_reason).
    """
    user_id = current_user.get("id") if current_user else None
    return reject_lead(
        lead_id=id,
        reason=payload.reason,
        user_id=user_id,
        db=db,
    )


@router.post(
    "/leads/sla/check",
    response_model=List[LeadResponse],
    summary="Quét kiểm tra vi phạm SLA phản hồi lead (S4-07)",
)
def check_sla_endpoint(
    sla_minutes: Optional[int] = Query(None, description="Thời gian SLA tối đa tính theo phút"),
    db: Session = Depends(get_db),
):
    """Kiểm tra và cập nhật các lead vi phạm SLA phản hồi."""
    return check_sla_violations(sla_minutes=sla_minutes, db=db)
