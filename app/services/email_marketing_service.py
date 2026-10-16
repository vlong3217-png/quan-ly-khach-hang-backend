from datetime import datetime
import re
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models.email_marketing import EmailTemplate, EmailLog
from app.models.customer import Customer
from app.models.contact import Contact
from app.models.lead import Lead
from app.services.activity_service import FAKE_ACTIVITIES

FAKE_EMAIL_TEMPLATES = []
FAKE_EMAIL_LOGS = []

def reset_fake_email_data():
    global FAKE_EMAIL_TEMPLATES, FAKE_EMAIL_LOGS
    FAKE_EMAIL_TEMPLATES.clear()
    FAKE_EMAIL_LOGS.clear()
    db = SessionLocal()
    try:
        db.query(EmailLog).delete()
        db.query(EmailTemplate).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def replace_template_variables(template_str, contact_name=None, company_name=None, owner_name=None, custom_vars=None):
    if not template_str:
        return ''
    mapping = {
        'contact_name': contact_name or 'Quý khách',
        'company_name': company_name or 'Quý công ty',
        'owner_name': owner_name or 'Đại diện kinh doanh',
    }
    if custom_vars:
        for k, v in custom_vars.items():
            mapping[k] = str(v)
    res = template_str
    for k, v in mapping.items():
        res = re.sub(r'\{\{\s*' + re.escape(k) + r'\s*\}\}', str(v), res, flags=re.IGNORECASE)
        res = re.sub(r'\{\s*' + re.escape(k) + r'\s*\}', str(v), res, flags=re.IGNORECASE)
    return res

def create_template(data, current_user):
    name = (data.get('name') or '').strip()
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Tên mẫu email không được để trống')
    if not subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Tiêu đề email không được để trống')
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Nội dung email không được để trống')

    db = SessionLocal()
    try:
        tpl = EmailTemplate(
            name=name,
            subject=subject,
            body=body,
            category=data.get('category') or 'MARKETING',
            is_active=data.get('is_active', True),
            created_by=current_user.get('id', 1),
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return {
            'id': tpl.id,
            'name': tpl.name,
            'subject': tpl.subject,
            'body': tpl.body,
            'category': tpl.category,
            'is_active': tpl.is_active,
            'created_by': tpl.created_by,
            'created_at': tpl.created_at,
            'updated_at': tpl.updated_at,
        }
    except Exception:
        db.rollback()
        new_id = (max(t['id'] for t in FAKE_EMAIL_TEMPLATES) + 1) if FAKE_EMAIL_TEMPLATES else 1
        t_dict = {
            'id': new_id,
            'name': name,
            'subject': subject,
            'body': body,
            'category': data.get('category') or 'MARKETING',
            'is_active': data.get('is_active', True),
            'created_by': current_user.get('id', 1),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        FAKE_EMAIL_TEMPLATES.append(t_dict)
        return t_dict
    finally:
        db.close()

def get_template(template_id):
    db = SessionLocal()
    try:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if tpl:
            return {
                'id': tpl.id,
                'name': tpl.name,
                'subject': tpl.subject,
                'body': tpl.body,
                'category': tpl.category,
                'is_active': tpl.is_active,
                'created_by': tpl.created_by,
                'created_at': tpl.created_at,
                'updated_at': tpl.updated_at,
            }
        ram = next((t for t in FAKE_EMAIL_TEMPLATES if t['id'] == template_id), None)
        if ram:
            return ram
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Không tìm thấy mẫu email')
    finally:
        db.close()

def list_templates(is_active=None, search=None):
    db = SessionLocal()
    try:
        q = db.query(EmailTemplate)
        if is_active is not None:
            q = q.filter(EmailTemplate.is_active == is_active)
        if search:
            s = f'%{search.strip()}%'.lower()
            q = q.filter((EmailTemplate.name.ilike(s)) | (EmailTemplate.subject.ilike(s)))
        rows = q.order_by(desc(EmailTemplate.id)).all()
        if rows:
            return [
                {
                    'id': t.id,
                    'name': t.name,
                    'subject': t.subject,
                    'body': t.body,
                    'category': t.category,
                    'is_active': t.is_active,
                    'created_by': t.created_by,
                    'created_at': t.created_at,
                    'updated_at': t.updated_at,
                }
                for t in rows
            ]
        res = list(FAKE_EMAIL_TEMPLATES)
        if is_active is not None:
            res = [t for t in res if t['is_active'] == is_active]
        if search:
            s = search.lower()
            res = [t for t in res if s in t['name'].lower() or s in t['subject'].lower()]
        return res
    finally:
        db.close()

def update_template(template_id, data):
    db = SessionLocal()
    try:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if tpl:
            for k in ['name', 'subject', 'body', 'category', 'is_active']:
                if data.get(k) is not None:
                    setattr(tpl, k, data[k])
            db.commit()
            db.refresh(tpl)
            return {
                'id': tpl.id,
                'name': tpl.name,
                'subject': tpl.subject,
                'body': tpl.body,
                'category': tpl.category,
                'is_active': tpl.is_active,
                'created_by': tpl.created_by,
                'created_at': tpl.created_at,
                'updated_at': tpl.updated_at,
            }
        ram = next((t for t in FAKE_EMAIL_TEMPLATES if t['id'] == template_id), None)
        if ram:
            for k in ['name', 'subject', 'body', 'category', 'is_active']:
                if data.get(k) is not None:
                    ram[k] = data[k]
            ram['updated_at'] = datetime.utcnow()
            return ram
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Không tìm thấy mẫu email')
    finally:
        db.close()

def delete_template(template_id):
    global FAKE_EMAIL_TEMPLATES
    db = SessionLocal()
    try:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if tpl:
            db.delete(tpl)
            db.commit()
            return True
        initial_len = len(FAKE_EMAIL_TEMPLATES)
        FAKE_EMAIL_TEMPLATES = [t for t in FAKE_EMAIL_TEMPLATES if t['id'] != template_id]
        if len(FAKE_EMAIL_TEMPLATES) < initial_len:
            return True
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Không tìm thấy mẫu email để xóa')
    finally:
        db.close()

def send_marketing_email(payload, current_user):
    recipient_email = (payload.get('recipient_email') or '').strip()
    if not recipient_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email người nhận không được để trống')

    template_id = payload.get('template_id')
    raw_subject = payload.get('subject') or ''
    raw_body = payload.get('body') or ''

    if template_id:
        tpl = get_template(template_id)
        if not raw_subject:
            raw_subject = tpl['subject']
        if not raw_body:
            raw_body = tpl['body']

    if not raw_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Tiêu đề email không được để trống')
    if not raw_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Nội dung email không được để trống')

    contact_name = None
    company_name = None
    owner_name = current_user.get('full_name') or current_user.get('username')

    customer_id = payload.get('customer_id')
    contact_id = payload.get('contact_id')
    lead_id = payload.get('lead_id')

    db = SessionLocal()
    try:
        if customer_id:
            c = db.query(Customer).filter(Customer.id == customer_id).first()
            if c:
                company_name = c.name
        if contact_id:
            ct = db.query(Contact).filter(Contact.id == contact_id).first()
            if ct:
                contact_name = ct.name or f'{ct.first_name} {ct.last_name}'.strip()
                if not company_name and ct.company_name:
                    company_name = ct.company_name
        if lead_id and not contact_name:
            ld = db.query(Lead).filter(Lead.id == lead_id).first()
            if ld:
                contact_name = ld.full_name or ld.name
                if not company_name and ld.company_name:
                    company_name = ld.company_name
    finally:
        db.close()

    final_subject = replace_template_variables(
        raw_subject,
        contact_name=contact_name,
        company_name=company_name,
        owner_name=owner_name,
        custom_vars=payload.get('variables'),
    )
    final_body = replace_template_variables(
        raw_body,
        contact_name=contact_name,
        company_name=company_name,
        owner_name=owner_name,
        custom_vars=payload.get('variables'),
    )

    fail_test = bool(payload.get('fail_silently')) or ('invalid' in recipient_email.lower()) or ('fail' in recipient_email.lower())
    email_status = 'FAILED' if fail_test else 'SENT'
    error_msg = 'SMTP connection timeout / Invalid recipient address' if fail_test else None
    sent_time = None if fail_test else datetime.utcnow()

    sender_id = current_user.get('id', 1)

    db = SessionLocal()
    try:
        log_entry = EmailLog(
            template_id=template_id,
            customer_id=customer_id,
            contact_id=contact_id,
            lead_id=lead_id,
            sender_id=sender_id,
            recipient_email=recipient_email,
            subject=final_subject,
            body=final_body,
            status=email_status,
            error_message=error_msg,
            retry_count=0,
            sent_at=sent_time,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        res_log = {
            'id': log_entry.id,
            'template_id': log_entry.template_id,
            'customer_id': log_entry.customer_id,
            'contact_id': log_entry.contact_id,
            'lead_id': log_entry.lead_id,
            'sender_id': log_entry.sender_id,
            'recipient_email': log_entry.recipient_email,
            'subject': log_entry.subject,
            'body': log_entry.body,
            'status': log_entry.status,
            'error_message': log_entry.error_message,
            'retry_count': log_entry.retry_count,
            'sent_at': log_entry.sent_at,
            'created_at': log_entry.created_at,
            'updated_at': log_entry.updated_at,
        }
    except Exception:
        db.rollback()
        new_id = (max(l['id'] for l in FAKE_EMAIL_LOGS) + 1) if FAKE_EMAIL_LOGS else 1
        res_log = {
            'id': new_id,
            'template_id': template_id,
            'customer_id': customer_id,
            'contact_id': contact_id,
            'lead_id': lead_id,
            'sender_id': sender_id,
            'recipient_email': recipient_email,
            'subject': final_subject,
            'body': final_body,
            'status': email_status,
            'error_message': error_msg,
            'retry_count': 0,
            'sent_at': sent_time,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        FAKE_EMAIL_LOGS.append(res_log)
    finally:
        db.close()

    if email_status == 'SENT' and (customer_id or contact_id):
        try:
            act_id = (max(a.get('id', 0) for a in FAKE_ACTIVITIES) + 1) if FAKE_ACTIVITIES else 1
            FAKE_ACTIVITIES.append({
                'id': act_id,
                'title': f'Đã gửi email: {final_subject}',
                'type': 'EMAIL',
                'description': final_body[:500] if len(final_body) > 500 else final_body,
                'customer_id': customer_id,
                'contact_id': contact_id,
                'owner_id': sender_id,
                'created_at': datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    return res_log

def retry_failed_email(email_log_id, current_user):
    db = SessionLocal()
    try:
        log_entry = db.query(EmailLog).filter(EmailLog.id == email_log_id).first()
        if log_entry:
            if log_entry.status == 'SENT':
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email này đã gửi thành công trước đó')
            log_entry.status = 'SENT'
            log_entry.error_message = None
            log_entry.retry_count = (log_entry.retry_count or 0) + 1
            log_entry.sent_at = datetime.utcnow()
            db.commit()
            db.refresh(log_entry)

            if log_entry.customer_id:
                try:
                    act_id = (max(a.get('id', 0) for a in FAKE_ACTIVITIES) + 1) if FAKE_ACTIVITIES else 1
                    FAKE_ACTIVITIES.append({
                        'id': act_id,
                        'title': f'Đã gửi lại thành công email: {log_entry.subject}',
                        'type': 'EMAIL',
                        'description': log_entry.body[:500],
                        'customer_id': log_entry.customer_id,
                        'contact_id': log_entry.contact_id,
                        'owner_id': current_user.get('id', 1),
                        'created_at': datetime.utcnow().isoformat(),
                    })
                except Exception:
                    pass

            return {
                'id': log_entry.id,
                'template_id': log_entry.template_id,
                'customer_id': log_entry.customer_id,
                'contact_id': log_entry.contact_id,
                'lead_id': log_entry.lead_id,
                'sender_id': log_entry.sender_id,
                'recipient_email': log_entry.recipient_email,
                'subject': log_entry.subject,
                'body': log_entry.body,
                'status': log_entry.status,
                'error_message': log_entry.error_message,
                'retry_count': log_entry.retry_count,
                'sent_at': log_entry.sent_at,
                'created_at': log_entry.created_at,
                'updated_at': log_entry.updated_at,
            }

        ram_entry = next((l for l in FAKE_EMAIL_LOGS if l['id'] == email_log_id), None)
        if not ram_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Không tìm thấy nhật ký gửi email')
        if ram_entry['status'] == 'SENT':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email này đã gửi thành công trước đó')
        ram_entry['status'] = 'SENT'
        ram_entry['error_message'] = None
        ram_entry['retry_count'] = (ram_entry.get('retry_count', 0)) + 1
        ram_entry['sent_at'] = datetime.utcnow()
        return ram_entry
    finally:
        db.close()

def list_email_logs(customer_id=None, status=None, skip=0, limit=50):
    db = SessionLocal()
    try:
        q = db.query(EmailLog)
        if customer_id:
            q = q.filter(EmailLog.customer_id == customer_id)
        if status:
            q = q.filter(EmailLog.status == status.upper())
        rows = q.order_by(desc(EmailLog.id)).offset(skip).limit(limit).all()
        if rows:
            return [
                {
                    'id': l.id,
                    'template_id': l.template_id,
                    'customer_id': l.customer_id,
                    'contact_id': l.contact_id,
                    'lead_id': l.lead_id,
                    'sender_id': l.sender_id,
                    'recipient_email': l.recipient_email,
                    'subject': l.subject,
                    'body': l.body,
                    'status': l.status,
                    'error_message': l.error_message,
                    'retry_count': l.retry_count,
                    'sent_at': l.sent_at,
                    'created_at': l.created_at,
                    'updated_at': l.updated_at,
                }
                for l in rows
            ]
        res = list(FAKE_EMAIL_LOGS)
        if customer_id:
            res = [l for l in res if l.get('customer_id') == customer_id]
        if status:
            res = [l for l in res if l.get('status') == status.upper()]
        return res[skip : skip + limit]
    finally:
        db.close()
