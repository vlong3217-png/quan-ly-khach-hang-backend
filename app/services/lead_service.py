import html
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import json
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.lead import Lead, LeadSourceConfig, LeadScoringRule, LeadScoringSetting
from app.schemas.lead import (
    LeadCreate,
    LeadFormCreate,
    LeadFormUpdate,
    LeadScoringRuleCreate,
    LeadScoringRuleUpdate,
    LeadUpdate,
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

        return {
            "success": True,
            "message": "Gửi thông tin thành công! Chúng tôi sẽ liên hệ trong thời gian sớm nhất.",
            "lead_id": new_lead.id,
            "status": new_lead.status,
            "source": new_lead.source,
            "score": new_lead.score,
            "grade": new_lead.grade,
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
    return new_lead


def update_crm_lead(lead_id: int, payload: LeadUpdate, db: Session) -> Lead:
    """Cập nhật thông tin lead và tự động tính lại điểm khi thông tin thay đổi (S4-05 AC)."""
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng tiềm năng với ID {lead_id}",
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
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Optional[Session] = None,
) -> Tuple[int, List[Lead]]:
    """Truy vấn danh sách lead kèm bộ lọc và tìm kiếm, hỗ trợ ưu tiên theo điểm."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        query = db.query(Lead)
        if status_filter:
            query = query.filter(Lead.status == status_filter.strip().upper())
        if source_filter:
            query = query.filter(Lead.source.ilike(f"%{source_filter.strip()}%"))
        if grade_filter:
            query = query.filter(Lead.grade == grade_filter.strip().upper())
        if min_score is not None:
            query = query.filter(Lead.score >= min_score)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                (Lead.full_name.ilike(term)) |
                (Lead.email.ilike(term)) |
                (Lead.phone.ilike(term)) |
                (Lead.company.ilike(term)) |
                (Lead.industry.ilike(term))
            )

        total = query.count()

        if sort_by == "score_desc":
            query = query.order_by(Lead.score.desc(), Lead.id.desc())
        elif sort_by == "score_asc":
            query = query.order_by(Lead.score.asc(), Lead.id.desc())
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

