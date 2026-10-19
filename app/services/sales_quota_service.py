from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models.sales_quota import SalesQuota, SalesQuotaAuditLog
from app.models.opportunity import Opportunity

FAKE_SALES_QUOTAS = []
FAKE_QUOTA_AUDIT_LOGS = []

def reset_fake_quotas():
    FAKE_SALES_QUOTAS.clear()
    FAKE_QUOTA_AUDIT_LOGS.clear()
    db = SessionLocal()
    try:
        db.query(SalesQuotaAuditLog).delete()
        db.query(SalesQuota).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def is_period_passed(quota_type: str, year: int, period_number: int) -> bool:
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month
    current_quarter = (current_month - 1) // 3 + 1

    if year < current_year:
        return True
    if year > current_year:
        return False

    if quota_type.lower() == "month":
        return period_number < current_month
    elif quota_type.lower() == "quarter":
        return period_number < current_quarter
    return False

def calculate_attainment(target: float, achieved: float) -> float:
    if not target or target <= 0:
        return 0.0
    return round((achieved / target) * 100, 2)

def create_sales_quota(data: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    quota_type = data["quota_type"].lower()
    period_name = data["period_name"]
    year = int(data["year"])
    period_number = int(data["period_number"])
    target_type = data["target_type"].lower()
    user_id = data.get("user_id")
    team_id = data.get("team_id")
    target_amount = float(data.get("target_amount", 0.0))

    if target_type == "user" and not user_id:
        raise HTTPException(status_code=400, detail="Chỉ tiêu nhân viên phải có user_id")
    if target_type == "team" and not team_id:
        raise HTTPException(status_code=400, detail="Chỉ tiêu nhóm phải có team_id")

    creator_id = current_user.get("id", 1)
    passed = is_period_passed(quota_type, year, period_number)
    lock_reason = "Đã qua kỳ chỉ tiêu" if passed else None

    db = SessionLocal()
    try:
        quota = SalesQuota(
            quota_type=quota_type,
            period_name=period_name,
            year=year,
            period_number=period_number,
            target_type=target_type,
            user_id=user_id,
            team_id=team_id,
            target_amount=target_amount,
            achieved_amount=0.0,
            is_locked=passed,
            lock_reason=lock_reason,
            created_by=creator_id,
        )
        db.add(quota)
        db.commit()
        db.refresh(quota)
        return {
            "id": quota.id,
            "quota_type": quota.quota_type,
            "period_name": quota.period_name,
            "year": quota.year,
            "period_number": quota.period_number,
            "target_type": quota.target_type,
            "user_id": quota.user_id,
            "team_id": quota.team_id,
            "target_amount": quota.target_amount,
            "achieved_amount": quota.achieved_amount,
            "attainment_rate": calculate_attainment(quota.target_amount, quota.achieved_amount),
            "is_locked": quota.is_locked,
            "lock_reason": quota.lock_reason,
            "created_by": quota.created_by,
            "created_at": quota.created_at,
            "updated_at": quota.updated_at,
        }
    except Exception:
        db.rollback()
        new_id = (max(q["id"] for q in FAKE_SALES_QUOTAS) + 1) if FAKE_SALES_QUOTAS else 1
        q_dict = {
            "id": new_id,
            "quota_type": quota_type,
            "period_name": period_name,
            "year": year,
            "period_number": period_number,
            "target_type": target_type,
            "user_id": user_id,
            "team_id": team_id,
            "target_amount": target_amount,
            "achieved_amount": 0.0,
            "attainment_rate": 0.0,
            "is_locked": passed,
            "lock_reason": lock_reason,
            "created_by": creator_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        FAKE_SALES_QUOTAS.append(q_dict)
        return q_dict
    finally:
        db.close()

def update_sales_quota(quota_id: int, data: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    new_target = float(data["target_amount"])
    reason = (data.get("reason") or "").strip()
    updater_id = current_user.get("id", 1)

    db = SessionLocal()
    try:
        quota = db.query(SalesQuota).filter(SalesQuota.id == quota_id).first()
        if quota:
            passed = is_period_passed(quota.quota_type, quota.year, quota.period_number)
            is_locked = quota.is_locked or passed

            if is_locked and not reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Chỉ tiêu đã qua kỳ và bị khoá. Sửa chỉ tiêu bắt buộc phải có lý do.",
                )

            old_target = quota.target_amount
            quota.target_amount = new_target
            if is_locked:
                quota.is_locked = True
                quota.lock_reason = "Đã qua kỳ và đã sửa có lý do"
            quota.updated_at = datetime.utcnow()

            # Ghi audit log
            audit = SalesQuotaAuditLog(
                quota_id=quota.id,
                action="UPDATE_LOCKED_QUOTA" if is_locked else "UPDATE_QUOTA",
                old_target_amount=old_target,
                new_target_amount=new_target,
                reason=reason or "Cập nhật chỉ tiêu trước khi khoá",
                changed_by=updater_id,
            )
            db.add(audit)
            db.commit()
            db.refresh(quota)

            return {
                "id": quota.id,
                "quota_type": quota.quota_type,
                "period_name": quota.period_name,
                "year": quota.year,
                "period_number": quota.period_number,
                "target_type": quota.target_type,
                "user_id": quota.user_id,
                "team_id": quota.team_id,
                "target_amount": quota.target_amount,
                "achieved_amount": quota.achieved_amount,
                "attainment_rate": calculate_attainment(quota.target_amount, quota.achieved_amount),
                "is_locked": quota.is_locked,
                "lock_reason": quota.lock_reason,
                "created_by": quota.created_by,
                "created_at": quota.created_at,
                "updated_at": quota.updated_at,
            }

        # fallback RAM
        q_item = next((q for q in FAKE_SALES_QUOTAS if q["id"] == quota_id), None)
        if not q_item:
            raise HTTPException(status_code=404, detail="Không tìm thấy chỉ tiêu")

        passed = is_period_passed(q_item["quota_type"], q_item["year"], q_item["period_number"])
        is_locked = q_item["is_locked"] or passed
        if is_locked and not reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ tiêu đã qua kỳ và bị khoá. Sửa chỉ tiêu bắt buộc phải có lý do.",
            )

        old_target = q_item["target_amount"]
        q_item["target_amount"] = new_target
        if is_locked:
            q_item["is_locked"] = True
            q_item["lock_reason"] = "Đã qua kỳ và đã sửa có lý do"
        q_item["updated_at"] = datetime.utcnow()
        q_item["attainment_rate"] = calculate_attainment(new_target, q_item["achieved_amount"])

        # Record RAM audit log
        audit_id = (max(a["id"] for a in FAKE_QUOTA_AUDIT_LOGS) + 1) if FAKE_QUOTA_AUDIT_LOGS else 1
        FAKE_QUOTA_AUDIT_LOGS.append({
            "id": audit_id,
            "quota_id": quota_id,
            "action": "UPDATE_LOCKED_QUOTA" if is_locked else "UPDATE_QUOTA",
            "old_target_amount": old_target,
            "new_target_amount": new_target,
            "reason": reason or "Cập nhật chỉ tiêu",
            "changed_by": updater_id,
            "changed_at": datetime.utcnow(),
        })
        return q_item
    finally:
        db.close()

def list_sales_quotas(
    current_user: Dict[str, Any],
    period_name: Optional[str] = None,
    quota_type: Optional[str] = None,
    team_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    role = current_user.get("role", "SALES").upper()
    user_id = current_user.get("id")

    db = SessionLocal()
    try:
        q = db.query(SalesQuota)
        if role in ["SALES", "USER", "EMPLOYEE"]:
            # Nhân viên chỉ xem được chỉ tiêu của chính mình
            q = q.filter(SalesQuota.target_type == "user", SalesQuota.user_id == user_id)
        else:
            if team_id:
                q = q.filter(SalesQuota.team_id == team_id)

        if period_name:
            q = q.filter(SalesQuota.period_name == period_name)
        if quota_type:
            q = q.filter(SalesQuota.quota_type == quota_type.lower())

        rows = q.all()
        if rows:
            return [
                {
                    "id": r.id,
                    "quota_type": r.quota_type,
                    "period_name": r.period_name,
                    "year": r.year,
                    "period_number": r.period_number,
                    "target_type": r.target_type,
                    "user_id": r.user_id,
                    "team_id": r.team_id,
                    "target_amount": r.target_amount,
                    "achieved_amount": r.achieved_amount,
                    "attainment_rate": calculate_attainment(r.target_amount, r.achieved_amount),
                    "is_locked": r.is_locked,
                    "lock_reason": r.lock_reason,
                    "created_by": r.created_by,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]

        # RAM fallback
        res = list(FAKE_SALES_QUOTAS)
        if role in ["SALES", "USER", "EMPLOYEE"]:
            res = [r for r in res if r.get("target_type") == "user" and r.get("user_id") == user_id]
        elif team_id:
            res = [r for r in res if r.get("team_id") == team_id]

        if period_name:
            res = [r for r in res if r.get("period_name") == period_name]
        if quota_type:
            res = [r for r in res if r.get("quota_type") == quota_type.lower()]
        return res
    except Exception:
        return []
    finally:
        db.close()

def validate_team_quota(team_id: str, period_name: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        team_quota = db.query(SalesQuota).filter(
            SalesQuota.target_type == "team",
            SalesQuota.team_id == team_id,
            SalesQuota.period_name == period_name,
        ).first()

        member_quotas = db.query(SalesQuota).filter(
            SalesQuota.target_type == "user",
            SalesQuota.team_id == team_id,
            SalesQuota.period_name == period_name,
        ).all()

        team_target = team_quota.target_amount if team_quota else 0.0
        members_total = sum(m.target_amount for m in member_quotas) if member_quotas else 0.0

        if not team_quota and not member_quotas:
            # Check RAM
            t_ram = next((q for q in FAKE_SALES_QUOTAS if q.get("target_type") == "team" and q.get("team_id") == team_id and q.get("period_name") == period_name), None)
            m_ram = [q for q in FAKE_SALES_QUOTAS if q.get("target_type") == "user" and q.get("team_id") == team_id and q.get("period_name") == period_name]
            team_target = t_ram["target_amount"] if t_ram else 0.0
            members_total = sum(m["target_amount"] for m in m_ram)

        diff = round(team_target - members_total, 2)
        is_valid = (diff == 0.0)
        warning = None
        if not is_valid:
            warning = f"Cảnh báo: Chỉ tiêu nhóm ({team_target:,.0f}) không bằng tổng chỉ tiêu các thành viên ({members_total:,.0f}), lệch {diff:,.0f} VND"

        return {
            "is_valid": is_valid,
            "team_id": team_id,
            "period_name": period_name,
            "team_target": team_target,
            "members_total_target": members_total,
            "difference": diff,
            "warning": warning,
        }
    finally:
        db.close()

def get_quota_audit_logs(quota_id: int) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(SalesQuotaAuditLog).filter(SalesQuotaAuditLog.quota_id == quota_id).order_by(desc(SalesQuotaAuditLog.id)).all()
        if rows:
            return [
                {
                    "id": r.id,
                    "quota_id": r.quota_id,
                    "action": r.action,
                    "old_target_amount": r.old_target_amount,
                    "new_target_amount": r.new_target_amount,
                    "reason": r.reason,
                    "changed_by": r.changed_by,
                    "changed_at": r.changed_at,
                }
                for r in rows
            ]
        return [l for l in FAKE_QUOTA_AUDIT_LOGS if l["quota_id"] == quota_id]
    finally:
        db.close()