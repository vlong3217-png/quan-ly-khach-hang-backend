from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
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
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadFormCreate,
    LeadFormEmbedCodeResponse,
    LeadFormResponse,
    LeadListResponse,
    LeadRecalculateResponse,
    LeadRejectSchema,
    LeadResponse,
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
from app.services.lead_service import (
    accept_lead,
    check_sla_violations,
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
    tags=["Web-to-Lead & Quản lý Lead (S4-01)"],
)


# ============================================================================
# 1. API PUBLIC TIẾP NHẬN LEAD TỪ BIỂU MẪU WEBSITE (KHÔNG YÊU CẦU TOKEN)
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
    """
    AC S4-01:
    - Biểu mẫu gồm: họ tên, email, số điện thoại, công ty, nhu cầu quan tâm.
    - Có chống spam bot qua honeypot và giới hạn tần suất (Rate limit) theo địa chỉ IP.
    - Gửi thành công tạo lead ở trạng thái 'Mới' (NEW) và gắn đúng nguồn của biểu mẫu.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Kiểm tra X-Forwarded-For nếu đi qua reverse proxy / load balancer
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    result = process_web_to_lead_submission(
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
def render_lead_form_iframe_endpoint(
    form_key: str,
    db: Session = Depends(get_db),
):
    """
    Phục vụ nhúng biểu mẫu qua thẻ <iframe> trên bất kỳ website nào.
    """
    form = get_lead_form_by_key(form_key, db=db)
    if not form or not form.is_active:
        return HTMLResponse(
            status_code=404,
            content="<h3>Biểu mẫu không tồn tại hoặc đã ngừng tiếp nhận thông tin.</h3>",
        )

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{form.name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 16px; background: transparent; }}
    .form-container {{ max-width: 480px; margin: 0 auto; background: #ffffff; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .form-group {{ margin-bottom: 14px; }}
    label {{ display: block; font-weight: 500; font-size: 14px; margin-bottom: 6px; color: #1e293b; }}
    input, textarea {{ width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; outline: none; }}
    input:focus, textarea:focus {{ border-color: #2563eb; ring: 2px solid #93c5fd; }}
    button {{ width: 100%; padding: 12px; font-size: 15px; font-weight: 600; color: #ffffff; background: #2563eb; border: none; border-radius: 6px; cursor: pointer; transition: background 0.2s; }}
    button:hover {{ background: #1d4ed8; }}
    .msg-box {{ display: none; padding: 12px; border-radius: 6px; font-size: 14px; margin-top: 12px; }}
    .msg-success {{ background: #dcfce7; color: #166534; }}
    .msg-error {{ background: #fee2e2; color: #991b1b; }}
  </style>
</head>
<body>
  <div class="form-container">
    <h3 style="margin-top:0;margin-bottom:16px;color:#0f172a;">{form.name}</h3>
    <form id="leadForm">
      <div class="form-group">
        <label>Họ và tên *</label>
        <input type="text" id="full_name" required placeholder="Nguyễn Văn A" />
      </div>
      <div class="form-group">
        <label>Email *</label>
        <input type="email" id="email" required placeholder="email@congty.com" />
      </div>
      <div class="form-group">
        <label>Số điện thoại</label>
        <input type="tel" id="phone" placeholder="0912345678" />
      </div>
      <div class="form-group">
        <label>Công ty</label>
        <input type="text" id="company" placeholder="Công ty TNHH ABC" />
      </div>
      <div class="form-group">
        <label>Nhu cầu quan tâm</label>
        <textarea id="interest" rows="3" placeholder="Ghi chú nhu cầu cần tư vấn..."></textarea>
      </div>
      <input type="text" id="hp_website" style="display:none;" tabindex="-1" autocomplete="off" />
      <button type="submit" id="submitBtn">Gửi thông tin</button>
      <div id="msgBox" class="msg-box"></div>
    </form>
  </div>

  <script>
    document.getElementById("leadForm").addEventListener("submit", async function(e) {{
      e.preventDefault();
      const btn = document.getElementById("submitBtn");
      const msgBox = document.getElementById("msgBox");
      btn.disabled = true;
      btn.innerText = "Đang gửi...";
      msgBox.style.display = "none";

      const payload = {{
        full_name: document.getElementById("full_name").value,
        email: document.getElementById("email").value,
        phone: document.getElementById("phone").value || null,
        company: document.getElementById("company").value || null,
        interest: document.getElementById("interest").value || null,
        hp_website: document.getElementById("hp_website").value || null
      }};

      try {{
        const res = await fetch("/lead-forms/{form_key}/submit", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload)
        }});
        const data = await res.json();
        if (res.ok) {{
          msgBox.className = "msg-box msg-success";
          msgBox.innerText = data.message || "Gửi thông tin thành công!";
          msgBox.style.display = "block";
          document.getElementById("leadForm").reset();
        }} else {{
          msgBox.className = "msg-box msg-error";
          msgBox.innerText = data.detail || "Đã xảy ra lỗi, vui lòng thử lại!";
          msgBox.style.display = "block";
        }}
      }} catch (err) {{
        msgBox.className = "msg-box msg-error";
        msgBox.innerText = "Không thể kết nối đến máy chủ. Vui lòng thử lại sau.";
        msgBox.style.display = "block";
      }} finally {{
        btn.disabled = false;
        btn.innerText = "Gửi thông tin";
      }}
    }});
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


# ============================================================================
# 2. API QUẢN TRỊ CẤU HÌNH BIỂU MẪU & MÃ NHÚNG (YÊU CẦU ĐĂNG NHẬP)
# ============================================================================

@router.post(
    "/lead-forms",
    response_model=LeadFormResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo biểu mẫu Web-to-Lead và sinh mã nhúng (Nhân viên Marketing / Admin)",
)
def create_lead_form_endpoint(
    payload: LeadFormCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-01: Sinh mã nhúng cho một biểu mẫu, dán được vào website bất kỳ.
    """
    result = create_lead_form(payload=payload, user_id=current_user["id"], db=db)
    return result


@router.get(
    "/lead-forms",
    response_model=List[LeadFormResponse],
    summary="Xem danh sách biểu mẫu Web-to-Lead đã tạo",
)
def list_lead_forms_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_lead_forms(db=db)


@router.get(
    "/lead-forms/{form_key}/embed-code",
    response_model=LeadFormEmbedCodeResponse,
    summary="Lấy chi tiết mã nhúng (Script tag, iframe, raw HTML) để dán vào website",
)
def get_lead_form_embed_code_endpoint(
    form_key: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-01: Sinh mã nhúng cho biểu mẫu dán được vào website bất kỳ.
    Trả về:
    - embed_script_tag: Đoạn JavaScript nhúng trực tiếp.
    - embed_iframe_code: Thẻ <iframe> nhúng độc lập.
    - embed_html_form: Khung HTML thuần kèm API endpoint.
    """
    base_url = str(request.base_url).rstrip("/")
    return get_lead_form_embed_code(form_key=form_key, base_url=base_url, db=db)


# ============================================================================
# 3. API QUẢN LÝ VÀ CHẤM ĐIỂM LEAD (LEAD MANAGEMENT & SCORING - S4-05)
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
    """AC S4-05: Xem ngưỡng điểm Nóng (HOT), Ấm (WARM), Lạnh (COLD)."""
    return get_or_create_scoring_settings(db=db)


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
    """
    AC S4-05: Giám đốc kinh doanh / Trưởng nhóm cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh.
    """
    return update_scoring_settings(
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
    active_only: bool = Query(False, description="Chỉ lấy các tiêu chí đang kích hoạt"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AC S4-05: Khai báo tiêu chí và số điểm."""
    return list_scoring_rules(active_only=active_only, db=db)


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
    """
    AC S4-05: Giám đốc kinh doanh khai báo tiêu chí và số điểm.
    Hỗ trợ các trường: industry, company_size, source, budget, job_title, phone, email, interest, city.
    Toán tử: EQUALS, NOT_EQUALS, CONTAINS, NOT_EMPTY, IS_EMPTY, GREATER_THAN, LESS_THAN, IN.
    """
    return create_scoring_rule(payload=payload, db=db)


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
    return update_scoring_rule(rule_id=rule_id, payload=payload, db=db)


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
    success = delete_scoring_rule(rule_id=rule_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tiêu chí chấm điểm với ID {rule_id}",
        )
    return None


@router.post(
    "/leads/recalculate-all-scores",
    summary="Tính lại điểm số cho toàn bộ khách hàng tiềm năng (S4-05)",
)
def recalculate_all_scores_endpoint(
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """AC S4-05: Tự động tính lại điểm cho toàn bộ lead khi quy tắc hoặc ngưỡng thay đổi."""
    return recalculate_all_leads_scores(db=db)


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
    """AC S4-05: Tự động tính lại điểm khi thông tin lead thay đổi."""
    return recalculate_single_lead_score(lead_id=lead_id, db=db)


@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="Xem danh sách khách hàng tiềm năng (Leads) trong hệ thống",
)
def list_leads_endpoint(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: NEW, IN_PROGRESS, QUALIFIED, DISQUALIFIED"),
    source: Optional[str] = Query(None, description="Lọc theo nguồn: Website Form, Google Ads, Hội thảo..."),
    grade: Optional[str] = Query(None, description="Lọc theo phân loại: HOT, WARM, COLD (S4-05)"),
    min_score: Optional[int] = Query(None, description="Lọc theo điểm tối thiểu (S4-05)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email, SĐT, công ty"),
    sort_by: Optional[str] = Query(None, description="Sắp xếp: score_desc (ưu tiên lead tiềm năng nhất), score_asc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-01 & S4-05:
    - Điểm chỉ dùng để ưu tiên, không tự động loại lead.
    - Nhân viên có thể lọc và sắp xếp theo điểm (score_desc) để gọi những lead có khả năng nhất trước.
    """
    total, items = list_leads(
        status_filter=status,
        source_filter=source,
        grade_filter=grade,
        min_score=min_score,
        search=search,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
        db=db,
    )
    return {
        "total": total,
        "items": items,
    }


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo mới khách hàng tiềm năng nội bộ từ CRM (S4-05)",
)
def create_crm_lead_endpoint(
    payload: LeadCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tạo lead nội bộ và tự động tính điểm theo tiêu chí (S4-05)."""
    return create_crm_lead(payload=payload, current_user=current_user, db=db)


@router.put(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Cập nhật thông tin khách hàng tiềm năng (S4-05)",
)
def update_crm_lead_endpoint(
    lead_id: int,
    payload: LeadUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-05: Tự động tính lại điểm khi thông tin lead thay đổi.
    """
    return update_crm_lead(lead_id=lead_id, payload=payload, db=db)




# ============================================================================
# 4. API CẤU HÌNH VÀ PHÂN BỔ LEAD TỰ ĐỘNG (LEAD ALLOCATION - S4-06)
# ============================================================================

@router.get(
    "/leads/allocation-rules",
    response_model=List[LeadAllocationRuleResponse],
    summary="Xem danh sách quy tắc phân bổ lead tự động (S4-06)",
)
def list_allocation_rules_endpoint(
    active_only: bool = Query(False, description="Chỉ lấy các quy tắc đang kích hoạt"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-06: Danh sách quy tắc phân bổ sắp xếp theo thứ tự ưu tiên (priority).
    """
    rules = list_allocation_rules(active_only=active_only, db=db)
    result = []
    for r in rules:
        try:
            assignee_ids = json.loads(r.assignee_user_ids)
        except Exception:
            assignee_ids = []
        result.append(
            LeadAllocationRuleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                priority=r.priority,
                criterion_type=r.criterion_type,
                criterion_value=r.criterion_value,
                allocation_method=r.allocation_method,
                assignee_user_ids=assignee_ids,
                last_assigned_index=r.last_assigned_index,
                is_active=r.is_active,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return result


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
    """
    AC S4-06: Giám đốc kinh doanh cấu hình quy tắc phân bổ lead tự động:
    - Tiêu chí: theo khu vực (REGION), ngành nghề (INDUSTRY), nguồn (SOURCE) hoặc tất cả (ANY).
    - Phương thức: xoay vòng (ROUND_ROBIN), nhân viên cố định (SPECIFIC_USER), theo khu vực (REGION), ngành nghề (INDUSTRY).
    - Có thứ tự ưu tiên (priority).
    """
    r = create_allocation_rule(payload=payload, db=db)
    return LeadAllocationRuleResponse(
        id=r.id,
        name=r.name,
        description=r.description,
        priority=r.priority,
        criterion_type=r.criterion_type,
        criterion_value=r.criterion_value,
        allocation_method=r.allocation_method,
        assignee_user_ids=payload.assignee_user_ids,
        last_assigned_index=r.last_assigned_index,
        is_active=r.is_active,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


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
    r = update_allocation_rule(rule_id=rule_id, payload=payload, db=db)
    try:
        assignee_ids = json.loads(r.assignee_user_ids)
    except Exception:
        assignee_ids = []
    return LeadAllocationRuleResponse(
        id=r.id,
        name=r.name,
        description=r.description,
        priority=r.priority,
        criterion_type=r.criterion_type,
        criterion_value=r.criterion_value,
        allocation_method=r.allocation_method,
        assignee_user_ids=assignee_ids,
        last_assigned_index=r.last_assigned_index,
        is_active=r.is_active,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


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
    success = delete_allocation_rule(rule_id=rule_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc phân bổ với ID {rule_id}",
        )
    return None


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
    """
    AC S4-06: Lead không khớp quy tắc vào hàng chờ để trưởng nhóm phân tay.
    """
    total, items = list_allocation_queue(skip=skip, limit=limit, db=db)
    return {
        "total": total,
        "items": items,
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
    """
    AC S4-06: Trưởng nhóm phân bổ lead thủ công kèm ghi chú và người phụ trách.
    """
    return manual_assign_lead(
        lead_id=lead_id,
        owner_id=payload.owner_id,
        note=payload.note,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/leads/allocation/run-background",
    response_model=BatchAllocationRunResponse,
    summary="Chạy nền quy trình phân bổ tự động cho hàng chờ (S4-06)",
)
def run_background_allocation_endpoint(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    AC S4-06: Phân bổ chạy nền và hoàn tất trong vòng 5 phút.
    Kích hoạt quét toàn bộ hàng chờ để khớp quy tắc phân bổ tự động.
    """
    result = run_batch_lead_allocation(db=db)
    return result


@router.get(
    "/leads/allocation-logs",
    response_model=List[LeadAllocationLogResponse],
    summary="Xem lịch sử / nhật ký phân bổ lead (S4-06)",
)
def list_allocation_logs_endpoint(
    lead_id: Optional[int] = Query(None, description="Lọc theo lead ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    total, items = list_allocation_logs(lead_id=lead_id, skip=skip, limit=limit, db=db)
    return items


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
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )
    return lead


# ============================================================================
# 5. API CHUYỂN ĐỔI LEAD SANG KHÁCH HÀNG & CƠ HỘI (LEAD CONVERSION - S4-08)
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





