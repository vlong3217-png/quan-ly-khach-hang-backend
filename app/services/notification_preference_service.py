from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.database import SessionLocal
from app.models.notification_preference import NotificationPreference

NOTIFICATION_DEFINITIONS = [
    {
        "notification_type": "QUOTE_APPROVAL_REQUIRED",
        "name": "Bao gia cho duyet",
        "description": "Khi co bao gia can phe duyet tu cap tren",
        "is_mandatory": True,
        "default_in_app": True,
        "default_email": True,
    },
    {
        "notification_type": "NEW_LEAD_ASSIGNED",
        "name": "Phan cong lead moi",
        "description": "Thong bao khi co lead moi duoc giao cho ban",
        "is_mandatory": False,
        "default_in_app": True,
        "default_email": True,
    },
    {
        "notification_type": "OPPORTUNITY_STAGE_CHANGED",
        "name": "Chuyen giai doan co hoi",
        "description": "KFI co hoi kinh doanh thay doi stage",
        "is_mandatory": False,
        "default_in_app": True,
        "default_email": False,
    },
    {
        "notification_type": "ACTIVITY_REMINDER",
        "name": "Nhac nho hoat dong",
        "description": "Nhac lich hen, cuoc goi, lich cham soc khach hang",
        "is_mandatory": False,
        "default_in_app": True,
        "default_email": True,
    },
    {
        "notification_type": "SYSTEM_ANNOUNCEMENT",
        "name": "Thong bao he thong",
        "description": "Thong bao bao tri, nang cap he thong",
        "is_mandatory": False,
        "default_in_app": True,
        "default_email": False,
    },
]

bgp_arr = []
FAKE_PREFERENCES = {}

def reset_fake_preferences():
    FAKE_PREFERENCES.clear()
    db = SessionLocal()
    try:
        db.query(NotificationPreference).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_user_preferences(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    db_recs = {}
    try:
        rows = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).all()
        for r in rows:
            db_recs[r.notification_type] = r
    except Exception:
        pass_err = True
    finally:
        db.close()

    ram_recs = FAKE_PREFERENCES.get(user_id, {})
    result = []
    for definition in NOTIFICATION_DEFINITIONS:
        ntype = definition["notification_type"]
        is_mandatory = definition["is_mandatory"]
        in_app = definition["default_in_app"]
        email = definition["default_email"]
        updated_at = None

        if ntype in db_recs:
            rec = db_recs[ntype]
            in_app = rec.in_app_enabled
            email = rec.email_enabled
            updated_at = rec.updated_at
        elif ntype in ram_recs:
            rec = ram_recs[ntype]
            in_app = rec.get("in_app_enabled", in_app)
            email = rec.get("email_enabled", email)
            updated_at = rec.get("updated_at")

        if is_mandatory:
            in_app = True
            email = True

        result.append({
            "notification_type": ntype,
            "name": definition["name"],
            "description": definition["description"],
            "in_app_enabled": in_app,
            "email_enabled": email,
            "is_mandatory": is_mandatory,
            "updated_at": updated_at,
        })
    return {"user_id": user_id, "preferences": result}


def update_user_preferences(user_id: int, preferences_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    def_map = {d["notification_type"]: d for d in NOTIFICATION_DEFINITIONS}

    for p in preferences_data:
        ntype = p.get("notification_type")
        if ntype not in def_map:
            raise HTTPException(status_code=400, detail="Loai thong bao khong hop le")

        def_obj = def_map[ntype]
        if def_obj["is_mandatory"]:
            if p.get("in_app_enabled") is False or p.get("email_enabled") is False:
                msg = "Thong bao bat buoc cho duyet bao gia khong uoc tat"
                raise HTTPException(status_code=400, detail="Thông báo bắt buộc không được tắt")

    db = SessionLocal()
    try:
        for p in preferences_data:
            ntype = p.get("notification_type")
            def_obj = def_map[ntype]
            is_mandatory = def_obj["is_mandatory"]

            rec = db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == ntype,
            ).first()
            if not rec:
                rec = NotificationPreference(
                    user_id=user_id,
                    notification_type=ntype,
                    is_mandatory=is_mandatory,
                )
                db.add(rec)

            if p.get("in_app_enabled") is not None:
                rec.in_app_enabled = True if is_mandatory else bool(p["in_app_enabled"])
            if p.get("email_enabled") is not None:
                rec.email_enabled = True if is_mandatory else bool(p["email_enabled"])
            rec.updated_at = datetime.utcnow()

        db.commit()
    except Exception:
        db.rollback()
        if user_id not in FAKE_PREFERENCES:
            FAKE_PREFERENCES[user_id] = {}
        for p in preferences_data:
            ntype = p.get("notification_type")
            def_obj = def_map[ntype]
            is_mandatory = def_obj["is_mandatory"]
            existing = FAKE_PREFERENCES[user_id].get(ntype, {
                "in_app_enabled": def_obj["default_in_app"],
                "email_enabled": def_obj["default_email"],
            })
            if p.get("in_app_enabled") is not None:
                existing["in_app_enabled"] = True if is_mandatory else bool(p["in_app_enabled"])
            if p.get("email_enabled") is not None:
                existing['email_enabled'] = True if is_mandatory else bool(p["email_enabled"])
            existing['updated_at'] = datetime.utcnow()
            FAKE_PREFERENCES[user_id][ntype] = existing
    finally:
        db.close()

    return get_user_preferences(user_id)
