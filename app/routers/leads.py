from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.lead import (
    LeadFormCreate,
    LeadFormEmbedCodeResponse,
    LeadFormResponse,
    LeadListResponse,
    LeadResponse,
    WebToLeadSubmitRequest,
    WebToLeadSubmitResponse,
)
from app.services.lead_service import (
    create_lead_form,
    get_lead_form_by_key,
    get_lead_form_embed_code,
    get_lead_by_id,
    list_lead_forms,
    list_leads,
    process_web_to_lead_submission,
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
# 3. API XEM DANH SÁCH LEAD THU THẬP ĐƯỢC (CRM LEADS)
# ============================================================================

@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="Xem danh sách khách hàng tiềm năng (Leads) trong hệ thống",
)
def list_leads_endpoint(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: NEW, IN_PROGRESS, QUALIFIED, DISQUALIFIED"),
    source: Optional[str] = Query(None, description="Lọc theo nguồn: Website Form, Google Ads, Hội thảo..."),
    search: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email, SĐT, công ty"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AC S4-01: Gửi thành công tạo lead ở trạng thái 'Mới' (NEW) và gắn đúng nguồn của biểu mẫu.
    Nhân viên Marketing và Sales có thể xem danh sách lead thu thập được.
    """
    total, items = list_leads(
        status_filter=status,
        source_filter=source,
        search=search,
        skip=skip,
        limit=limit,
        db=db,
    )
    return {
        "total": total,
        "items": items,
    }


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
