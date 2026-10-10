"""
Unified Lead Service:
- S4-01: Web-to-lead embed code & anti-spam collection
- S4-02: Manual lead creation with mandatory source & Excel batch import with template/preview
- S4-03: Campaign tracking linkage
- S4-04: Duplicate detection, attach to customer, lead merge preserving history
- S4-05: Lead scoring rules & classification
- S4-06: Lead allocation rules & assignment
"""

import copy
import html
import io
import json
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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
    LeadMergeHistory,
    LeadSavedFilter,
)
from app.models.customer import Customer
from app.schemas.lead import (
    LeadAllocationRuleCreate,
    LeadAllocationRuleUpdate,
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadUpdate,
    LeadFormCreate,
    LeadFormUpdate,
    LeadScoringRuleCreate,
    LeadScoringRuleUpdate,
    LeadAllocationRuleCreate,
    LeadAllocationRuleUpdate,
    WebToLeadSubmitRequest,
)
from app.services import customer_service, auth_service
from app.services.activity_service import FAKE_ACTIVITIES


# ============================================================================
# BỘ NHỚ TẠM CHO RATE LIMITING & SUBMISSION (S4-01)
# ============================================================================

_ip_submission_timestamps: Dict[str, List[float]] = defaultdict(list)


def _check_rate_limit(ip_address: str, max_per_minute: int = 5) -> bool:
    """Kiểm tra giới hạn tần suất gửi theo địa chỉ IP (Rate limiting chống spam - S4-01)."""
    now = time.time()
    one_minute_ago = now - 60.0
    _ip_submission_timestamps[ip_address] = [
        t for t in _ip_submission_timestamps[ip_address] if t > one_minute_ago
    ]
    if len(_ip_submission_timestamps[ip_address]) >= max_per_minute:
        return False
    _ip_submission_timestamps[ip_address].append(now)
    return True


def _generate_embed_snippets(form_key: str, form_name: str, base_url: str = "") -> Dict[str, str]:
    """Tạo các đoạn mã nhúng chuẩn (Embed Script, Iframe, HTML Form) để chèn vào website."""
    endpoint = f"{base_url}/lead-forms/{form_key}/submit"
    render_endpoint = f"{base_url}/lead-forms/{form_key}/render"

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

    iframe_code = f'<iframe src="{render_endpoint}" width="100%" height="480" frameborder="0" style="border:1px solid #e2e8f0;border-radius:8px;"></iframe>'

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
# CẤU HÌNH BIỂU MẪU WEB-TO-LEAD (S4-01)
# ============================================================================

def create_lead_form(payload: LeadFormCreate, user_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
    form_key = uuid.uuid4().hex[:16]
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
        return {
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
    finally:
        if should_close:
            db.close()


def list_lead_forms(db: Optional[Session] = None) -> List[Dict[str, Any]]:
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


def process_web_to_lead_submission(
    form_key: str,
    payload: WebToLeadSubmitRequest,
    client_ip: str = "127.0.0.1",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        form = get_lead_form_by_key(form_key, db=db)
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mã biểu mẫu '{form_key}' không tồn tại hoặc đã bị xóa",
            )
        if not form.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Biểu mẫu này hiện đang tạm ngưng tiếp nhận thông tin",
            )

        if payload.hp_website and payload.hp_website.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phát hiện hành vi gửi dữ liệu bất thường (Spam detected)",
            )

        max_rate = form.rate_limit_per_minute or 5
        if not _check_rate_limit(client_ip, max_per_minute=max_rate):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Bạn đã gửi quá số lần cho phép ({max_rate} lần/phút). Vui lòng đợi và thử lại sau.",
            )

        clean_phone = None
        if payload.phone and payload.phone.strip():
            clean_phone = payload.phone.strip()
            vn_phone_pattern = re.compile(r"^(0|\+84)(3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}$")
            if not vn_phone_pattern.match(clean_phone):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại không đúng định dạng Việt Nam hợp lệ (10 chữ số, đầu số 03, 05, 07, 08, 09 hoặc +84)",
                )

        new_lead = Lead(
            full_name=payload.full_name.strip(),
            name=payload.full_name.strip(),
            email=payload.email.strip().lower(),
            phone=clean_phone,
            company=payload.company.strip() if payload.company else None,
            company_name=payload.company.strip() if payload.company else None,
            interest=payload.interest.strip() if payload.interest else None,
            source=form.source_name,
            status="NEW",
            form_key=form.form_key,
            ip_address=client_ip,
        )

        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        calculate_lead_score(new_lead, db=db, commit=True)
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
    setting = db.query(LeadScoringSetting).first()
    if not setting:
        setting = LeadScoringSetting(hot_threshold=50, warm_threshold=20)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def update_scoring_settings(hot_threshold: int, warm_threshold: int, db: Session) -> LeadScoringSetting:
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
    query = db.query(LeadScoringRule)
    if active_only:
        query = query.filter(LeadScoringRule.is_active == True)
    return query.order_by(LeadScoringRule.id.asc()).all()


def get_scoring_rule_by_id(rule_id: int, db: Session) -> Optional[LeadScoringRule]:
    return db.query(LeadScoringRule).filter(LeadScoringRule.id == rule_id).first()


def create_scoring_rule(payload: LeadScoringRuleCreate, db: Session) -> LeadScoringRule:
    valid_fields = ["industry", "company_size", "source", "budget", "job_title", "phone", "email", "interest", "city"]
    if payload.field_name not in valid_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trường dữ liệu '{payload.field_name}' không hỗ trợ chấm điểm. Các trường hợp lệ: {', '.join(valid_fields)}",
        )
    valid_ops = ["EQUALS", "NOT_EQUALS", "CONTAINS", "NOT_EMPTY", "IS_EMPTY", "GREATER_THAN", "LESS_THAN", "IN"]
    op = payload.operator.upper()
    if op not in valid_ops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Toán tử '{payload.operator}' không hợp lệ. Các toán tử hợp lệ: {', '.join(valid_ops)}",
        )
    rule = LeadScoringRule(
        name=payload.name.strip(),
        description=payload.description,
        field_name=payload.field_name,
        operator=op,
        target_value=payload.target_value.strip() if payload.target_value else None,
        points=payload.points,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_scoring_rule(rule_id: int, payload: LeadScoringRuleUpdate, db: Session) -> LeadScoringRule:
    rule = get_scoring_rule_by_id(rule_id, db=db)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc chấm điểm với ID {rule_id}",
        )
    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.description is not None:
        rule.description = payload.description
    if payload.field_name is not None:
        rule.field_name = payload.field_name
    if payload.operator is not None:
        rule.operator = payload.operator.upper()
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
    field = rule.field_name
    val = getattr(lead, field, None)
    target = rule.target_value or ""
    op = rule.operator

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
    lead.last_scored_at = datetime.now(timezone.utc)

    if commit:
        db.commit()
        db.refresh(lead)

    return total_score, grade, matched_details


def recalculate_single_lead_score(lead_id: int, db: Session) -> Dict[str, Any]:
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
# PHÂN BỔ LEAD TỰ ĐỘNG (LEAD ALLOCATION - S4-06)
# ============================================================================
# CẤU HÌNH VÀ PHÂN BỔ LEAD TỰ ĐỘNG (LEAD ALLOCATION - S4-06)
# ============================================================================
# ============================================================================

def list_allocation_rules(active_only: bool = False, db: Session = None) -> List[LeadAllocationRule]:
    query = db.query(LeadAllocationRule)
    if active_only:
        query = query.filter(LeadAllocationRule.is_active == True)
    return query.order_by(LeadAllocationRule.priority.asc(), LeadAllocationRule.id.asc()).all()


def get_allocation_rule_by_id(rule_id: int, db: Session) -> Optional[LeadAllocationRule]:
    return db.query(LeadAllocationRule).filter(LeadAllocationRule.id == rule_id).first()


def create_allocation_rule(payload: LeadAllocationRuleCreate, db: Session) -> LeadAllocationRule:
    valid_types = ["REGION", "INDUSTRY", "SOURCE", "ANY"]
    c_type = payload.criterion_type.strip().upper()
    if c_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại tiêu chí '{payload.criterion_type}' không hợp lệ. Các loại hợp lệ: {', '.join(valid_types)}",
        )
    valid_methods = ["ROUND_ROBIN", "SPECIFIC_USER", "REGION", "INDUSTRY"]
    m_type = payload.allocation_method.strip().upper()
    if m_type not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phương thức phân bổ '{payload.allocation_method}' không hợp lệ",
        )
    if not payload.assignee_user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh sách nhân viên nhận lead không được để trống",
        )
    rule = LeadAllocationRule(
        name=payload.name.strip(),
        description=payload.description,
        priority=payload.priority,
        criterion_type=c_type,
        criterion_value=payload.criterion_value.strip() if payload.criterion_value else None,
        allocation_method=m_type,
        assignee_user_ids=json.dumps(payload.assignee_user_ids),
        last_assigned_index=-1,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_allocation_rule(rule_id: int, payload: LeadAllocationRuleUpdate, db: Session) -> LeadAllocationRule:
    rule = get_allocation_rule_by_id(rule_id, db=db)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc phân bổ ID {rule_id}",
        )
    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.description is not None:
        rule.description = payload.description
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.criterion_type is not None:
        rule.criterion_type = payload.criterion_type.strip().upper()
    if payload.criterion_value is not None:
        rule.criterion_value = payload.criterion_value.strip()
    if payload.allocation_method is not None:
        rule.allocation_method = payload.allocation_method.strip().upper()
    if payload.assignee_user_ids is not None:
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
    rules = list_allocation_rules(active_only=True, db=db)

    for rule in rules:
        if matches_allocation_criterion(lead, rule):
            try:
                assignee_ids = json.loads(rule.assignee_user_ids)
            except Exception:
                assignee_ids = []

            if not assignee_ids:
                continue

            if rule.allocation_method in ("ROUND_ROBIN", "REGION", "INDUSTRY"):
                next_index = (rule.last_assigned_index + 1) % len(assignee_ids)
                rule.last_assigned_index = next_index
                assigned_user_id = assignee_ids[next_index]
            else:
                assigned_user_id = assignee_ids[0]

            lead.owner_id = assigned_user_id
            lead.allocation_status = "ASSIGNED"
            lead.allocated_at = datetime.now(timezone.utc)
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
    lead.allocated_at = datetime.now(timezone.utc)
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
    query = db.query(Lead).filter(
        (Lead.allocation_status.in_(["QUEUED", "UNASSIGNED"])) | (Lead.owner_id.is_(None))
    )
    total = query.count()
    items = query.order_by(Lead.id.desc()).offset(skip).limit(limit).all()
    return total, items


def run_batch_lead_allocation(db: Session) -> Dict[str, Any]:
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
    query = db.query(LeadAllocationLog)
    if lead_id is not None:
        query = query.filter(LeadAllocationLog.lead_id == lead_id)
    total = query.count()
    items = query.order_by(LeadAllocationLog.id.desc()).offset(skip).limit(limit).all()
    return total, items


# ============================================================================
# S4-02: LEAD CRUD & MANUAL CREATION (BẮT BUỘC CÓ NGUỒN)
# ============================================================================

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


def _enrich_lead_model(lead: Lead) -> Lead:
    """Gắn các thông tin phụ trợ cho hiển thị (owner_name, campaign_name, customer_name)."""
    if hasattr(lead, "owner_id") and lead.owner_id:
        owner = auth_service.get_user_by_id(lead.owner_id)
        setattr(lead, "owner_name", owner.get("full_name") if owner else None)
    else:
        setattr(lead, "owner_name", None)

    if hasattr(lead, "campaign_id") and lead.campaign_id:
        from app.services import campaign_service
        camp = campaign_service.get_campaign_by_id(lead.campaign_id)
        setattr(lead, "campaign_name", camp.get("name") if camp else None)
    else:
        setattr(lead, "campaign_name", None)

    if hasattr(lead, "customer_id") and lead.customer_id:
        cust = customer_service.get_customer_by_id(lead.customer_id)
        setattr(lead, "customer_name", cust.get("name") if cust else None)
    else:
        setattr(lead, "customer_name", None)

    # Đảm bảo name và full_name, company và company_name luôn đồng bộ
    if not lead.name and lead.full_name:
        lead.name = lead.full_name
    elif not lead.full_name and lead.name:
        lead.full_name = lead.name

    if not lead.company_name and lead.company:
        lead.company_name = lead.company
    elif not lead.company and lead.company_name:
        lead.company = lead.company_name

    return lead


def create_crm_lead(payload: Any, current_user: dict, db: Optional[Session] = None) -> Lead:
    """
    AC S4-02: Nhập tay một lead từ sự kiện hoặc danh thiếp.
    MỌI LEAD NHẬP VÀO ĐỀU BẮT BUỘC CÓ NGUỒN (source).
    """
    data = payload if isinstance(payload, dict) else payload.model_dump()

    source = data.get("source")
    if not source or not str(source).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mọi lead nhập vào đều bắt buộc có nguồn",
        )

    full_name = data.get("full_name") or data.get("name")
    if not full_name or not str(full_name).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Họ và tên lead là bắt buộc",
        )

    company = data.get("company") or data.get("company_name")

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        new_lead = Lead(
            full_name=str(full_name).strip(),
            name=str(full_name).strip(),
            email=normalize_email(data.get("email")) or None,
            phone=str(data.get("phone")).strip() if data.get("phone") else None,
            company=str(company).strip() if company else None,
            company_name=str(company).strip() if company else None,
            title=data.get("title"),
            address=data.get("address"),
            industry=data.get("industry"),
            company_size=data.get("company_size"),
            budget=data.get("budget"),
            job_title=data.get("job_title") or data.get("title"),
            city=data.get("city"),
            interest=data.get("interest"),
            notes=data.get("notes"),
            source=str(source).strip(),
            campaign_id=data.get("campaign_id"),
            customer_id=data.get("customer_id"),
            status=data.get("status") or "NEW",
            owner_id=data.get("owner_id"),
            team_id=data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        )
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        # Tính điểm tự động S4-05
        calculate_lead_score(new_lead, db=db, commit=True)

        # Phân bổ S4-06
        if new_lead.owner_id is None:
            allocate_single_lead(new_lead, db=db, commit=True)
        else:
            new_lead.allocation_status = "ASSIGNED"
            new_lead.allocated_at = datetime.now(timezone.utc)
            new_lead.allocation_method = "SPECIFIC_USER"
            new_lead.allocation_note = f"Gán trực tiếp cho nhân viên ID {new_lead.owner_id}"
            db.commit()
            db.refresh(new_lead)

        return _enrich_lead_model(new_lead)
    finally:
        if should_close:
            db.close()


def create_lead(data: dict, current_user: dict) -> dict:
    """Tương thích ngược cho các gọi hàm dạng create_lead."""
    db = SessionLocal()
    try:
        lead_obj = create_crm_lead(data, current_user, db=db)
        return lead_to_dict(lead_obj)
    finally:
        db.close()


def get_lead_by_id(lead_id: int, db: Optional[Session] = None) -> Optional[Lead]:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            _enrich_lead_model(lead)
        return lead
    finally:
        if should_close:
            db.close()


def update_crm_lead(lead_id: int, payload: Any, db: Session, current_user: Optional[dict] = None) -> Lead:
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

    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)

    if "source" in data and data["source"] is not None:
        if not str(data["source"]).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nguồn lead không được để trống",
            )
        lead.source = str(data["source"]).strip()

    name_val = data.get("name") or data.get("full_name")
    if name_val is not None:
        if not str(name_val).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Họ và tên lead không được để trống",
            )
        lead.name = str(name_val).strip()
        lead.full_name = str(name_val).strip()

    comp_val = data.get("company") or data.get("company_name")
    if comp_val is not None:
        lead.company = str(comp_val).strip()
        lead.company_name = str(comp_val).strip()

    for key, value in data.items():
        if key not in ("id", "source", "name", "full_name", "company", "company_name") and hasattr(lead, key):
            if value is not None:
                setattr(lead, key, value)

    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)

    calculate_lead_score(lead, db=db, commit=True)
    return _enrich_lead_model(lead)


def update_lead(lead_id: int, data: dict, current_user: dict) -> dict:
    db = SessionLocal()
    try:
        updated = update_crm_lead(lead_id, data, db=db, current_user=current_user)
        return lead_to_dict(updated)
    finally:
        db.close()


def delete_lead(lead_id: int, db: Optional[Session] = None) -> bool:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return False
        db.delete(lead)
        db.commit()
        return True
    finally:
        if should_close:
            db.close()


def list_leads(
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    grade_filter: Optional[str] = None,
    campaign_id: Optional[int] = None,
    min_score: Optional[int] = None,
    owner_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    is_overdue_sla: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    include_merged: bool = False,
    skip: int = 0,
    limit: int = 100,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Tuple[int, List[Lead]]:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Cập nhật vi phạm SLA theo thời gian thực trước khi truy vấn (S4-07)
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

        # 1. Scope RBAC
        if current_user:
            role = current_user.get("role", "USER")
            uid = current_user.get("id")
            if role == "USER":
                query = query.filter(
                    (Lead.owner_id == uid) |
                    (Lead.assigned_to == uid) |
                    (Lead.owner_id.is_(None)) |
                    (Lead.status == "UNASSIGNED")
                )
            elif role == "MANAGER":
                pass

        # 2. Không lấy lead đã gộp trừ khi được yêu cầu (S4-04)
        if not include_merged:
            query = query.filter(Lead.status != "MERGED")

        # 3. Bộ lọc trạng thái
        if status_filter:
            query = query.filter(Lead.status == status_filter.strip().upper())

        # 4. Bộ lọc nguồn
        if source_filter:
            query = query.filter(Lead.source.ilike(f"%{source_filter.strip()}%"))

        # 5. Bộ lọc phân loại Nóng/Ấm/Lạnh
        if grade_filter:
            query = query.filter(Lead.grade == grade_filter.strip().upper())

        # 6. Bộ lọc chiến dịch (S4-03)
        if campaign_id is not None:
            query = query.filter(Lead.campaign_id == campaign_id)

        # 7. Bộ lọc điểm số tối thiểu
        if min_score is not None:
            query = query.filter(Lead.score >= min_score)

        # 8. Bộ lọc người phụ trách (owner_id hoặc assigned_to)
        assignee_id = owner_id if owner_id is not None else assigned_to
        if assignee_id is not None:
            query = query.filter(
                (Lead.owner_id == assignee_id) | (Lead.assigned_to == assignee_id)
            )

        # 9. Bộ lọc SLA
        if is_overdue_sla is not None:
            query = query.filter(Lead.is_overdue_sla == is_overdue_sla)

        # 10. Khoảng thời gian (start_date, end_date)
        if start_date is not None:
            query = query.filter(Lead.created_at >= start_date)
        if end_date is not None:
            query = query.filter(Lead.created_at <= end_date)

        # 11. Tìm kiếm tự do
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                (Lead.full_name.ilike(term))
                | (Lead.name.ilike(term))
                | (Lead.email.ilike(term))
                | (Lead.phone.ilike(term))
                | (Lead.company.ilike(term))
            )

        total = query.count()

        # 12. Sắp xếp kết quả
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
        for it in items:
            _enrich_lead_model(it)
        return total, items
    finally:
        if should_close:
            db.close()


def lead_to_dict(lead: Lead) -> dict:
    """Chuyển đổi instance Lead sang dictionary an toàn."""
    _enrich_lead_model(lead)
    return {
        "id": lead.id,
        "name": lead.full_name or lead.name,
        "full_name": lead.full_name or lead.name,
        "company_name": lead.company or lead.company_name,
        "company": lead.company or lead.company_name,
        "title": lead.title or lead.job_title,
        "job_title": lead.job_title or lead.title,
        "email": lead.email,
        "phone": lead.phone,
        "address": lead.address,
        "interest": lead.interest,
        "industry": lead.industry,
        "company_size": lead.company_size,
        "budget": lead.budget,
        "city": lead.city,
        "source": lead.source,
        "campaign_id": lead.campaign_id,
        "customer_id": lead.customer_id,
        "status": lead.status,
        "notes": lead.notes,
        "form_key": getattr(lead, "form_key", None),
        "ip_address": getattr(lead, "ip_address", None),
        "merged_into_id": lead.merged_into_id,
        "owner_id": lead.owner_id,
        "assigned_to": getattr(lead, "assigned_to", None),
        "team_id": getattr(lead, "team_id", None),
        "owner_name": getattr(lead, "owner_name", None),
        "campaign_name": getattr(lead, "campaign_name", None),
        "customer_name": getattr(lead, "customer_name", None),
        "rejection_reason": getattr(lead, "rejection_reason", None),
        "is_overdue_sla": bool(getattr(lead, "is_overdue_sla", False)),
        "sla_deadline": getattr(lead, "sla_deadline", None),
        "converted_customer_id": getattr(lead, "converted_customer_id", None),
        "converted_opportunity_id": getattr(lead, "converted_opportunity_id", None),
        "converted_at": getattr(lead, "converted_at", None),
        "score": lead.score or 0,
        "grade": lead.grade or "COLD",
        "score_details": getattr(lead, "score_details", None),
        "last_scored_at": getattr(lead, "last_scored_at", None),
        "allocation_status": lead.allocation_status or "UNASSIGNED",
        "allocated_at": getattr(lead, "allocated_at", None),
        "allocation_rule_id": getattr(lead, "allocation_rule_id", None),
        "allocation_method": getattr(lead, "allocation_method", None),
        "allocation_note": getattr(lead, "allocation_note", None),
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


# ============================================================================
# S4-02: EXCEL TEMPLATE, PREVIEW & BATCH IMPORT
# ============================================================================
# 2. XUẤT TỆP MẪU EXCEL & NHẬP LEAD HÀNG LOẠT (S4-02)
# ============================================================================

def generate_lead_import_template() -> bytes:
    """
    AC S4-02: Xuất tệp mẫu Excel chuẩn để người dùng thấy cấu trúc & nội dung cần điền.
    - Sheet 1: 'Mau_Nhap_Lead' chứa tiêu đề và 2 dòng dữ liệu mẫu ví dụ trực quan.
    - Sheet 2: 'Huong_Dan' hướng dẫn chi tiết định dạng từng trường, lưu ý các trường bắt buộc.
    - Tuyệt đối không lấy dữ liệu thực tế trong hệ thống ra, chỉ cung cấp mẫu chuẩn.
    """
    wb = openpyxl.Workbook()

    # --- Sheet 1: Mẫu nhập liệu ---
    ws1 = wb.active
    ws1.title = "Mau_Nhap_Lead"

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

    ws1.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # 2 dòng dữ liệu mẫu minh họa nội dung cần ghi vào
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
        ws1.append(row)

    column_widths = [24, 28, 18, 28, 34, 24, 28, 40, 20]
    for i, width in enumerate(column_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws1.column_dimensions[col_letter].width = width

    # --- Sheet 2: Hướng dẫn nhập liệu ---
    ws2 = wb.create_sheet(title="Huong_Dan")
    ws2.column_dimensions["A"].width = 25
    ws2.column_dimensions["B"].width = 15
    ws2.column_dimensions["C"].width = 35
    ws2.column_dimensions["D"].width = 45

    guide_title = "HƯỚNG DẪN ĐIỀN DỮ LIỆU TỆP MẪU NHẬP LEAD (USER STORY S4-02)"
    ws2["A1"] = guide_title
    ws2["A1"].font = Font(name="Calibri", size=13, bold=True, color="1E88E5")

    ws2["A2"] = "Lưu ý: Tệp này là tệp mẫu hướng dẫn. Các dòng trên Sheet 'Mau_Nhap_Lead' là ví dụ minh họa cách ghi nội dung."
    ws2["A2"].font = Font(name="Calibri", size=10, italic=True)

    guide_headers = ["Tên cột", "Bắt buộc", "Ví dụ nội dung", "Quy tắc kiểm tra hợp lệ"]
    ws2.append([])  # Row 3 trống
    ws2.append(guide_headers)  # Row 4

    guide_hdr_fill = PatternFill(start_color="37474F", end_color="37474F", fill_type="solid")
    guide_hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, 5):
        c = ws2.cell(row=4, column=col_idx)
        c.fill = guide_hdr_fill
        c.font = guide_hdr_font
        c.alignment = center_align

    guide_rows = [
        ["Họ và tên (*)", "Bắt buộc", "Nguyễn Văn A", "Không được để trống. Họ tên của khách hàng tiềm năng."],
        ["Nguồn lead (*)", "Bắt buộc", "Hội thảo, Sự kiện, Danh thiếp", "Bắt buộc theo AC S4-02: Mọi lead nhập vào đều phải có nguồn."],
        ["Số điện thoại", "Tùy chọn", "0981234567, 0912345678", "Gồm 10 hoặc 11 chữ số hợp lệ."],
        ["Email", "Tùy chọn", "bao.tran@techvn.com", "Định dạng email chuẩn (ten@domain.com)."],
        ["Tên công ty", "Tùy chọn", "Công ty Cổ phần Công nghệ ABC", "Tên doanh nghiệp nơi lead đang làm việc."],
        ["Chức vụ", "Tùy chọn", "Trưởng phòng CNTT, Giám đốc", "Vị trí / chức danh chuyên môn."],
        ["Địa chỉ", "Tùy chọn", "Cầu Giấy, Hà Nội", "Địa chỉ liên hệ hoặc khu vực địa lý."],
        ["Ghi chú", "Tùy chọn", "Trao đổi danh thiếp tại hội thảo", "Nhu cầu tư vấn, mối quan tâm sơ bộ."],
        ["Mã chiến dịch", "Tùy chọn", "CAMP-2026-EXPO", "Mã chiến dịch marketing liên kết nếu có."],
    ]

    for g_row in guide_rows:
        ws2.append(g_row)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def preview_import_leads_excel(file_bytes: bytes, current_user: dict) -> dict:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tệp không đúng định dạng Excel (.xlsx): {str(e)}",
        )

    # Ưu tiên sheet Mau_Nhap_Lead hoặc Lead_Template nếu có
    ws = None
    for s_name in ["Mau_Nhap_Lead", "Lead_Template", "Sheet1"]:
        if s_name in wb.sheetnames:
            ws = wb[s_name]
            break
    if ws is None:
        ws = wb.active

    rows_data: List[dict] = []
    duplicate_count = 0
    invalid_count = 0

    from app.services import campaign_service

    # Đọc dòng tiêu đề (Header row 1) để map linh hoạt tên cột
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None) or []
    header_col_map = {}
    for idx, cell_val in enumerate(header_row):
        if cell_val is not None:
            clean_hdr = str(cell_val).strip().lower()
            header_col_map[clean_hdr] = idx

    def get_cell(row_tuple, default_col_idx, aliases):
        for alias in aliases:
            if alias in header_col_map:
                mapped_idx = header_col_map[alias]
                if mapped_idx < len(row_tuple) and row_tuple[mapped_idx] is not None:
                    return str(row_tuple[mapped_idx]).strip()
        if default_col_idx < len(row_tuple) and row_tuple[default_col_idx] is not None:
            return str(row_tuple[default_col_idx]).strip()
        return ""

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        raw_name = get_cell(row, 0, ["họ và tên (*)", "họ và tên", "họ tên (*)", "họ tên", "name", "full_name"])
        raw_source = get_cell(row, 1, ["nguồn lead (*)", "nguồn lead", "nguồn", "source"])
        raw_phone = get_cell(row, 2, ["số điện thoại", "sđt", "điện thoại", "phone"])
        raw_email = get_cell(row, 3, ["email", "thư điện tử"])
        raw_company = get_cell(row, 4, ["tên công ty", "công ty", "company", "tên công ty / doanh nghiệp"])
        raw_title = get_cell(row, 5, ["chức vụ", "chức danh", "title", "position"])
        raw_address = get_cell(row, 6, ["địa chỉ", "address", "ngành nghề"])
        raw_notes = get_cell(row, 7, ["ghi chú", "nhu cầu tư vấn / ghi chú", "nhu cầu tư vấn", "notes"])
        raw_camp_code = get_cell(row, 8, ["mã chiến dịch", "mã chiến dịch (*)", "chiến dịch", "campaign_code"])

        errors: List[str] = []
        is_duplicate = False
        duplicate_reasons: List[str] = []
        existing_lead_id = None
        existing_customer_id = None
        campaign_id = None

        if not raw_name:
            errors.append("Họ và tên lead là bắt buộc (cột 1)")

        if not raw_source:
            errors.append("Nguồn lead là bắt buộc (cột 2)")

        if raw_email and not _is_valid_email_format(raw_email):
            errors.append("Email không đúng định dạng")

        if raw_phone and not _is_valid_phone_format(raw_phone):
            errors.append("Số điện thoại không hợp lệ (phải gồm 10-11 chữ số)")

        if raw_camp_code:
            camp = campaign_service.get_campaign_by_code(raw_camp_code)
            if camp:
                campaign_id = camp["id"]
            else:
                errors.append(f"Không tìm thấy chiến dịch với mã '{raw_camp_code}'")

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
    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    result_leads = []

    db = SessionLocal()
    try:
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
                        "company": r.get("company_name"),
                        "company_name": r.get("company_name"),
                        "title": r.get("title"),
                        "address": r.get("address"),
                        "notes": r.get("notes"),
                        "campaign_id": r.get("campaign_id"),
                    }
                    up_lead = update_crm_lead(up_id, update_payload, db=db, current_user=current_user)
                    updated += 1
                    result_leads.append(lead_to_dict(up_lead))
                    continue

            lead_payload = {
                "name": r.get("name"),
                "full_name": r.get("name"),
                "source": r.get("source"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "company": r.get("company_name"),
                "company_name": r.get("company_name"),
                "title": r.get("title"),
                "address": r.get("address"),
                "notes": r.get("notes"),
                "campaign_id": r.get("campaign_id"),
                "customer_id": r.get("existing_customer_id"),
                "status": "NEW",
            }
            new_lead_obj = create_crm_lead(lead_payload, current_user, db=db)
            inserted += 1
            result_leads.append(lead_to_dict(new_lead_obj))

        return {
            "total_rows": len(rows),
            "inserted_count": inserted,
            "updated_count": updated,
            "skipped_count": skipped,
            "failed_count": failed,
            "leads": result_leads,
        }
    finally:
        db.close()


# ============================================================================
# S4-04: DUPLICATE DETECTION, ATTACH TO CUSTOMER & MERGE LEADS
# ============================================================================

def check_lead_duplicates(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    exclude_lead_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> dict:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        matching_leads: List[dict] = []
        matching_customers: List[dict] = []

        norm_target_email = normalize_email(email)
        norm_target_phone = normalize_phone(phone)
        norm_target_company = normalize_company(company_name)

        # 1. So khớp với Lead trong DB
        query = db.query(Lead).filter(Lead.status != "MERGED")
        if exclude_lead_id:
            query = query.filter(Lead.id != exclude_lead_id)
        all_leads = query.all()

        for l in all_leads:
            reasons = []
            score = 0.0

            l_email = normalize_email(l.email)
            if norm_target_email and l_email and norm_target_email == l_email:
                reasons.append(f"Trùng email: {l.email}")
                score = max(score, 1.0)

            l_phone = normalize_phone(l.phone)
            if norm_target_phone and l_phone and norm_target_phone == l_phone:
                reasons.append(f"Trùng số điện thoại: {l.phone}")
                score = max(score, 0.95)

            l_comp = normalize_company(l.company or l.company_name)
            if norm_target_company and l_comp:
                if norm_target_company == l_comp:
                    reasons.append(f"Trùng tên công ty: {l.company or l.company_name}")
                    score = max(score, 0.9)
                elif norm_target_company in l_comp or l_comp in norm_target_company:
                    reasons.append(f"Tên công ty tương tự: {l.company or l.company_name}")
                    score = max(score, 0.75)

            if reasons:
                matching_leads.append({
                    "confidence_score": score,
                    "match_reasons": reasons,
                    "lead": lead_to_dict(l),
                })

        # 2. So khớp với Khách hàng (Customer) đã có trong hệ thống (S4-04)
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

        return {
            "has_duplicates": bool(matching_leads or matching_customers),
            "matching_leads": matching_leads,
            "matching_customers": matching_customers,
        }
    finally:
        if should_close:
            db.close()


def find_lead_duplicates(lead_id: int, db: Optional[Session] = None) -> dict:
    lead = get_lead_by_id(lead_id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lead ID {lead_id}",
        )
    return check_lead_duplicates(
        email=lead.email,
        phone=lead.phone,
        company_name=lead.company or lead.company_name,
        exclude_lead_id=lead_id,
        db=db,
    )


def attach_lead_to_customer(
    lead_id: int,
    customer_id: int,
    create_contact: bool = True,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
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

        lead.customer_id = customer_id
        lead.status = "CONVERTED"
        lead.updated_at = datetime.now(timezone.utc)

        created_contact = None
        if create_contact:
            from app.services import contact_service
            contact_payload = {
                "customer_id": customer_id,
                "name": lead.full_name or lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "position": lead.title or lead.job_title or "Người liên hệ từ Lead",
                "decision_role": "INFLUENCER",
                "is_primary": False,
                "notes": f"Được chuyển đổi từ Lead #{lead_id} (Nguồn: {lead.source})",
            }
            user_str = (current_user.get("full_name") or current_user.get("email")) if current_user else "Admin"
            created_contact = contact_service.create_contact(contact_payload, current_user_username=user_str, db=db)

        db.commit()
        db.refresh(lead)

        res_dict = lead_to_dict(lead)
        res_dict["created_contact"] = created_contact
        return res_dict
    finally:
        if should_close:
            db.close()


def preview_merge_leads(primary_id: int, secondary_id: int, db: Optional[Session] = None) -> dict:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        primary = get_lead_by_id(primary_id, db=db)
        secondary = get_lead_by_id(secondary_id, db=db)

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

        acts_count = len([a for a in FAKE_ACTIVITIES if a.get("lead_id") == secondary_id])
        try:
            from app.models.activity import Activity as ActivityModel
            db_acts = db.query(ActivityModel).filter(ActivityModel.lead_id == secondary_id).count()
            acts_count = max(acts_count, db_acts)
        except Exception:
            pass

        comparison_fields = [
            {"field": "name", "label": "Họ và tên", "primary": primary.full_name or primary.name, "secondary": secondary.full_name or secondary.name},
            {"field": "company_name", "label": "Công ty", "primary": primary.company or primary.company_name, "secondary": secondary.company or secondary.company_name},
            {"field": "title", "label": "Chức danh", "primary": primary.title or primary.job_title, "secondary": secondary.title or secondary.job_title},
            {"field": "email", "label": "Email", "primary": primary.email, "secondary": secondary.email},
            {"field": "phone", "label": "Số điện thoại", "primary": primary.phone, "secondary": secondary.phone},
            {"field": "source", "label": "Nguồn lead", "primary": primary.source, "secondary": secondary.source},
            {"field": "address", "label": "Địa chỉ", "primary": primary.address, "secondary": secondary.address},
            {"field": "notes", "label": "Ghi chú", "primary": primary.notes, "secondary": secondary.notes},
        ]

        return {
            "primary": lead_to_dict(primary),
            "secondary": lead_to_dict(secondary),
            "comparison_fields": comparison_fields,
            "activities_to_transfer": acts_count,
        }
    finally:
        if should_close:
            db.close()


def merge_leads(
    primary_id: int,
    secondary_id: int,
    chosen_fields: Optional[dict] = None,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        primary = db.query(Lead).filter(Lead.id == primary_id).first()
        secondary = db.query(Lead).filter(Lead.id == secondary_id).first()

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

        # 1. Snapshot của secondary
        snapshot_dict = lead_to_dict(secondary)
        for k, v in snapshot_dict.items():
            if isinstance(v, datetime):
                snapshot_dict[k] = v.isoformat()

        user_name = current_user.get("full_name") or current_user.get("email") if current_user else "Admin"

        m_hist = LeadMergeHistory(
            primary_lead_id=primary_id,
            secondary_lead_id=secondary_id,
            secondary_lead_name=secondary.full_name or secondary.name,
            secondary_snapshot=json.dumps(snapshot_dict, ensure_ascii=False),
            merged_by=user_name,
        )
        db.add(m_hist)

        # 2. Áp dụng chosen_fields vào primary
        if chosen_fields:
            for f, val in chosen_fields.items():
                if val is not None and f not in ("id", "created_at"):
                    if f in ("name", "full_name"):
                        primary.name = val
                        primary.full_name = val
                    elif f in ("company", "company_name"):
                        primary.company = val
                        primary.company_name = val
                    elif hasattr(primary, f):
                        setattr(primary, f, val)
        else:
            if not primary.company and secondary.company:
                primary.company = secondary.company
                primary.company_name = secondary.company
            if not primary.title and secondary.title:
                primary.title = secondary.title
            if not primary.email and secondary.email:
                primary.email = secondary.email
            if not primary.phone and secondary.phone:
                primary.phone = secondary.phone
            if not primary.address and secondary.address:
                primary.address = secondary.address
            if not primary.campaign_id and secondary.campaign_id:
                primary.campaign_id = secondary.campaign_id

        merge_note = f"\n[Gộp từ Lead #{secondary_id} ({secondary.full_name or secondary.name}) vào lúc {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}]"
        primary.notes = (primary.notes or "") + merge_note
        primary.updated_at = datetime.now(timezone.utc)

        # 3. Chuyển giao toàn bộ hoạt động (Activities) sang primary
        for a in FAKE_ACTIVITIES:
            if a.get("lead_id") == secondary_id:
                a["lead_id"] = primary_id

        try:
            from app.models.activity import Activity as ActivityModel
            db.query(ActivityModel).filter(ActivityModel.lead_id == secondary_id).update({"lead_id": primary_id})
        except Exception:
            pass

        # 4. Đánh dấu secondary là MERGED
        secondary.status = "MERGED"
        secondary.merged_into_id = primary_id
        secondary.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(primary)

        return lead_to_dict(primary)
    finally:
        if should_close:
            db.close()


def reset_fake_leads() -> None:
    """Hàm khởi tạo dữ liệu mẫu cho kiểm thử."""
    db = SessionLocal()
    try:
        db.query(LeadMergeHistory).delete()
        db.query(Lead).delete()

        sample_leads = [
            Lead(
                id=1,
                full_name="Trần Văn Hùng",
                name="Trần Văn Hùng",
                company="Công ty TNHH SmartTech",
                company_name="Công ty TNHH SmartTech",
                title="Trưởng phòng CNTT",
                email="hung.tran@smarttech.vn",
                phone="0912345678",
                address="Cầu Giấy, Hà Nội",
                source="Hội thảo",
                campaign_id=1,
                status="NEW",
                notes="Gặp mặt tại hội thảo chuyển đổi số",
                owner_id=1,
                team_id=1,
            ),
            Lead(
                id=2,
                full_name="Nguyễn Thị Mai",
                name="Nguyễn Thị Mai",
                company="Tập đoàn Đại Nam",
                company_name="Tập đoàn Đại Nam",
                title="Giám đốc Marketing",
                email="mai.nguyen@dainam.com",
                phone="0987654321",
                address="Quận 1, TP. Hồ Chí Minh",
                source="Sự kiện",
                campaign_id=1,
                status="CONTACTED",
                notes="Nhận danh thiếp tại Tech Expo",
                owner_id=2,
                team_id=1,
            ),
            Lead(
                id=3,
                full_name="Lê Hoàng Long",
                name="Lê Hoàng Long",
                company="Công ty Cổ phần VinaLogistics",
                company_name="Công ty Cổ phần VinaLogistics",
                title="Phó Giám đốc Điều hành",
                email="long.le@vinalogistics.vn",
                phone="0903456789",
                address="Hải Phòng",
                source="Danh thiếp",
                status="QUALIFIED",
                notes="Trao đổi danh thiếp tại gala doanh nhân",
                owner_id=3,
                team_id=1,
            ),
        ]
        for l in sample_leads:
            db.add(l)
        db.commit()
    finally:
        db.close()


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
            "campaign_id": lead.campaign_id,
            "lead_id": lead.id,
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
