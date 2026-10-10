import html
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import json
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.customer import Customer as CustomerModel
from app.models.contact import Contact as ContactModel, ContactCompanyHistory as ContactCompanyHistoryModel
from app.services.customer_service import FAKE_CUSTOMERS, _enrich_customer_names
from app.services.contact_service import FAKE_CONTACTS, _model_to_dict as _contact_model_to_dict
from app.services.opportunity_service import FAKE_OPPORTUNITIES
from app.services.activity_service import FAKE_ACTIVITIES
from app.models.lead import (
    Lead,
    LeadSourceConfig,
    LeadScoringRule,
    LeadScoringSetting,
    LeadAllocationRule,
    LeadAllocationLog,
    LeadSavedFilter,
)
from app.schemas.lead import (
    LeadAllocationRuleCreate,
    LeadAllocationRuleUpdate,
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadFormCreate,
    LeadFormUpdate,
    LeadScoringRuleCreate,
    LeadScoringRuleUpdate,
    LeadUpdate,
    ManualAssignRequest,
    WebToLeadSubmitRequest,
)



# Bộ nhớ tạm để rate-limit theo địa chỉ IP: ip -> list các timestamp submit gần nhất
_ip_submission_timestamps: Dict[str, List[float]] = defaultdict(list)

# Bộ nhớ tạm in-memory lưu trữ fallback nếu database chưa sẵn sàng
_fake_lead_forms_db: List[Dict[str, Any]] = []
_fake_leads_db: List[Dict[str, Any]] = []


def _check_rate_limit(ip_address: str, max_per_minute: int = 5) -> bool:
    """
    Kiểm tra giới hạn tần suất gửi theo IP (Rate limit).
    Cho phép tối đa `max_per_minute` lượt gửi trong cửa sổ 60 giây.
    """
    now = time.time()
    window = 60.0  # 60 giây

    # Lọc bỏ các timestamp cũ hơn 60s
    timestamps = [t for t in _ip_submission_timestamps[ip_address] if now - t < window]
    _ip_submission_timestamps[ip_address] = timestamps

    if len(timestamps) >= max_per_minute:
        return False

    _ip_submission_timestamps[ip_address].append(now)
    return True


def _generate_embed_snippets(form_key: str, form_name: str, base_url: str = "") -> Dict[str, str]:
    """
    Tạo các đoạn mã nhúng chuẩn (Embed Script, Iframe, HTML Form) để chèn vào website bất kỳ.
    """
    endpoint = f"{base_url}/lead-forms/{form_key}/submit"
    render_endpoint = f"{base_url}/lead-forms/{form_key}/render"

    # 1. Đoạn nhúng Script JS tự động chèn biểu mẫu vào div container
    script_code = f"""<!-- Web-to-Lead Form Embed: {html.escape(form_name)} -->
<div id="crm-lead-form-{form_key}"></div>
<script>
(function() {{
  var container = document.getElementById("crm-lead-form-{form_key}");
  if (!container) return;
  var form = document.createElement("form");
  form.action = "{endpoint}";
  form.method = "POST";
  form.innerHTML = `
    <div style="margin-bottom:10px;"><label>Họ và tên *</label><br/><input type="text" name="full_name" required style="width:100%;padding:8px;box-sizing:border-box;"/></div>
    <div style="margin-bottom:10px;"><label>Email *</label><br/><input type="email" name="email" required style="width:100%;padding:8px;box-sizing:border-box;"/></div>
    <div style="margin-bottom:10px;"><label>Số điện thoại</label><br/><input type="tel" name="phone" style="width:100%;padding:8px;box-sizing:border-box;"/></div>
    <div style="margin-bottom:10px;"><label>Công ty</label><br/><input type="text" name="company" style="width:100%;padding:8px;box-sizing:border-box;"/></div>
    <div style="margin-bottom:10px;"><label>Nhu cầu quan tâm</label><br/><textarea name="interest" rows="3" style="width:100%;padding:8px;box-sizing:border-box;"></textarea></div>
    <input type="text" name="hp_website" style="display:none;" tabindex="-1" autocomplete="off"/>
    <button type="submit" style="background:#2563eb;color:#fff;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;">Gửi thông tin</button>
  `;
  form.onsubmit = async function(e) {{
    e.preventDefault();
    var data = {{
      full_name: form.full_name.value,
      email: form.email.value,
      phone: form.phone.value,
      company: form.company.value,
      interest: form.interest.value,
      hp_website: form.hp_website.value
    }};
    try {{
      var res = await fetch("{endpoint}", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(data)
      }});
      var result = await res.json();
      if (res.ok) {{
        container.innerHTML = '<div style="color:green;padding:15px;background:#f0fdf4;border-radius:4px;">Cảm ơn bạn! Chúng tôi đã nhận được thông tin và sẽ liên hệ sớm nhất.</div>';
      }} else {{
        alert(result.detail || "Có lỗi xảy ra, vui lòng thử lại.");
      }}
    }} catch (err) {{
      alert("Lỗi kết nối máy chủ");
    }}
  }};
  container.appendChild(form);
}})();
</script>"""

    # 2. Đoạn nhúng Iframe
    iframe_code = f'<iframe src="{render_endpoint}" width="100%" height="480" frameborder="0" style="border:1px solid #e2e8f0;border-radius:8px;"></iframe>'

    # 3. HTML Form thuần túy
    html_form = f"""<!-- Web-to-Lead Raw HTML Form -->
<form action="{endpoint}" method="POST" class="crm-lead-form">
  <div><label>Họ và tên *</label><input type="text" name="full_name" required /></div>
  <div><label>Email *</label><input type="email" name="email" required /></div>
  <div><label>Số điện thoại</label><input type="tel" name="phone" /></div>
  <div><label>Công ty</label><input type="text" name="company" /></div>
  <div><label>Nhu cầu quan tâm</label><textarea name="interest"></textarea></div>
  <input type="text" name="hp_website" style="display:none;" tabindex="-1" autocomplete="off" />
  <button type="submit">Gửi thông tin</button>
</form>"""

    return {
        "embed_script_tag": script_code,
        "embed_iframe_code": iframe_code,
        "embed_html_form": html_form,
    }


# ============================================================================
# SERVICE NGIỆP VỤ BIỂU MẪU (LEAD FORM CONFIG SERVICE)
# ============================================================================

def create_lead_form(payload: LeadFormCreate, user_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
    """Tạo biểu mẫu Web-to-Lead mới và sinh mã nhúng duy nhất (form_key)."""
    form_key = uuid.uuid4().hex[:16]
    now = datetime.utcnow()

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        new_form = LeadSourceConfig(
            form_key=form_key,
            name=payload.name.strip(),
            source_name=payload.source_name.strip() if payload.source_name else "Website Form",
            description=payload.description,
            target_url=payload.target_url,
            rate_limit_per_minute=payload.rate_limit_per_minute or 5,
            is_active=True,
            created_by=user_id,
        )
        db.add(new_form)
        db.commit()
        db.refresh(new_form)

        snippets = _generate_embed_snippets(new_form.form_key, new_form.name)
        result = {
            "id": new_form.id,
            "form_key": new_form.form_key,
            "name": new_form.name,
            "source_name": new_form.source_name,
            "description": new_form.description,
            "target_url": new_form.target_url,
            "is_active": new_form.is_active,
            "rate_limit_per_minute": new_form.rate_limit_per_minute,
            "created_by": new_form.created_by,
            "created_at": new_form.created_at,
            **snippets,
        }
        return result
    finally:
        if should_close:
            db.close()


def list_lead_forms(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách các biểu mẫu Web-to-Lead đang có."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        rows = db.query(LeadSourceConfig).order_by(LeadSourceConfig.id.desc()).all()
        results = []
        for r in rows:
            snippets = _generate_embed_snippets(r.form_key, r.name)
            results.append({
                "id": r.id,
                "form_key": r.form_key,
                "name": r.name,
                "source_name": r.source_name,
                "description": r.description,
                "target_url": r.target_url,
                "is_active": r.is_active,
                "rate_limit_per_minute": r.rate_limit_per_minute,
                "created_by": r.created_by,
                "created_at": r.created_at,
                **snippets,
            })
        return results
    finally:
        if should_close:
            db.close()


def get_lead_form_by_key(form_key: str, db: Optional[Session] = None) -> Optional[LeadSourceConfig]:
    """Tìm biểu mẫu theo form_key."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        return db.query(LeadSourceConfig).filter(LeadSourceConfig.form_key == form_key).first()
    finally:
        if should_close:
            db.close()


def get_lead_form_embed_code(form_key: str, base_url: str = "", db: Optional[Session] = None) -> Dict[str, Any]:
    """Lấy mã nhúng chi tiết cho một biểu mẫu Web-to-Lead."""
    form = get_lead_form_by_key(form_key, db=db)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy biểu mẫu với mã nhúng '{form_key}'",
        )

    snippets = _generate_embed_snippets(form.form_key, form.name, base_url=base_url)
    return {
        "form_key": form.form_key,
        "name": form.name,
        "source_name": form.source_name,
        "endpoint_url": f"{base_url}/lead-forms/{form.form_key}/submit",
        **snippets,
    }


# ============================================================================
# XỬ LÝ SUBMIT TỪ WEBSITE VÀ CHỐNG SPAM (PUBLIC WEB-TO-LEAD SUBMISSION)
# ============================================================================

def process_web_to_lead_submission(
    form_key: str,
    payload: WebToLeadSubmitRequest,
    client_ip: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    AC S4-01:
    1. Kiểm tra tồn tại và trạng thái kích hoạt của form_key.
    2. Chống spam qua Honeypot: Nếu hp_website có giá trị, từ chối hoặc bỏ qua (spam bot).
    3. Giới hạn tần suất (Rate limit) theo địa chỉ IP của client.
    4. Kiểm tra định dạng số điện thoại Việt Nam nếu có nhập.
    5. Tạo Lead mới ở trạng thái Mới ('NEW') và gắn đúng nguồn (source) của biểu mẫu.
    6. Lưu trữ nhất quán vào CSDL.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # 1. Tìm biểu mẫu theo form_key
        form = db.query(LeadSourceConfig).filter(LeadSourceConfig.form_key == form_key).first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mã biểu mẫu (form_key) không tồn tại trong hệ thống",
            )
        if not form.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Biểu mẫu này hiện đang tạm dừng tiếp nhận thông tin",
            )

        # 2. Chống spam: Honeypot check
        if payload.hp_website and payload.hp_website.strip():
            # Bot spam tự động điền trường ẩn
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phát hiện hành vi gửi dữ liệu bất thường (Spam detected)",
            )

        # 3. Giới hạn tần suất gửi theo địa chỉ IP (Rate limiting)
        max_rate = form.rate_limit_per_minute or 5
        if not _check_rate_limit(client_ip, max_per_minute=max_rate):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Bạn đã gửi quá số lần cho phép ({max_rate} lần/phút). Vui lòng đợi và thử lại sau.",
            )

        # 4. Kiểm tra số điện thoại Việt Nam nếu có điền
        clean_phone = None
        if payload.phone and payload.phone.strip():
            clean_phone = payload.phone.strip()
            vn_phone_pattern = re.compile(r"^(0|\+84)(3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}$")
            if not vn_phone_pattern.match(clean_phone):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại không đúng định dạng Việt Nam hợp lệ (10 chữ số, đầu số 03, 05, 07, 08, 09 hoặc +84)",
                )

        # 5. Tạo Lead mới ở trạng thái 'NEW' và gắn đúng nguồn của form
        new_lead = Lead(
            full_name=payload.full_name.strip(),
            email=payload.email.strip().lower(),
            phone=clean_phone,
            company=payload.company.strip() if payload.company else None,
            interest=payload.interest.strip() if payload.interest else None,
            source=form.source_name,  # Gắn đúng nguồn của biểu mẫu
            status="NEW",              # Trạng thái Mới theo AC
            form_key=form.form_key,
            ip_address=client_ip,
        )

        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        # S4-05: Tự động tính điểm ngay khi tiếp nhận lead
        calculate_lead_score(new_lead, db=db, commit=True)
        # S4-06: Tự động phân bổ lead theo quy tắc
        allocate_single_lead(new_lead, db=db, commit=True)

        return {
            "success": True,
            "message": "Gửi thông tin thành công! Chúng tôi sẽ liên hệ trong thời gian sớm nhất.",
            "lead_id": new_lead.id,
            "status": new_lead.status,
            "source": new_lead.source,
            "score": new_lead.score,
            "grade": new_lead.grade,
            "owner_id": new_lead.owner_id,
            "allocation_status": new_lead.allocation_status,
        }
    finally:
        if should_close:
            db.close()


# ============================================================================
# CẤU HÌNH VÀ TÍNH ĐIỂM LEAD (LEAD SCORING - S4-05)
# ============================================================================

def get_or_create_scoring_settings(db: Session) -> LeadScoringSetting:
    """Lấy hoặc khởi tạo cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh."""
    setting = db.query(LeadScoringSetting).first()
    if not setting:
        setting = LeadScoringSetting(hot_threshold=50, warm_threshold=20)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def update_scoring_settings(hot_threshold: int, warm_threshold: int, db: Session) -> LeadScoringSetting:
    """Cập nhật ngưỡng điểm phân loại Nóng, Ấm, Lạnh."""
    if warm_threshold >= hot_threshold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngưỡng điểm Ấm (WARM) phải nhỏ hơn ngưỡng điểm Nóng (HOT)",
        )
    setting = get_or_create_scoring_settings(db)
    setting.hot_threshold = hot_threshold
    setting.warm_threshold = warm_threshold
    db.commit()
    db.refresh(setting)
    return setting


def list_scoring_rules(active_only: bool = False, db: Session = None) -> List[LeadScoringRule]:
    """Lấy danh sách các tiêu chí chấm điểm."""
    query = db.query(LeadScoringRule)
    if active_only:
        query = query.filter(LeadScoringRule.is_active == True)
    return query.order_by(LeadScoringRule.id.asc()).all()


def get_scoring_rule_by_id(rule_id: int, db: Session) -> Optional[LeadScoringRule]:
    return db.query(LeadScoringRule).filter(LeadScoringRule.id == rule_id).first()


def create_scoring_rule(payload: LeadScoringRuleCreate, db: Session) -> LeadScoringRule:
    """Khai báo tiêu chí và số điểm (S4-05 AC)."""
    valid_fields = [
        "industry", "company_size", "source", "budget",
        "job_title", "phone", "email", "interest", "city", "company"
    ]
    clean_field = payload.field_name.strip().lower()
    if clean_field not in valid_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trường '{payload.field_name}' không hợp lệ. Các trường hỗ trợ: {', '.join(valid_fields)}",
        )

    valid_operators = [
        "EQUALS", "NOT_EQUALS", "CONTAINS", "NOT_EMPTY",
        "IS_EMPTY", "GREATER_THAN", "LESS_THAN", "IN"
    ]
    clean_op = payload.operator.strip().upper()
    if clean_op not in valid_operators:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Toán tử '{payload.operator}' không hợp lệ. Các toán tử hỗ trợ: {', '.join(valid_operators)}",
        )

    new_rule = LeadScoringRule(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        field_name=clean_field,
        operator=clean_op,
        target_value=payload.target_value.strip() if payload.target_value else None,
        points=payload.points,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule


def update_scoring_rule(rule_id: int, payload: LeadScoringRuleUpdate, db: Session) -> LeadScoringRule:
    rule = get_scoring_rule_by_id(rule_id, db=db)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tiêu chí chấm điểm với ID {rule_id}",
        )
    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.description is not None:
        rule.description = payload.description.strip()
    if payload.field_name is not None:
        valid_fields = [
            "industry", "company_size", "source", "budget",
            "job_title", "phone", "email", "interest", "city", "company"
        ]
        clean_field = payload.field_name.strip().lower()
        if clean_field not in valid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trường '{payload.field_name}' không hợp lệ",
            )
        rule.field_name = clean_field
    if payload.operator is not None:
        valid_operators = [
            "EQUALS", "NOT_EQUALS", "CONTAINS", "NOT_EMPTY",
            "IS_EMPTY", "GREATER_THAN", "LESS_THAN", "IN"
        ]
        clean_op = payload.operator.strip().upper()
        if clean_op not in valid_operators:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Toán tử '{payload.operator}' không hợp lệ",
            )
        rule.operator = clean_op
    if payload.target_value is not None:
        rule.target_value = payload.target_value.strip()
    if payload.points is not None:
        rule.points = payload.points
    if payload.is_active is not None:
        rule.is_active = payload.is_active

    db.commit()
    db.refresh(rule)
    return rule


def delete_scoring_rule(rule_id: int, db: Session) -> bool:
    rule = get_scoring_rule_by_id(rule_id, db=db)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def evaluate_rule_match(lead: Lead, rule: LeadScoringRule) -> bool:
    """Kiểm tra một rule chấm điểm có khớp với thông tin của lead hay không."""
    val = getattr(lead, rule.field_name, None)
    op = rule.operator
    target = rule.target_value or ""

    if op == "NOT_EMPTY":
        return val is not None and str(val).strip() != ""
    if op == "IS_EMPTY":
        return val is None or str(val).strip() == ""

    if val is None:
        return False

    s_val = str(val).strip()
    s_target = target.strip()

    if op == "EQUALS":
        return s_val.lower() == s_target.lower()
    elif op == "NOT_EQUALS":
        return s_val.lower() != s_target.lower()
    elif op == "CONTAINS":
        return s_target.lower() in s_val.lower()
    elif op == "IN":
        allowed = [x.strip().lower() for x in s_target.split(",") if x.strip()]
        return s_val.lower() in allowed
    elif op in ("GREATER_THAN", "LESS_THAN"):
        try:
            num_val = float(val)
            num_target = float(target)
            return num_val >= num_target if op == "GREATER_THAN" else num_val <= num_target
        except (ValueError, TypeError):
            return False
    return False


def calculate_lead_score(lead: Lead, db: Session, commit: bool = True) -> Tuple[int, str, List[dict]]:
    """
    AC S4-05:
    - Tính điểm dựa trên các tiêu chí khai báo đang active.
    - Phân loại Nóng (HOT), Ấm (WARM), Lạnh (COLD) theo ngưỡng cấu hình.
    - Điểm chỉ dùng để ưu tiên, không tự động loại lead (giữ nguyên status).
    """
    settings = get_or_create_scoring_settings(db)
    rules = list_scoring_rules(active_only=True, db=db)

    total_score = 0
    matched_details = []

    for rule in rules:
        if evaluate_rule_match(lead, rule):
            total_score += rule.points
            matched_details.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "field_name": rule.field_name,
                "points": rule.points,
            })

    if total_score >= settings.hot_threshold:
        grade = "HOT"
    elif total_score >= settings.warm_threshold:
        grade = "WARM"
    else:
        grade = "COLD"

    lead.score = total_score
    lead.grade = grade
    lead.score_details = json.dumps(matched_details, ensure_ascii=False)
    lead.last_scored_at = datetime.utcnow()

    if commit:
        db.commit()
        db.refresh(lead)

    return total_score, grade, matched_details


def recalculate_single_lead_score(lead_id: int, db: Session) -> Dict[str, Any]:
    """Tính lại điểm cho một lead cụ thể."""
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )
    score, grade, details = calculate_lead_score(lead, db=db, commit=True)
    return {
        "lead_id": lead.id,
        "score": score,
        "grade": grade,
        "matched_rules_count": len(details),
        "score_details": lead.score_details,
        "message": f"Đã tính lại điểm cho lead #{lead.id}: {score} điểm ({grade})",
    }


def recalculate_all_leads_scores(db: Session) -> Dict[str, Any]:
    """Tính lại điểm cho tất cả lead trong hệ thống."""
    leads = db.query(Lead).all()
    count = 0
    for lead in leads:
        calculate_lead_score(lead, db=db, commit=False)
        count += 1
    db.commit()
    return {
        "success": True,
        "total_recalculated": count,
        "message": f"Đã tính lại điểm cho {count} khách hàng tiềm năng",
    }


# ============================================================================
# QUẢN LÝ DANH SÁCH LEAD (CRM LEADS)
# ============================================================================

def create_crm_lead(payload: LeadCreate, current_user: dict, db: Session) -> Lead:
    """Tạo mới Lead từ giao diện CRM và tự động tính điểm."""
    new_lead = Lead(
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        phone=payload.phone.strip() if payload.phone else None,
        company=payload.company.strip() if payload.company else None,
        industry=payload.industry.strip() if payload.industry else None,
        company_size=payload.company_size.strip() if payload.company_size else None,
        budget=payload.budget,
        job_title=payload.job_title.strip() if payload.job_title else None,
        city=payload.city.strip() if payload.city else None,
        interest=payload.interest.strip() if payload.interest else None,
        source=payload.source.strip() if payload.source else "Manual Entry",
        status=payload.status.strip() if payload.status else "NEW",
        owner_id=payload.owner_id,
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    # Tự động tính điểm ngay khi tạo
    calculate_lead_score(new_lead, db=db, commit=True)

    # S4-06: Tự động phân bổ nếu chưa gán người phụ trách
    if new_lead.owner_id is None:
        allocate_single_lead(new_lead, db=db, commit=True)
    else:
        new_lead.allocation_status = "ASSIGNED"
        new_lead.allocated_at = datetime.utcnow()
        new_lead.allocation_method = "SPECIFIC_USER"
        new_lead.allocation_note = f"Gán trực tiếp cho nhân viên ID {new_lead.owner_id}"
        db.commit()
        db.refresh(new_lead)

    return new_lead



def update_crm_lead(lead_id: int, payload: LeadUpdate, db: Session) -> Lead:
    """Cập nhật thông tin lead và tự động tính lại điểm khi thông tin thay đổi (S4-05 AC)."""
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )

    # S4-08: Chặn chức năng chỉnh sửa đối với Lead đã chuyển đổi
    if lead.status in ["CONVERTED", "ĐÃ CHUYỂN ĐỔI", "Đã chuyển đổi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể chỉnh sửa khách hàng tiềm năng đã được chuyển đổi",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(lead, key) and value is not None:
            setattr(lead, key, value)

    db.commit()
    db.refresh(lead)

    # Tự động tính lại điểm sau khi thông tin thay đổi
    calculate_lead_score(lead, db=db, commit=True)
    return lead


def list_leads(
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    grade_filter: Optional[str] = None,
    min_score: Optional[int] = None,
    owner_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    is_overdue_sla: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Tuple[int, List[Lead]]:
    """
    Truy vấn danh sách lead kèm bộ lọc đa năng (S4-09):
    - Trạng thái, Nguồn, Phân loại Nóng/Ấm/Lạnh, Người phụ trách.
    - Khoảng thời gian (start_date, end_date) theo created_at.
    - Nhận diện lead vi phạm SLA (is_overdue_sla) nổi bật.
    - Kiểm tra phạm vi dữ liệu (Scope RBAC: USER chỉ xem lead của mình hoặc lead chưa phân bổ; MANAGER xem theo team/mình; ADMIN xem tất cả).
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Cập nhật vi phạm SLA theo thời gian thực trước khi truy vấn
        now = datetime.now(timezone.utc)
        pending_leads = db.query(Lead).filter(
            Lead.status.in_(["UNASSIGNED", "ASSIGNED", "NEW"]),
            Lead.is_overdue_sla == False,
            Lead.sla_deadline.isnot(None),
        ).all()
        for pl in pending_leads:
            deadline = pl.sla_deadline
            if deadline.tzinfo is None and now.tzinfo is not None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            elif deadline.tzinfo is not None and now.tzinfo is None:
                deadline = deadline.replace(tzinfo=None)
            if now > deadline:
                pl.is_overdue_sla = True
        db.commit()

        query = db.query(Lead)

        # 1. Kiểm tra Data Scope RBAC theo vai trò
        if current_user:
            role = current_user.get("role", "USER")
            uid = current_user.get("id")
            if role == "USER":
                # Nhân viên chỉ xem lead do mình phụ trách (owner_id hoặc assigned_to) hoặc lead chưa phân bổ
                query = query.filter(
                    (Lead.owner_id == uid) |
                    (Lead.assigned_to == uid) |
                    (Lead.owner_id.is_(None)) |
                    (Lead.status == "UNASSIGNED")
                )
            elif role == "MANAGER":
                # Quản lý xem toàn team hoặc lead được chỉ định (mặc định manager có quyền xem rộng trong nhóm)
                pass

        # 2. Bộ lọc trạng thái
        if status_filter:
            query = query.filter(Lead.status == status_filter.strip().upper())

        # 3. Bộ lọc nguồn
        if source_filter:
            query = query.filter(Lead.source.ilike(f"%{source_filter.strip()}%"))

        # 4. Bộ lọc phân loại Nóng/Ấm/Lạnh
        if grade_filter:
            query = query.filter(Lead.grade == grade_filter.strip().upper())

        # 5. Bộ lọc điểm số tối thiểu
        if min_score is not None:
            query = query.filter(Lead.score >= min_score)

        # 6. Bộ lọc người phụ trách (owner_id hoặc assigned_to)
        assignee_id = owner_id if owner_id is not None else assigned_to
        if assignee_id is not None:
            query = query.filter(
                (Lead.owner_id == assignee_id) | (Lead.assigned_to == assignee_id)
            )

        # 7. Bộ lọc nhận diện lead quá hạn SLA
        if is_overdue_sla is not None:
            query = query.filter(Lead.is_overdue_sla == is_overdue_sla)

        # 8. Bộ lọc khoảng thời gian tạo (start_date, end_date)
        if start_date is not None:
            query = query.filter(Lead.created_at >= start_date)
        if end_date is not None:
            query = query.filter(Lead.created_at <= end_date)

        # 9. Tìm kiếm từ khóa tự do
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                (Lead.full_name.ilike(term)) |
                (Lead.name.ilike(term)) |
                (Lead.email.ilike(term)) |
                (Lead.phone.ilike(term)) |
                (Lead.company.ilike(term)) |
                (Lead.industry.ilike(term))
            )

        total = query.count()

        # 10. Sắp xếp kết quả
        if sort_by == "score_desc":
            query = query.order_by(Lead.score.desc(), Lead.id.desc())
        elif sort_by == "score_asc":
            query = query.order_by(Lead.score.asc(), Lead.id.desc())
        elif sort_by == "created_at_desc":
            query = query.order_by(Lead.created_at.desc(), Lead.id.desc())
        elif sort_by == "created_at_asc":
            query = query.order_by(Lead.created_at.asc(), Lead.id.desc())
        elif sort_by == "sla_deadline_asc":
            query = query.order_by(Lead.sla_deadline.asc().nullslast(), Lead.id.desc())
        else:
            query = query.order_by(Lead.id.desc())

        items = query.offset(skip).limit(limit).all()
        return total, items
    finally:
        if should_close:
            db.close()


def get_lead_by_id(lead_id: int, db: Optional[Session] = None) -> Optional[Lead]:
    """Lấy chi tiết một lead theo ID."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        return db.query(Lead).filter(Lead.id == lead_id).first()
    finally:
        if should_close:
            db.close()


# ============================================================================
# CẤU HÌNH VÀ PHÂN BỔ LEAD TỰ ĐỘNG (LEAD ALLOCATION - S4-06)
# ============================================================================

def list_allocation_rules(active_only: bool = False, db: Session = None) -> List[LeadAllocationRule]:
    """
    AC S4-06: Danh sách quy tắc phân bổ, sắp xếp theo thứ tự ưu tiên (priority tăng dần: 1 > 2 > 3).
    """
    query = db.query(LeadAllocationRule)
    if active_only:
        query = query.filter(LeadAllocationRule.is_active == True)
    return query.order_by(LeadAllocationRule.priority.asc(), LeadAllocationRule.id.asc()).all()


def get_allocation_rule_by_id(rule_id: int, db: Session) -> Optional[LeadAllocationRule]:
    return db.query(LeadAllocationRule).filter(LeadAllocationRule.id == rule_id).first()


def create_allocation_rule(payload: LeadAllocationRuleCreate, db: Session) -> LeadAllocationRule:
    """
    AC S4-06: Khai báo quy tắc phân bổ theo khu vực, ngành nghề hoặc xoay vòng.
    """
    valid_criterion_types = ["REGION", "INDUSTRY", "SOURCE", "ANY"]
    c_type = payload.criterion_type.strip().upper()
    if c_type not in valid_criterion_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại tiêu chí '{payload.criterion_type}' không hợp lệ. Hỗ trợ: {', '.join(valid_criterion_types)}",
        )

    valid_methods = ["ROUND_ROBIN", "SPECIFIC_USER", "REGION", "INDUSTRY"]
    m_type = payload.allocation_method.strip().upper()
    if m_type not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phương thức phân bổ '{payload.allocation_method}' không hợp lệ. Hỗ trợ: {', '.join(valid_methods)}",
        )

    if not payload.assignee_user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quy tắc phân bổ phải có ít nhất một nhân viên nhận lead",
        )

    new_rule = LeadAllocationRule(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        priority=payload.priority,
        criterion_type=c_type,
        criterion_value=payload.criterion_value.strip() if payload.criterion_value else None,
        allocation_method=m_type,
        assignee_user_ids=json.dumps(payload.assignee_user_ids),
        last_assigned_index=-1,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule


def update_allocation_rule(rule_id: int, payload: LeadAllocationRuleUpdate, db: Session) -> LeadAllocationRule:
    rule = get_allocation_rule_by_id(rule_id, db=db)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc phân bổ với ID {rule_id}",
        )

    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.description is not None:
        rule.description = payload.description.strip()
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.criterion_type is not None:
        c_type = payload.criterion_type.strip().upper()
        valid_criterion_types = ["REGION", "INDUSTRY", "SOURCE", "ANY"]
        if c_type not in valid_criterion_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại tiêu chí '{payload.criterion_type}' không hợp lệ",
            )
        rule.criterion_type = c_type
    if payload.criterion_value is not None:
        rule.criterion_value = payload.criterion_value.strip()
    if payload.allocation_method is not None:
        m_type = payload.allocation_method.strip().upper()
        valid_methods = ["ROUND_ROBIN", "SPECIFIC_USER", "REGION", "INDUSTRY"]
        if m_type not in valid_methods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phương thức phân bổ '{payload.allocation_method}' không hợp lệ",
            )
        rule.allocation_method = m_type
    if payload.assignee_user_ids is not None:
        if not payload.assignee_user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Danh sách nhân viên nhận lead không được để trống",
            )
        rule.assignee_user_ids = json.dumps(payload.assignee_user_ids)
    if payload.is_active is not None:
        rule.is_active = payload.is_active

    db.commit()
    db.refresh(rule)
    return rule


def delete_allocation_rule(rule_id: int, db: Session) -> bool:
    rule = get_allocation_rule_by_id(rule_id, db=db)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def matches_allocation_criterion(lead: Lead, rule: LeadAllocationRule) -> bool:
    """Kiểm tra lead có khớp với điều kiện lọc của quy tắc phân bổ hay không."""
    c_type = rule.criterion_type
    val = rule.criterion_value or ""

    if c_type == "ANY":
        return True

    allowed_values = [v.strip().lower() for v in val.split(",") if v.strip()]

    if c_type == "REGION":
        lead_city = (lead.city or "").lower().strip()
        lead_company = (lead.company or "").lower().strip()
        lead_interest = (lead.interest or "").lower().strip()
        return any(
            v in lead_city or v in lead_company or v in lead_interest
            for v in allowed_values
        )
    elif c_type == "INDUSTRY":
        lead_ind = (lead.industry or "").lower().strip()
        return any(v in lead_ind or lead_ind in v for v in allowed_values)
    elif c_type == "SOURCE":
        lead_src = (lead.source or "").lower().strip()
        return any(v in lead_src for v in allowed_values)

    return False


def allocate_single_lead(lead: Lead, db: Session, commit: bool = True) -> LeadAllocationLog:
    """
    AC S4-06:
    - Phân bổ theo khu vực, ngành nghề hoặc xoay vòng.
    - Nhiều quy tắc có thứ tự ưu tiên (ưu tiên nhỏ hơn chạy trước: priority 1 > 2 > 3).
    - Lead không khớp quy tắc nào sẽ vào hàng chờ (QUEUED) để trưởng nhóm phân tay.
    - Ghi nhận lịch sử phân bổ LeadAllocationLog.
    """
    rules = list_allocation_rules(active_only=True, db=db)

    for rule in rules:
        if matches_allocation_criterion(lead, rule):
            try:
                assignee_ids = json.loads(rule.assignee_user_ids)
            except Exception:
                assignee_ids = []

            if not assignee_ids:
                continue

            # Phân bổ theo xoay vòng (Round Robin) hoặc gán cố định
            if rule.allocation_method in ("ROUND_ROBIN", "REGION", "INDUSTRY"):
                next_index = (rule.last_assigned_index + 1) % len(assignee_ids)
                rule.last_assigned_index = next_index
                assigned_user_id = assignee_ids[next_index]
            else:
                # SPECIFIC_USER: Gán cố định cho nhân viên đầu tiên trong danh sách
                assigned_user_id = assignee_ids[0]

            lead.owner_id = assigned_user_id
            lead.allocation_status = "ASSIGNED"
            lead.allocated_at = datetime.utcnow()
            lead.allocation_rule_id = rule.id
            lead.allocation_method = rule.allocation_method
            lead.allocation_note = f"Phân bổ tự động theo quy tắc #{rule.id} ({rule.name})"

            log = LeadAllocationLog(
                lead_id=lead.id,
                rule_id=rule.id,
                rule_name=rule.name,
                allocation_method=rule.allocation_method,
                assigned_to=assigned_user_id,
                status="SUCCESS",
                note=lead.allocation_note,
            )
            db.add(log)
            if commit:
                db.commit()
                db.refresh(lead)
            return log

    # Lead không khớp bất kỳ quy tắc nào -> Vào hàng chờ phân tay (AC S4-06)
    lead.owner_id = None
    lead.allocation_status = "QUEUED"
    lead.allocated_at = None
    lead.allocation_rule_id = None
    lead.allocation_method = None
    lead.allocation_note = "Không khớp quy tắc nào - Đang trong hàng chờ phân bổ thủ công"

    log = LeadAllocationLog(
        lead_id=lead.id,
        rule_id=None,
        rule_name=None,
        allocation_method="UNASSIGNED",
        assigned_to=None,
        status="QUEUED",
        note=lead.allocation_note,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(lead)
    return log


def manual_assign_lead(lead_id: int, owner_id: int, note: Optional[str], current_user: dict, db: Session) -> Lead:
    """
    AC S4-06: Trưởng nhóm hoặc quản trị viên phân bổ thủ công lead từ hàng chờ.
    """
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )

    # S4-08: Không phân bổ lại lead đã chuyển đổi
    if lead.status in ["CONVERTED", "ĐÃ CHUYỂN ĐỔI", "Đã chuyển đổi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể phân bổ khách hàng tiềm năng đã được chuyển đổi",
        )

    assigner_name = current_user.get("full_name") or current_user.get("username") or "Manager"
    allocation_note = note or f"Phân bổ thủ công bởi {assigner_name}"

    lead.owner_id = owner_id
    lead.allocation_status = "ASSIGNED"
    lead.allocated_at = datetime.utcnow()
    lead.allocation_method = "MANUAL"
    lead.allocation_note = allocation_note

    log = LeadAllocationLog(
        lead_id=lead.id,
        rule_id=None,
        rule_name="Thủ công",
        allocation_method="MANUAL",
        assigned_to=owner_id,
        status="MANUAL",
        note=allocation_note,
    )
    db.add(log)
    db.commit()
    db.refresh(lead)
    return lead


def list_allocation_queue(skip: int = 0, limit: int = 50, db: Session = None) -> Tuple[int, List[Lead]]:
    """
    AC S4-06: Lấy danh sách hàng chờ phân bổ (những lead chưa được gán hoặc ở trạng thái QUEUED).
    """
    query = db.query(Lead).filter(
        (Lead.allocation_status.in_(["QUEUED", "UNASSIGNED"])) | (Lead.owner_id.is_(None))
    )
    total = query.count()
    items = query.order_by(Lead.id.desc()).offset(skip).limit(limit).all()
    return total, items


def run_batch_lead_allocation(db: Session) -> Dict[str, Any]:
    """
    AC S4-06: Chạy quy trình phân bổ chạy nền cho toàn bộ lead đang trong hàng chờ.
    Hoàn tất nhanh chóng chỉ trong vài giây (< 5 phút).
    """
    unassigned_leads = db.query(Lead).filter(
        (Lead.allocation_status.in_(["QUEUED", "UNASSIGNED"])) | (Lead.owner_id.is_(None))
    ).all()

    assigned_count = 0
    queued_count = 0

    for lead in unassigned_leads:
        log = allocate_single_lead(lead, db=db, commit=False)
        if log.status == "SUCCESS":
            assigned_count += 1
        else:
            queued_count += 1

    db.commit()
    return {
        "success": True,
        "total_processed": len(unassigned_leads),
        "assigned_count": assigned_count,
        "queued_count": queued_count,
        "message": f"Đã xử lý {len(unassigned_leads)} lead trong hàng chờ: {assigned_count} phân bổ thành công, {queued_count} giữ trong hàng chờ.",
    }


def list_allocation_logs(lead_id: Optional[int] = None, skip: int = 0, limit: int = 50, db: Session = None) -> Tuple[int, List[LeadAllocationLog]]:
    """Truy vấn nhật ký phân bổ lead."""
    query = db.query(LeadAllocationLog)
    if lead_id is not None:
        query = query.filter(LeadAllocationLog.lead_id == lead_id)
    total = query.count()
    items = query.order_by(LeadAllocationLog.id.desc()).offset(skip).limit(limit).all()
    return total, items


# ============================================================================
# CHUYỂN ĐỔI LEAD SANG KHÁCH HÀNG & CƠ HỘI (LEAD CONVERSION - S4-08)
# ============================================================================

def convert_lead(
    lead_id: int,
    payload: Optional[LeadConvertRequest],
    current_user: dict,
    db: Session,
) -> Dict[str, Any]:
    """
    AC S4-08: Chuyển một lead đủ điều kiện thành khách hàng và cơ hội.
    - Kế thừa toàn bộ thông tin từ Lead, không bắt người dùng nhập lại các thông tin đã có sẵn.
    - Chạy trong 1 database transaction:
      + Tạo Khách hàng (Customer) doanh nghiệp/cá nhân từ dữ liệu của Lead.
      + Tạo Người liên hệ (Contact) gắn với Customer vừa tạo.
      + Tạo Cơ hội (Opportunity) gắn với Customer và Contact đó.
    - Cập nhật trạng thái Lead sang 'CONVERTED'.
    - Di chuyển/liên kết toàn bộ lịch sử hoạt động (Activity/Interaction) của Lead sang Customer/Opportunity mới.
    - Validate quyền hạn và dữ liệu chặt chẽ.
    """
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
        )

    # 1. Kiểm tra trạng thái đã chuyển đổi
    if lead.status in ["CONVERTED", "ĐÃ CHUYỂN ĐỔI", "Đã chuyển đổi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Khách hàng tiềm năng đã được chuyển đổi trước đó",
        )

    # 2. Kiểm tra nếu Lead bị loại/hủy (DISQUALIFIED)
    if lead.status == "DISQUALIFIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể chuyển đổi khách hàng tiềm năng không đạt điều kiện (DISQUALIFIED)",
        )

    # 3. Validate quyền hạn: USER chỉ được convert lead của mình hoặc lead chưa phân bổ
    role = current_user.get("role", "USER")
    user_id = current_user.get("id")
    if role == "USER" and lead.owner_id is not None and lead.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chuyển đổi khách hàng tiềm năng của người khác",
        )

    if payload is None:
        payload = LeadConvertRequest()

    owner_id = lead.owner_id or user_id or 1
    team_id = current_user.get("team_id")

    # Xác định tên Customer
    raw_customer_name = payload.customer_name or lead.company or lead.full_name
    customer_name = raw_customer_name.strip()
    tax_code = payload.tax_code.strip() if payload.tax_code else None

    # Kiểm tra trùng lặp MST nếu có
    if tax_code:
        existing_in_db = db.query(CustomerModel).filter(CustomerModel.tax_code == tax_code).first()
        if existing_in_db or any(c.get("tax_code") == tax_code for c in FAKE_CUSTOMERS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã số thuế '{tax_code}' đã tồn tại trong hệ thống",
            )

    try:
        # --- 1. TẠO KHÁCH HÀNG (CUSTOMER) ---
        db_max_cust_id = db.query(func.max(CustomerModel.id)).scalar() or 0
        fake_max_cust_id = max((c["id"] for c in FAKE_CUSTOMERS), default=0)
        new_cust_id = max(db_max_cust_id, fake_max_cust_id) + 1

        now_utc = datetime.utcnow()
        new_customer = CustomerModel(
            id=new_cust_id,
            name=customer_name,
            tax_code=tax_code,
            industry=lead.industry,
            company_size=lead.company_size,
            website=None,
            address=lead.city,
            status="CUSTOMER",
            parent_company_id=None,
            email=lead.email,
            phone=lead.phone,
            company=lead.company or customer_name,
            owner_id=owner_id,
            team_id=team_id,
            created_at=now_utc,
        )
        db.add(new_customer)
        db.flush()

        customer_dict = {
            "id": new_cust_id,
            "name": customer_name,
            "tax_code": tax_code,
            "industry": lead.industry,
            "company_size": lead.company_size,
            "website": None,
            "address": lead.city,
            "status": "CUSTOMER",
            "parent_company_id": None,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company or customer_name,
            "owner_id": owner_id,
            "team_id": team_id,
            "created_at": now_utc,
        }
        FAKE_CUSTOMERS.append(customer_dict)

        # --- 2. TẠO NGƯỜI LIÊN HỆ (CONTACT) ---
        raw_contact_name = payload.contact_name or lead.full_name
        contact_name = raw_contact_name.strip()
        decision_role = payload.contact_role or "DECISION_MAKER"
        contact_notes = payload.notes or lead.interest

        now_tz = datetime.now(timezone.utc)
        new_contact = ContactModel(
            customer_id=new_cust_id,
            name=contact_name,
            phone=lead.phone,
            email=lead.email,
            position=lead.job_title,
            decision_role=decision_role,
            is_primary=True,
            notes=contact_notes,
            created_at=now_tz,
        )
        db.add(new_contact)
        db.flush()

        performer = current_user.get("full_name") or current_user.get("email") or "system"
        contact_history = ContactCompanyHistoryModel(
            contact_id=new_contact.id,
            action="CREATE",
            from_customer_id=None,
            to_customer_id=new_cust_id,
            note="Chuyển đổi từ khách hàng tiềm năng (Lead)",
            performed_by=performer,
            timestamp=now_tz,
        )
        db.add(contact_history)

        contact_dict = _contact_model_to_dict(new_contact)
        FAKE_CONTACTS.append(contact_dict)

        # --- 3. TẠO CƠ HỘI (OPPORTUNITY) ---
        opp_title = (payload.opportunity_name and payload.opportunity_name.strip()) or f"Cơ hội - {customer_name}"
        opp_value = payload.opportunity_value if payload.opportunity_value is not None else (lead.budget or 0.0)
        opp_stage = payload.opportunity_stage or "PROSPECTING"
        new_opp_id = (max(o["id"] for o in FAKE_OPPORTUNITIES) + 1) if FAKE_OPPORTUNITIES else 1

        opp_dict = {
            "id": new_opp_id,
            "title": opp_title,
            "value": float(opp_value),
            "stage": opp_stage,
            "customer_id": new_cust_id,
            "contact_id": new_contact.id,
            "owner_id": owner_id,
            "team_id": team_id,
            "arr": 0.0,
            "has_products": False,
            "products": [],
        }
        FAKE_OPPORTUNITIES.append(opp_dict)

        # --- 4. DI CHUYỂN / LIÊN KẾT TOÀN BỘ HOẠT ĐỘNG (ACTIVITY/INTERACTION) ---
        for act in FAKE_ACTIVITIES:
            if act.get("lead_id") == lead.id:
                act["customer_id"] = new_cust_id
                act["opportunity_id"] = new_opp_id

        # Tạo thêm 1 activity ghi nhận log chuyển đổi
        new_act_id = (max(a["id"] for a in FAKE_ACTIVITIES) + 1) if FAKE_ACTIVITIES else 1
        conversion_act = {
            "id": new_act_id,
            "title": f"Chuyển đổi khách hàng tiềm năng: {lead.full_name}",
            "type": "NOTE",
            "description": f"Lead #{lead.id} ({lead.full_name}) đã được chuyển đổi thành Khách hàng '{customer_name}' và Cơ hội '{opp_title}'. Ngân sách: {lead.budget or 0}.",
            "customer_id": new_cust_id,
            "opportunity_id": new_opp_id,
            "lead_id": lead.id,
            "owner_id": owner_id,
            "team_id": team_id,
        }
        FAKE_ACTIVITIES.append(conversion_act)

        # --- 5. CẬP NHẬT TRẠNG THÁI LEAD SANG 'CONVERTED' ---
        lead.status = "CONVERTED"
        lead.converted_customer_id = new_cust_id
        lead.converted_opportunity_id = new_opp_id
        lead.converted_at = datetime.utcnow()
        lead.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(lead)
        db.refresh(new_customer)
        db.refresh(new_contact)

        return {
            "success": True,
            "message": f"Chuyển đổi khách hàng tiềm năng #{lead.id} thành công",
            "lead_id": lead.id,
            "customer_id": new_cust_id,
            "contact_id": new_contact.id,
            "opportunity_id": new_opp_id,
            "customer": _enrich_customer_names(customer_dict),
            "contact": contact_dict,
            "opportunity": opp_dict,
            "converted_at": lead.converted_at,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thực hiện giao dịch chuyển đổi Lead: {str(e)}",
        )


# ============================================================================
# TIẾP NHẬN, TỪ CHỐI VÀ KIỂM TRA SLA PHẢN HỒI LEAD (TASK S4-07)
# ============================================================================

def accept_lead(lead_id: int, user_id: Optional[int] = None, db: Optional[Session] = None) -> Lead:
    """
    Task S4-07: Tiếp nhận lead: đổi status sang IN_PROGRESS.
    Nếu user_id được chỉ định, gán assigned_to = user_id và owner_id = user_id.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )

        lead.status = "IN_PROGRESS"
        if user_id is not None:
            lead.assigned_to = user_id
            lead.owner_id = user_id
        lead.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(lead)
        return lead
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


def reject_lead(
    lead_id: int,
    reason: str,
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Lead:
    """
    Task S4-07: Từ chối tiếp nhận lead:
    - Bắt buộc phải có lý do (reason).
    - Đổi status sang UNASSIGNED.
    - Gán assigned_to = None, owner_id = None.
    - Lưu rejection_reason.
    """
    if not reason or not str(reason).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lý do từ chối không được để trống",
        )

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead với ID {lead_id} không tồn tại",
            )

        lead.status = "UNASSIGNED"
        lead.assigned_to = None
        lead.owner_id = None
        lead.rejection_reason = str(reason).strip()
        lead.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(lead)
        return lead
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


def check_sla_violations(
    sla_minutes: Optional[int] = None,
    current_time: Optional[datetime] = None,
    db: Optional[Session] = None,
) -> List[Lead]:
    """
    Task S4-07: Kiểm tra vi phạm SLA phản hồi lead:
    - Áp dụng cho các lead chưa được tiếp nhận xử lý (status != IN_PROGRESS, CONVERTED, DISQUALIFIED)
    - Nếu đã qua sla_deadline hoặc vượt quá threshold (sla_minutes) thì gán is_overdue_sla = True.
    - Trả về danh sách các lead vi phạm SLA.
    """
    now = current_time or datetime.now(timezone.utc)
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        leads = db.query(Lead).all()
        violated_leads: List[Lead] = []
        for lead in leads:
            # Chỉ kiểm tra các lead chưa vào xử lý
            if lead.status in ["UNASSIGNED", "ASSIGNED", "NEW"]:
                is_overdue = False

                # Kiểm tra hạn chót sla_deadline
                if lead.sla_deadline is not None:
                    deadline = lead.sla_deadline
                    if deadline.tzinfo is None and now.tzinfo is not None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    elif deadline.tzinfo is not None and now.tzinfo is None:
                        deadline = deadline.replace(tzinfo=None)
                    if now > deadline:
                        is_overdue = True

                # Kiểm tra số phút từ lúc tạo lead nếu có cấu hình sla_minutes
                if sla_minutes is not None and lead.created_at is not None:
                    created_at = lead.created_at
                    if created_at.tzinfo is None and now.tzinfo is not None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    elif created_at.tzinfo is not None and now.tzinfo is None:
                        created_at = created_at.replace(tzinfo=None)
                    if (now - created_at) > timedelta(minutes=sla_minutes):
                        is_overdue = True

                if is_overdue:
                    lead.is_overdue_sla = True
                    violated_leads.append(lead)

        db.commit()
        for v in violated_leads:
            db.refresh(v)
        return violated_leads
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


# ============================================================================
# BỘ LỌC LEAD ĐÃ LƯU (LEAD SAVED FILTERS - TASK S4-09)
# ============================================================================

def list_lead_saved_filters(user_id: int, db: Optional[Session] = None) -> List[LeadSavedFilter]:
    """Lấy danh sách các bộ lọc lead đã lưu của người dùng."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        return db.query(LeadSavedFilter).filter(
            LeadSavedFilter.user_id == user_id
        ).order_by(LeadSavedFilter.id.desc()).all()
    finally:
        if should_close:
            db.close()


def get_lead_saved_filter_by_id(filter_id: int, user_id: int, db: Optional[Session] = None) -> Optional[LeadSavedFilter]:
    """Lấy chi tiết bộ lọc lead đã lưu theo ID và quyền sở hữu."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        return db.query(LeadSavedFilter).filter(
            LeadSavedFilter.id == filter_id,
            LeadSavedFilter.user_id == user_id,
        ).first()
    finally:
        if should_close:
            db.close()


def create_lead_saved_filter(
    user_id: int,
    name: str,
    filter_criteria: dict,
    db: Optional[Session] = None,
) -> LeadSavedFilter:
    """Tạo mới và lưu bộ lọc lead để nhân viên tái sử dụng nhanh mỗi sáng."""
    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên bộ lọc không được để trống",
        )

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        criteria_json = json.dumps(filter_criteria, ensure_ascii=False)
        saved = LeadSavedFilter(
            user_id=user_id,
            name=name.strip(),
            filter_criteria=criteria_json,
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


def delete_lead_saved_filter(
    filter_id: int,
    user_id: int,
    db: Optional[Session] = None,
) -> bool:
    """Xóa bộ lọc lead đã lưu của nhân viên."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        filter_item = db.query(LeadSavedFilter).filter(
            LeadSavedFilter.id == filter_id,
            LeadSavedFilter.user_id == user_id,
        ).first()
        if not filter_item:
            return False
        db.delete(filter_item)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()





