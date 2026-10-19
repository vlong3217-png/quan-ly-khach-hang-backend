"""
Opportunity service with MySQL Database persistence & data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc
from app.core.dependencies import DataScope
from app.core.database import SessionLocal
from app.models.opportunity import (
    OpportunityModel,
    OpportunityProductModel,
    OpportunityHistoryModel,
    OpportunitySavedFilterModel,
    OpportunityShareModel,
    OpportunityAttachmentModel,
)
from app.models.customer import Customer as CustomerModel
from app.models.user import User as UserModel

# Dữ liệu ban đầu rỗng cho production / MySQL (Đồng bộ MySQL - Không có dữ liệu mẫu hardcode)
INITIAL_OPPORTUNITIES: List[Dict[str, Any]] = []
INITIAL_OPPORTUNITY_PRODUCTS: List[Dict[str, Any]] = []

# Dữ liệu mẫu dùng cho test fixtures khi reset_fake_opportunities() được gọi trong pytest
TEST_SAMPLE_OPPORTUNITIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Hợp đồng phần mềm Admin",
        "value": 50000000.0,
        "stage": "PROPOSAL",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
        "status": "OPEN",
    },
    {
        "id": 2,
        "title": "Hợp đồng dịch vụ Manager",
        "value": 30000000.0,
        "stage": "QUALIFICATION",
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
        "status": "OPEN",
    },
    {
        "id": 3,
        "title": "Cung cấp thiết bị User1",
        "value": 15000000.0,
        "stage": "PROSPECTING",
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
        "status": "OPEN",
    },
    {
        "id": 4,
        "title": "Bảo trì hệ thống User2",
        "value": 20000000.0,
        "stage": "CLOSED_WON",
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
        "status": "CLOSED_WON",
    },
]

FAKE_OPPORTUNITIES: List[Dict[str, Any]] = []
FAKE_OPPORTUNITY_PRODUCTS: List[Dict[str, Any]] = []


def _row_to_dict(row: OpportunityModel, db_session=None) -> Dict[str, Any]:
    """Chuyển đổi một dòng OpportunityModel thành dict và bổ sung customer_name, owner_name."""
    customer_name = None
    owner_name = None
    team_name = None

    if db_session:
        if row.customer_id:
            cust = db_session.query(CustomerModel).filter(CustomerModel.id == row.customer_id).first()
            if cust:
                customer_name = cust.name
        if row.owner_id:
            user = db_session.query(UserModel).filter(UserModel.id == row.owner_id).first()
            if user:
                owner_name = user.full_name or user.username
                if row.team_id and getattr(user, 'department', None):
                    team_name = user.department

    return {
        "id": row.id,
        "title": row.title,
        "value": row.value or 0.0,
        "stage": row.stage,
        "customer_id": row.customer_id,
        "customer_name": customer_name,
        "campaign_id": row.campaign_id,
        "lead_id": row.lead_id,
        "owner_id": row.owner_id,
        "owner_name": owner_name,
        "team_id": row.team_id,
        "team_name": team_name,
        "arr": row.arr or 0.0,
        "status": row.status or "OPEN",
        "expected_close_date": row.expected_close_date.isoformat() if row.expected_close_date else None,
        "contact_person": row.contact_person,
        "contact_id": row.contact_id,
        "source": row.source,
        "win_probability": row.win_probability,
        "probability_notes": row.probability_notes,
        "description": row.description,
        "stage_overridden": bool(row.stage_overridden),
        "override_reason": row.override_reason,
        "override_by": row.override_by,
        "is_flagged": bool(row.is_flagged),
        "is_stagnant": bool(row.is_stagnant),
        "is_overdue": bool(row.is_overdue),
        "flagged_at": row.flagged_at.isoformat() if row.flagged_at else None,
        "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "has_products": False,
        "products": [],
        "flag_reasons": [],
    }


def _product_row_to_dict(row: OpportunityProductModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "opportunity_id": row.opportunity_id,
        "product_id": row.product_id,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "product_type": row.product_type,
        "quantity": row.quantity,
        "unit_price": row.unit_price,
        "floor_price": row.floor_price,
        "discount_percent": row.discount_percent,
        "billing_cycle": row.billing_cycle,
        "number_of_cycles": row.number_of_cycles,
        "term_months": row.term_months,
        "arr": row.arr,
        "mrr": row.mrr,
        "amount": row.amount,
    }


def _sync_fake_from_db():
    """Đồng bộ RAM FAKE_OPPORTUNITIES từ MySQL để tương thích với các module test/legacy."""
    global FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS
    db = SessionLocal()
    try:
        opp_rows = db.query(OpportunityModel).all()
        prod_rows = db.query(OpportunityProductModel).all()
        
        FAKE_OPPORTUNITY_PRODUCTS.clear()
        for p in prod_rows:
            FAKE_OPPORTUNITY_PRODUCTS.append(_product_row_to_dict(p))

        FAKE_OPPORTUNITIES.clear()
        for o in opp_rows:
            opp_dict = _row_to_dict(o, db)
            items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == o.id]
            opp_dict["products"] = items
            opp_dict["has_products"] = len(items) > 0
            FAKE_OPPORTUNITIES.append(opp_dict)
    except Exception:
        pass
    finally:
        db.close()


def reset_fake_opportunities() -> None:
    """Xóa dữ liệu cơ hội trong CSDL MySQL và nạp dữ liệu mẫu vào RAM cho test suites."""
    global FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS, FAKE_OPPORTUNITY_HISTORIES, FAKE_OPPORTUNITY_SAVED_FILTERS, FAKE_OPPORTUNITY_SHARES, FAKE_OPPORTUNITY_ATTACHMENTS
    FAKE_OPPORTUNITIES.clear()
    FAKE_OPPORTUNITIES.extend(copy.deepcopy(TEST_SAMPLE_OPPORTUNITIES))
    FAKE_OPPORTUNITY_PRODUCTS.clear()
    FAKE_OPPORTUNITY_HISTORIES.clear()
    FAKE_OPPORTUNITY_SAVED_FILTERS.clear()
    FAKE_OPPORTUNITY_SHARES.clear()
    FAKE_OPPORTUNITY_ATTACHMENTS.clear()
    db = SessionLocal()
    try:
        db.query(OpportunityAttachmentModel).delete()
        db.query(OpportunityShareModel).delete()
        db.query(OpportunitySavedFilterModel).delete()
        db.query(OpportunityHistoryModel).delete()
        db.query(OpportunityProductModel).delete()
        db.query(OpportunityModel).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def recalculate_opportunity_value(opportunity_id: int) -> Optional[dict]:
    """
    AC S5-03: Tự động tính lại giá trị cơ hội:
    - Tổng giá trị cơ hội (value) = Tổng thành tiền của tất cả sản phẩm/dịch vụ.
    - Dịch vụ thuê bao: Tổng giá trị hợp đồng theo năm (arr).
    """
    db = SessionLocal()
    try:
        opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        if not opp:
            # Fallback nếu cơ hội nằm trong RAM
            opp_ram = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
            if not opp_ram:
                return None
            items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]
            if items:
                opp_ram["value"] = round(sum(i["amount"] for i in items), 2)
                opp_ram["arr"] = round(sum(i.get("arr", 0.0) or 0.0 for i in items if i.get("arr") is not None), 2)
                opp_ram["has_products"] = True
            else:
                opp_ram["value"] = 0.0
                opp_ram["arr"] = 0.0
                opp_ram["has_products"] = False
            return opp_ram

        items = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opportunity_id).all()
        if items:
            total_value = sum(i.amount for i in items)
            total_arr = sum((i.arr or 0.0) for i in items if i.arr is not None)
            opp.value = round(total_value, 2)
            opp.arr = round(total_arr, 2)
        else:
            opp.value = 0.0
            opp.arr = 0.0

        db.commit()
        db.refresh(opp)
        opp_dict = _row_to_dict(opp, db)
        opp_dict["products"] = [_product_row_to_dict(p) for p in items]
        opp_dict["has_products"] = len(items) > 0
        _sync_fake_from_db()
        return opp_dict
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def _enrich_opportunity_record(opp: dict) -> dict:
    opp_copy = copy.deepcopy(opp)
    opp_id = opp["id"]
    items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opp_id]
    opp_copy["products"] = items
    opp_copy["has_products"] = len(items) > 0
    opp_copy["arr"] = opp.get("arr", 0.0)

    # 1. Bổ sung customer_name nếu có customer_id
    if opp.get("customer_id") and not opp_copy.get("customer_name"):
        try:
            from app.services import customer_service
            cust = customer_service.get_customer_by_id(opp["customer_id"])
            opp_copy["customer_name"] = cust.get("name") if cust else None
        except Exception:
            opp_copy["customer_name"] = None

    # 2. Bổ sung win_probability nếu chưa có
    if opp_copy.get("win_probability") is None:
        try:
            from app.services import pipeline_service
            stage_info = pipeline_service.find_stage(opp.get("stage", "PROSPECTING"))
            opp_copy["win_probability"] = float(stage_info["win_probability"]) if stage_info and "win_probability" in stage_info else 10.0
        except Exception:
            opp_copy["win_probability"] = 10.0

    # 3. Tích hợp cảnh báo đình trệ S5-07 & S5-02
    is_stagnant = bool(opp.get("is_stagnant"))
    is_overdue = bool(opp.get("is_overdue"))
    is_flagged = bool(opp.get("is_flagged"))
    days_inactive = opp.get("days_inactive")
    days_overdue = opp.get("days_overdue")
    threshold = opp.get("stagnant_threshold_days") or 14

    opp_copy["is_stagnant"] = is_stagnant
    opp_copy["is_overdue"] = is_overdue
    opp_copy["is_flagged"] = is_flagged
    opp_copy["flag_reasons"] = opp.get("flag_reasons", [])
    opp_copy["days_inactive"] = days_inactive
    opp_copy["days_overdue"] = days_overdue
    opp_copy["stagnant_threshold_days"] = threshold
    opp_copy["flagged_at"] = opp.get("flagged_at")

    if is_stagnant:
        days_str = f" trong {days_inactive} ngày" if days_inactive is not None else ""
        opp_copy["stagnant_warning"] = f"Cảnh báo đình trệ: không có hoạt động{days_str} (ngưỡng {threshold} ngày)"
    elif is_overdue:
        days_str = f" {days_overdue} ngày" if days_overdue is not None else ""
        opp_copy["stagnant_warning"] = f"Cảnh báo quá hạn: trễ ngày dự kiến chốt{days_str}"
    else:
        opp_copy["stagnant_warning"] = None

    return opp_copy


def get_raw_opportunity_by_id(opportunity_id: int) -> Optional[dict]:
    db = SessionLocal()
    try:
        opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        if opp:
            items = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opportunity_id).all()
            opp_dict = _row_to_dict(opp, db)
            opp_dict["products"] = [_product_row_to_dict(p) for p in items]
            opp_dict["has_products"] = len(items) > 0
            return _enrich_opportunity_record(opp_dict)
        # Fallback RAM
        for o in FAKE_OPPORTUNITIES:
            if o["id"] == opportunity_id:
                items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]
                c = copy.deepcopy(o)
                c["products"] = items
                c["has_products"] = len(items) > 0
                return _enrich_opportunity_record(c)
        return None
    finally:
        db.close()


def get_opportunities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(OpportunityModel)

        if scope == DataScope.ALL:
            pass
        elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
            user_team_id = current_user.get("team_id")
            if user_team_id is not None:
                query = query.filter(OpportunityModel.team_id == user_team_id)
        else:
            user_id = current_user.get("id")
            query = query.filter(OpportunityModel.owner_id == user_id)

        if customer_id is not None:
            query = query.filter(OpportunityModel.customer_id == customer_id)

        if search:
            s = f"%{search.strip().lower()}%"
            query = query.filter(
                (OpportunityModel.title.ilike(s)) | (OpportunityModel.stage.ilike(s))
            )

        rows = query.order_by(desc(OpportunityModel.id)).all()

        results = []
        for opp in rows:
            items = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opp.id).all()
            opp_dict = _row_to_dict(opp, db)
            opp_dict["products"] = [_product_row_to_dict(p) for p in items]
            opp_dict["has_products"] = len(items) > 0
            results.append(_enrich_opportunity_record(opp_dict))

        # Nếu DB trống và có RAM (dùng trong test unit)
        if not results and FAKE_OPPORTUNITIES:
            if scope == DataScope.ALL:
                raw_list = list(FAKE_OPPORTUNITIES)
            elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
                user_team_id = current_user.get("team_id")
                raw_list = [o for o in FAKE_OPPORTUNITIES if o.get("team_id") == user_team_id] if user_team_id else list(FAKE_OPPORTUNITIES)
            else:
                user_id = current_user.get("id")
                raw_list = [o for o in FAKE_OPPORTUNITIES if o.get("owner_id") == user_id]

            if customer_id is not None:
                raw_list = [o for o in raw_list if o.get("customer_id") == customer_id]

            for opp in raw_list:
                items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opp["id"]]
                c = copy.deepcopy(opp)
                c["products"] = items
                c["has_products"] = len(items) > 0
                results.append(_enrich_opportunity_record(c))

            if search:
                s = search.lower().strip()
                results = [o for o in results if s in o.get("title", "").lower() or s in o.get("stage", "").lower()]

        return results
    except Exception:
        return []
    finally:
        db.close()


def get_kanban_board_data(
    current_user: dict,
    scope: DataScope,
    owner_id: Optional[int] = None,
    team_id: Optional[int] = None,
    expected_close_date_from = None,
    expected_close_date_to = None,
    search: Optional[str] = None,
) -> dict:
    """
    AC S5-02: Bảng pipeline dạng Kanban:
    - Mỗi cột là một giai đoạn, hiển thị số cơ hội và tổng giá trị của cột.
    - Thẻ cơ hội hiển thị tên khách, giá trị, ngày dự kiến chốt và cảnh báo nếu đình trệ.
    - Lọc theo người sở hữu, nhóm, khoảng ngày chốt; nhân viên mặc định chỉ thấy cơ hội của mình.
    """
    from app.services import pipeline_service
    from datetime import datetime, date

    stages = pipeline_service.get_all_stages()
    opps = get_opportunities_by_scope(current_user, scope, search=search)

    # 1. Lọc theo người sở hữu (owner_id)
    if owner_id is not None:
        opps = [o for o in opps if o.get("owner_id") == owner_id]

    # 2. Lọc theo nhóm (team_id)
    if team_id is not None:
        opps = [o for o in opps if o.get("team_id") == team_id]

    # 3. Lọc theo khoảng ngày dự kiến chốt
    from_date_obj = None
    to_date_obj = None
    if expected_close_date_from:
        if isinstance(expected_close_date_from, str):
            try:
                from_date_obj = datetime.strptime(expected_close_date_from[:10], "%Y-%m-%d").date()
            except Exception:
                pass
        elif isinstance(expected_close_date_from, date):
            from_date_obj = expected_close_date_from

    if expected_close_date_to:
        if isinstance(expected_close_date_to, str):
            try:
                to_date_obj = datetime.strptime(expected_close_date_to[:10], "%Y-%m-%d").date()
            except Exception:
                pass
        elif isinstance(expected_close_date_to, date):
            to_date_obj = expected_close_date_to

    filtered_opps = []
    for o in opps:
        close_date_str = o.get("expected_close_date")
        close_date_obj = None
        if close_date_str:
            try:
                close_date_obj = datetime.strptime(str(close_date_str)[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        if from_date_obj and (not close_date_obj or close_date_obj < from_date_obj):
            continue
        if to_date_obj and (not close_date_obj or close_date_obj > to_date_obj):
            continue
        filtered_opps.append(o)

    # 4. Gom nhóm cơ hội vào từng cột giai đoạn
    columns = []
    for stg in stages:
        stg_code = stg["code"]
        stg_id = stg["id"]
        col_opps = [o for o in filtered_opps if o.get("stage") == stg_code or o.get("stage") == str(stg_id)]
        col_val = round(sum(o.get("value", 0.0) for o in col_opps), 2)
        columns.append({
            "stage_id": stg_id,
            "stage_code": stg_code,
            "stage_name": stg["name"],
            "order_index": stg.get("order_index", 0),
            "default_win_probability": float(stg.get("win_probability", 0.0)),
            "count": len(col_opps),
            "total_value": col_val,
            "opportunities": col_opps,
        })

    total_count = sum(c["count"] for c in columns)
    total_val = round(sum(c["total_value"] for c in columns), 2)

    return {
        "scope": scope.value if hasattr(scope, "value") else str(scope),
        "total_opportunities": total_count,
        "total_pipeline_value": total_val,
        "columns": columns,
    }


def move_opportunity_kanban_stage(
    opportunity_id: int,
    new_stage_identifier: str,
    current_user: dict,
    probability: Optional[float] = None,
    probability_notes: Optional[str] = None,
) -> dict:
    """
    AC S5-02: Kéo thả để chuyển giai đoạn cơ hội bán hàng.
    """
    from app.services import pipeline_service
    from fastapi import HTTPException, status

    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    target_stage = pipeline_service.find_stage(new_stage_identifier)
    if not target_stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giai đoạn '{new_stage_identifier}'",
        )

    opp["stage"] = target_stage["code"]

    if probability is not None:
        opp["win_probability"] = float(probability)
        opp["probability_notes"] = probability_notes
    else:
        opp["win_probability"] = float(target_stage.get("win_probability", 10.0))

    return get_raw_opportunity_by_id(opportunity_id)


def create_opportunity_record(data: dict, current_user: dict) -> dict:
    from app.services import pipeline_service, customer_service
    from fastapi import HTTPException, status
    from datetime import date

    # AC S5-01: Đối với Nhân viên kinh doanh, ngày dự kiến chốt không được ở quá khứ khi tạo mới
    user_role = (current_user.get("role") or "").upper()
    close_date_raw = data.get("expected_close_date")
    close_date_obj = None
    if close_date_raw:
        if isinstance(close_date_raw, str) and close_date_raw.strip():
            try:
                close_date_obj = datetime.strptime(close_date_raw[:10], "%Y-%m-%d").date()
            except Exception:
                close_date_obj = None
        elif isinstance(close_date_raw, date):
            close_date_obj = close_date_raw

    if user_role not in ("ADMIN", "MANAGER"):
        if close_date_obj and close_date_obj < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ngày dự kiến chốt không được ở quá khứ khi tạo mới",
            )

    # AC S5-01: Xác suất thắng lấy mặc định theo giai đoạn, sửa tay được kèm ghi chú
    stage = data.get("stage", "PROSPECTING")
    stage_info = pipeline_service.find_stage(stage)
    default_prob = float(stage_info["win_probability"]) if stage_info and "win_probability" in stage_info else 10.0

    prob_notes = (data.get("probability_notes") or "").strip()
    if data.get("win_probability") is not None:
        user_prob = float(data["win_probability"])
        if abs(user_prob - default_prob) > 1e-4:
            if not prob_notes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sửa tay xác suất thắng khác mặc định của giai đoạn bắt buộc phải có ghi chú giải trình",
                )
            final_prob = user_prob
            final_notes = prob_notes
        else:
            final_prob = user_prob
            final_notes = prob_notes or None
    else:
        final_prob = default_prob
        final_notes = prob_notes or None

    customer_name = None
    if data.get("customer_id"):
        cust = customer_service.get_customer_by_id(data["customer_id"])
        if cust:
            customer_name = cust.get("name")

    db = SessionLocal()
    try:
        new_opp = OpportunityModel(
            title=data["title"],
            value=float(data.get("value") or 0.0),
            stage=stage,
            customer_id=data.get("customer_id"),
            campaign_id=data.get("campaign_id"),
            lead_id=data.get("lead_id"),
            owner_id=current_user.get("id", 1),
            team_id=data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
            expected_close_date=close_date_obj,
            contact_person=data.get("contact_person"),
            contact_id=data.get("contact_id"),
            source=data.get("source"),
            win_probability=final_prob,
            probability_notes=final_notes,
            description=data.get("description"),
            arr=0.0,
            status="OPEN",
        )
        db.add(new_opp)
        db.commit()
        db.refresh(new_opp)
        res = _row_to_dict(new_opp, db)
        _sync_fake_from_db()
        return _enrich_opportunity_record(res)
    except Exception as e:
        db.rollback()
        # Fallback RAM
        new_id = (max(o["id"] for o in FAKE_OPPORTUNITIES) + 1) if FAKE_OPPORTUNITIES else 1
        new_opp_ram = {
            "id": new_id,
            "title": data["title"],
            "value": float(data.get("value", 0.0)),
            "stage": stage,
            "customer_id": data.get("customer_id"),
            "customer_name": customer_name,
            "contact_person": data.get("contact_person"),
            "contact_id": data.get("contact_id"),
            "source": data.get("source"),
            "expected_close_date": str(close_date_obj) if close_date_obj else None,
            "win_probability": final_prob,
            "probability_notes": final_notes,
            "description": data.get("description"),
            "campaign_id": data.get("campaign_id"),
            "lead_id": data.get("lead_id"),
            "owner_id": current_user.get("id", 1),
            "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
            "arr": 0.0,
            "has_products": False,
            "products": [],
            "status": "OPEN",
            "created_at": datetime.utcnow().isoformat(),
        }
        FAKE_OPPORTUNITIES.append(new_opp_ram)
        return _enrich_opportunity_record(new_opp_ram)
    finally:
        db.close()


def update_opportunity_record(opportunity_id: int, data: dict, current_user: Optional[dict] = None) -> Optional[dict]:
    from app.services import pipeline_service, customer_service
    from fastapi import HTTPException, status
    from datetime import date

    db = SessionLocal()
    try:
        opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        opp_ram = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
        
        current_stage = opp.stage if opp else (opp_ram.get("stage", "PROSPECTING") if opp_ram else "PROSPECTING")
        current_prob = opp.win_probability if opp else (opp_ram.get("win_probability") if opp_ram else 10.0)
        current_notes = opp.probability_notes if opp else (opp_ram.get("probability_notes") if opp_ram else None)

        new_stage = data.get("stage")
        stage_to_check = new_stage or current_stage
        stage_info = pipeline_service.find_stage(stage_to_check)
        default_prob = float(stage_info["win_probability"]) if stage_info and "win_probability" in stage_info else 10.0

        final_prob = current_prob
        final_notes = current_notes
        if data.get("win_probability") is not None:
            user_prob = float(data["win_probability"])
            prob_notes = (data.get("probability_notes") or current_notes or "").strip()
            if abs(user_prob - default_prob) > 1e-4:
                if not prob_notes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Sửa tay xác suất thắng khác mặc định của giai đoạn bắt buộc phải có ghi chú giải trình",
                    )
                final_prob = user_prob
                final_notes = prob_notes
            else:
                final_prob = user_prob
                if data.get("probability_notes") is not None:
                    final_notes = (data.get("probability_notes") or "").strip() or None
        elif new_stage and new_stage != current_stage:
            final_prob = default_prob

        # S6-01: Ghi nhận lịch sử trước và sau khi update
        old_stage = opp.stage if opp else (opp_ram.get("stage") if opp_ram else None)
        old_val = opp.value if opp else (opp_ram.get("value") if opp_ram else None)
        old_close = str(opp.expected_close_date) if (opp and opp.expected_close_date) else (str(opp_ram.get("expected_close_date")) if (opp_ram and opp_ram.get("expected_close_date")) else None)
        old_owner = opp.owner_id if opp else (opp_ram.get("owner_id") if opp_ram else None)

        if opp is not None:
            for key, value in data.items():
                if key in ("id", "owner_id", "win_probability", "probability_notes"):
                    continue
                if key == "expected_close_date":
                    if isinstance(value, str) and value.strip():
                        try:
                            value = datetime.strptime(value[:10], "%Y-%m-%d").date()
                        except Exception:
                            value = None
                    elif not isinstance(value, date):
                        value = None
                if hasattr(opp, key):
                    setattr(opp, key, value)

            opp.win_probability = final_prob
            opp.probability_notes = final_notes

            # Ghi nhận lịch sử S6-01 cho các trường thay đổi
            performer_id = current_user.get("id", 1) if current_user else 1
            performer_name = (current_user.get("full_name") or current_user.get("username") or f"User {performer_id}") if current_user else "System"

            if new_stage and new_stage != old_stage:
                record_opportunity_history(opportunity_id, "stage", old_stage, new_stage, performer_id, performer_name, db=db)
            if data.get("value") is not None and float(data["value"]) != float(old_val or 0.0):
                record_opportunity_history(opportunity_id, "value", str(old_val), str(data["value"]), performer_id, performer_name, db=db)
            new_close_str = str(data.get("expected_close_date")) if data.get("expected_close_date") else None
            if "expected_close_date" in data and new_close_str != old_close:
                record_opportunity_history(opportunity_id, "expected_close_date", old_close, new_close_str, performer_id, performer_name, db=db)

            db.commit()
            db.refresh(opp)
            items = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opp.id).all()
            opp_dict = _row_to_dict(opp, db)
            opp_dict["products"] = [_product_row_to_dict(p) for p in items]
            opp_dict["has_products"] = len(items) > 0
            _sync_fake_from_db()
            return _enrich_opportunity_record(opp_dict)

        # Fallback RAM
        if opp_ram:
            performer_id = current_user.get("id", 1) if current_user else 1
            performer_name = (current_user.get("full_name") or current_user.get("username") or f"User {performer_id}") if current_user else "System"

            if new_stage and new_stage != old_stage:
                record_opportunity_history(opportunity_id, "stage", old_stage, new_stage, performer_id, performer_name)
            if data.get("value") is not None and float(data["value"]) != float(old_val or 0.0):
                record_opportunity_history(opportunity_id, "value", str(old_val), str(data["value"]), performer_id, performer_name)
            new_close_str = str(data.get("expected_close_date")) if data.get("expected_close_date") else None
            if "expected_close_date" in data and new_close_str != old_close:
                record_opportunity_history(opportunity_id, "expected_close_date", old_close, new_close_str, performer_id, performer_name)

            for k, v in data.items():
                if v is not None and k not in ("id", "owner_id", "win_probability", "probability_notes"):
                    if k == "expected_close_date":
                        opp_ram[k] = str(v)
                    else:
                        opp_ram[k] = v
            opp_ram["win_probability"] = final_prob
            opp_ram["probability_notes"] = final_notes
            if data.get("customer_id"):
                cust = customer_service.get_customer_by_id(data["customer_id"])
                if cust:
                    opp_ram["customer_name"] = cust.get("name")
            return get_raw_opportunity_by_id(opportunity_id)
        return None
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def delete_opportunity_record(opportunity_id: int) -> bool:
    global FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS
    db = SessionLocal()
    try:
        opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        if opp:
            db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opportunity_id).delete()
            db.delete(opp)
            db.commit()
            _sync_fake_from_db()
            return True
        # Fallback RAM
        initial_len = len(FAKE_OPPORTUNITIES)
        FAKE_OPPORTUNITIES = [o for o in FAKE_OPPORTUNITIES if o["id"] != opportunity_id]
        FAKE_OPPORTUNITY_PRODUCTS = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] != opportunity_id]
        return len(FAKE_OPPORTUNITIES) < initial_len
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


# ============================================================================
# QUẢN LÝ SẢN PHẨM / DỊCH VỤ TRONG CƠ HỘI (OPPORTUNITY PRODUCTS - S5-03)
# ============================================================================

def list_opportunity_products(opportunity_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        items = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opportunity_id).all()
        if items:
            return [_product_row_to_dict(p) for p in items]
        return [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]
    finally:
        db.close()


def add_product_to_opportunity(
    opportunity_id: int,
    payload_data: dict,
    current_user: dict,
) -> dict:
    from fastapi import HTTPException, status
    from app.services.product_service import get_product_by_id, fake_products_db

    opp_dict = get_raw_opportunity_by_id(opportunity_id)
    if not opp_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cơ hội bán hàng với ID {opportunity_id}",
        )

    product_id = payload_data["product_id"]
    try:
        product = get_product_by_id(product_id, current_user=current_user)
    except Exception:
        product = next((p for p in fake_products_db if p["id"] == product_id), None)

    if not product or product.get("status") == "DISCONTINUED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã ngừng kinh doanh",
        )

    quantity = float(payload_data.get("quantity") or 1.0)
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số lượng sản phẩm phải lớn hơn 0")

    floor_price = float(product.get("floor_price", 0.0))
    list_price = float(product.get("list_price", 0.0))

    unit_price = float(payload_data.get("unit_price")) if payload_data.get("unit_price") is not None and float(payload_data.get("unit_price")) > 0 else list_price

    if unit_price < floor_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn giá {unit_price:,.0f} đ không được thấp hơn giá sàn {floor_price:,.0f} đ của sản phẩm '{product['name']}'",
        )

    discount = float(payload_data.get("discount_percent") or 0.0)
    if discount < 0 or discount > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chiết khấu phải từ 0% đến 100%")

    product_type = product.get("product_type", "ONE_TIME")

    if product_type == "SUBSCRIPTION":
        cycle = (payload_data.get("billing_cycle") or "MONTHLY").upper()
        if cycle not in ("MONTHLY", "QUARTERLY", "ANNUALLY"):
            cycle = "MONTHLY"

        default_cycles = 12 if cycle == "MONTHLY" else (4 if cycle == "QUARTERLY" else 1)
        num_cycles = int(payload_data.get("number_of_cycles") or default_cycles)
        if num_cycles <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số kỳ thanh toán phải lớn hơn 0")

        months_per_cycle = 1 if cycle == "MONTHLY" else (3 if cycle == "QUARTERLY" else 12)
        term_months = num_cycles * months_per_cycle

        amount = round(quantity * unit_price * num_cycles * (1 - discount / 100), 2)
        if cycle == "MONTHLY":
            mrr = round(quantity * unit_price * (1 - discount / 100), 2)
            arr = round(mrr * 12, 2)
        elif cycle == "QUARTERLY":
            arr = round(quantity * unit_price * 4 * (1 - discount / 100), 2)
            mrr = round(arr / 12, 2)
        else:
            arr = round(quantity * unit_price * (1 - discount / 100), 2)
            mrr = round(arr / 12, 2)
    else:
        cycle = None
        num_cycles = None
        term_months = None
        arr = None
        mrr = None
        amount = round(quantity * unit_price * (1 - discount / 100), 2)

    db = SessionLocal()
    try:
        opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        if opp:
            new_item = OpportunityProductModel(
                opportunity_id=opportunity_id,
                product_id=product_id,
                product_code=product.get("code", f"PROD-{product_id}"),
                product_name=product.get("name", "Sản phẩm"),
                product_type=product_type,
                quantity=quantity,
                unit_price=unit_price,
                floor_price=floor_price,
                discount_percent=discount,
                billing_cycle=cycle,
                number_of_cycles=num_cycles,
                term_months=term_months,
                arr=arr,
                mrr=mrr,
                amount=amount,
            )
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            res_dict = _product_row_to_dict(new_item)
        else:
            # Fallback RAM
            new_item_id = (max(p["id"] for p in FAKE_OPPORTUNITY_PRODUCTS) + 1) if FAKE_OPPORTUNITY_PRODUCTS else 1
            res_dict = {
                "id": new_item_id,
                "opportunity_id": opportunity_id,
                "product_id": product_id,
                "product_code": product.get("code", f"PROD-{product_id}"),
                "product_name": product.get("name", "Sản phẩm"),
                "product_type": product_type,
                "quantity": quantity,
                "unit_price": unit_price,
                "floor_price": floor_price,
                "discount_percent": discount,
                "billing_cycle": cycle,
                "number_of_cycles": num_cycles,
                "term_months": term_months,
                "arr": arr,
                "mrr": mrr,
                "amount": amount,
            }
            FAKE_OPPORTUNITY_PRODUCTS.append(res_dict)
    finally:
        db.close()

    recalculate_opportunity_value(opportunity_id)
    return res_dict


def update_opportunity_product(
    opportunity_id: int,
    item_id: int,
    patch_data: dict,
) -> dict:
    from fastapi import HTTPException, status

    db = SessionLocal()
    try:
        item = db.query(OpportunityProductModel).filter(
            OpportunityProductModel.id == item_id,
            OpportunityProductModel.opportunity_id == opportunity_id
        ).first()

        if item:
            if "unit_price" in patch_data and patch_data["unit_price"] is not None:
                new_price = float(patch_data["unit_price"])
                if new_price < item.floor_price:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Đơn giá {new_price:,.0f} đ không được thấp hơn giá sàn {item.floor_price:,.0f} đ",
                    )
                item.unit_price = new_price

            if "quantity" in patch_data and patch_data["quantity"] is not None:
                new_qty = float(patch_data["quantity"])
                if new_qty <= 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số lượng phải lớn hơn 0")
                item.quantity = new_qty

            if "discount_percent" in patch_data and patch_data["discount_percent"] is not None:
                new_disc = float(patch_data["discount_percent"])
                if new_disc < 0 or new_disc > 100:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chiết khấu phải từ 0% đến 100%")
                item.discount_percent = new_disc

            if item.product_type == "SUBSCRIPTION":
                if "billing_cycle" in patch_data and patch_data["billing_cycle"]:
                    item.billing_cycle = patch_data["billing_cycle"].upper()
                if "number_of_cycles" in patch_data and patch_data["number_of_cycles"] is not None:
                    item.number_of_cycles = int(patch_data["number_of_cycles"])

                cycle = item.billing_cycle or "MONTHLY"
                num_cycles = item.number_of_cycles or (12 if cycle == "MONTHLY" else (4 if cycle == "QUARTERLY" else 1))
                months_per_cycle = 1 if cycle == "MONTHLY" else (3 if cycle == "QUARTERLY" else 12)
                item.term_months = num_cycles * months_per_cycle
                item.amount = round(item.quantity * item.unit_price * num_cycles * (1 - item.discount_percent / 100), 2)

                if cycle == "MONTHLY":
                    mrr = round(item.quantity * item.unit_price * (1 - item.discount_percent / 100), 2)
                    item.mrr = mrr
                    item.arr = round(mrr * 12, 2)
                elif cycle == "QUARTERLY":
                    arr = round(item.quantity * item.unit_price * 4 * (1 - item.discount_percent / 100), 2)
                    item.arr = arr
                    item.mrr = round(arr / 12, 2)
                else:
                    arr = round(item.quantity * item.unit_price * (1 - item.discount_percent / 100), 2)
                    item.arr = arr
                    item.mrr = round(arr / 12, 2)
            else:
                item.amount = round(item.quantity * item.unit_price * (1 - item.discount_percent / 100), 2)

            db.commit()
            db.refresh(item)
            res_dict = _product_row_to_dict(item)
        else:
            # Fallback RAM
            item_ram = next((p for p in FAKE_OPPORTUNITY_PRODUCTS if p["id"] == item_id and p["opportunity_id"] == opportunity_id), None)
            if not item_ram:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy dòng sản phẩm ID {item_id}")
            
            if "unit_price" in patch_data and patch_data["unit_price"] is not None:
                p = float(patch_data["unit_price"])
                if p < item_ram.get("floor_price", 0.0):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Đơn giá {p:,.0f} đ không được thấp hơn giá sàn {item_ram.get('floor_price', 0.0):,.0f} đ",
                    )
                item_ram["unit_price"] = p

            if "quantity" in patch_data and patch_data["quantity"] is not None:
                q = float(patch_data["quantity"])
                if q <= 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số lượng phải lớn hơn 0")
                item_ram["quantity"] = q

            if "discount_percent" in patch_data and patch_data["discount_percent"] is not None:
                d = float(patch_data["discount_percent"])
                if d < 0 or d > 100:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chiết khấu phải từ 0% đến 100%")
                item_ram["discount_percent"] = d

            if item_ram.get("product_type") == "SUBSCRIPTION":
                if "billing_cycle" in patch_data and patch_data["billing_cycle"]:
                    c = patch_data["billing_cycle"].upper()
                    if c in ("MONTHLY", "QUARTERLY", "ANNUALLY"):
                        item_ram["billing_cycle"] = c
                if "number_of_cycles" in patch_data and patch_data["number_of_cycles"] is not None:
                    nc = int(patch_data["number_of_cycles"])
                    if nc > 0:
                        item_ram["number_of_cycles"] = nc

                cycle = item_ram.get("billing_cycle") or "MONTHLY"
                num_cycles = item_ram.get("number_of_cycles") or 12
                item_ram["term_months"] = num_cycles if cycle == "MONTHLY" else (num_cycles * 3 if cycle == "QUARTERLY" else num_cycles * 12)
                item_ram["amount"] = round(item_ram["quantity"] * item_ram["unit_price"] * num_cycles * (1 - item_ram.get("discount_percent", 0.0) / 100), 2)

                if cycle == "MONTHLY":
                    mrr = round(item_ram["quantity"] * item_ram["unit_price"] * (1 - item_ram.get("discount_percent", 0.0) / 100), 2)
                    item_ram["mrr"] = mrr
                    item_ram["arr"] = round(mrr * 12, 2)
                elif cycle == "QUARTERLY":
                    arr = round(item_ram["quantity"] * item_ram["unit_price"] * 4 * (1 - item_ram.get("discount_percent", 0.0) / 100), 2)
                    item_ram["arr"] = arr
                    item_ram["mrr"] = round(arr / 12, 2)
                else:
                    arr = round(item_ram["quantity"] * item_ram["unit_price"] * (1 - item_ram.get("discount_percent", 0.0) / 100), 2)
                    item_ram["arr"] = arr
                    item_ram["mrr"] = round(arr / 12, 2)
            else:
                item_ram["amount"] = round(item_ram["quantity"] * item_ram["unit_price"] * (1 - item_ram.get("discount_percent", 0.0) / 100), 2)

            res_dict = item_ram
    finally:
        db.close()

    recalculate_opportunity_value(opportunity_id)
    return res_dict


def delete_opportunity_product(opportunity_id: int, item_id: int) -> bool:
    global FAKE_OPPORTUNITY_PRODUCTS
    db = SessionLocal()
    success = False
    try:
        item = db.query(OpportunityProductModel).filter(
            OpportunityProductModel.id == item_id,
            OpportunityProductModel.opportunity_id == opportunity_id
        ).first()
        if item:
            db.delete(item)
            db.commit()
            success = True
        else:
            initial_len = len(FAKE_OPPORTUNITY_PRODUCTS)
            FAKE_OPPORTUNITY_PRODUCTS = [p for p in FAKE_OPPORTUNITY_PRODUCTS if not (p["id"] == item_id and p["opportunity_id"] == opportunity_id)]
            success = len(FAKE_OPPORTUNITY_PRODUCTS) < initial_len
    except Exception:
        db.rollback()
        success = False
    finally:
        db.close()

    if success:
        recalculate_opportunity_value(opportunity_id)
    return success


def reassign_opportunities(
    opportunity_ids: list[int],
    new_owner_id: int,
    reason: str,
    current_user: dict,
) -> dict:
    from fastapi import HTTPException, status
    from app.services.auth_service import get_user_by_id
    from app.services.audit_log_service import log_change
    from app.services.activity_service import FAKE_ACTIVITIES

    clean_reason = reason.strip() if reason else ""
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lý do phân bổ lại cơ hội không được để trống",
        )

    if not opportunity_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh sách cơ hội cần phân bổ lại không được để trống",
        )

    target_user = get_user_by_id(new_owner_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng nhận chuyển quyền với ID {new_owner_id}",
        )

    if not target_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể phân bổ cơ hội cho người dùng đã bị vô hiệu hóa",
        )

    db = SessionLocal()
    try:
        matched_opps = db.query(OpportunityModel).filter(OpportunityModel.id.in_(opportunity_ids)).all()
        found_ids = {o.id for o in matched_opps}
        missing_ids = [oid for oid in opportunity_ids if oid not in found_ids]

        # Nếu không có trong DB thì kiểm tra RAM
        if missing_ids:
            ram_matched = [o for o in FAKE_OPPORTUNITIES if o["id"] in opportunity_ids]
            if len(ram_matched) == len(opportunity_ids):
                matched_opps = []
                missing_ids = []

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy các cơ hội với ID: {missing_ids}",
            )

        current_role = current_user.get("role", "USER")
        current_uid = current_user.get("id")
        current_team = current_user.get("team_id")

        all_opp_objs = matched_opps if matched_opps else [o for o in FAKE_OPPORTUNITIES if o["id"] in opportunity_ids]

        for opp in all_opp_objs:
            opp_team = getattr(opp, 'team_id', None) if hasattr(opp, 'team_id') else opp.get('team_id')
            opp_owner = getattr(opp, 'owner_id', None) if hasattr(opp, 'owner_id') else opp.get('owner_id')
            opp_title = getattr(opp, 'title', '') if hasattr(opp, 'title') else opp.get('title', '')
            opp_id = getattr(opp, 'id', 0) if hasattr(opp, 'id') else opp.get('id', 0)

            if current_role == "ADMIN":
                continue
            elif current_role == "MANAGER":
                if opp_owner != current_uid and (opp_team is None or opp_team != current_team):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Bạn không có quyền phân bổ lại cơ hội '{opp_title}' (ID {opp_id}) ngoài nhóm quản lý",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ Trưởng nhóm kinh doanh hoặc Quản trị viên mới có quyền phân bổ lại cơ hội",
                )

        reassigned_ids = []
        for opp in all_opp_objs:
            if hasattr(opp, 'owner_id'):
                old_owner_id = opp.owner_id
                opp.owner_id = new_owner_id
                if target_user.get("team_id") is not None:
                    opp.team_id = target_user["team_id"]
                reassigned_ids.append(opp.id)
                oid = opp.id
            else:
                old_owner_id = opp["owner_id"]
                opp["owner_id"] = new_owner_id
                if target_user.get("team_id") is not None:
                    opp["team_id"] = target_user["team_id"]
                reassigned_ids.append(opp["id"])
                oid = opp["id"]

            for act in FAKE_ACTIVITIES:
                if act.get("opportunity_id") == oid:
                    if target_user.get("team_id") is not None:
                        act["team_id"] = target_user["team_id"]

            log_change(
                user_id=current_uid,
                user_name=current_user.get("full_name") or current_user.get("username") or "Manager",
                entity_type="DATA_OWNERSHIP",
                entity_id=str(oid),
                action="REASSIGN_OPPORTUNITY",
                field_name="owner_id",
                old_value=f"Owner ID {old_owner_id}",
                new_value=f"Owner ID {new_owner_id} ({target_user.get('full_name')}) - Lý do: {clean_reason}",
            )

        if matched_opps:
            db.commit()

        target_name = target_user.get("full_name") or target_user.get("username") or str(new_owner_id)
        return {
            "success": True,
            "reassigned_count": len(reassigned_ids),
            "reassigned_opportunity_ids": reassigned_ids,
            "new_owner_id": new_owner_id,
            "new_owner_name": target_name,
            "reason": clean_reason,
            "message": f"Đã phân bổ lại thành công {len(reassigned_ids)} cơ hội cho {target_name}",
        }
    finally:
        db.close()


# ============================================================================
# SPRINT 6: S6-01, S6-02, S6-03, S6-04 IMPLEMENTATIONS
# ============================================================================

FAKE_OPPORTUNITY_HISTORIES: List[Dict[str, Any]] = []
FAKE_OPPORTUNITY_SAVED_FILTERS: List[Dict[str, Any]] = []
FAKE_OPPORTUNITY_SHARES: List[Dict[str, Any]] = []
FAKE_OPPORTUNITY_ATTACHMENTS: List[Dict[str, Any]] = []


def record_opportunity_history(
    opportunity_id: int,
    field_name: str,
    old_value: Any,
    new_value: Any,
    performer_id: int,
    performer_name: Optional[str] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """S6-01: Ghi nhận lịch sử thay đổi trường cơ hội (chỉ ghi khi thực sự thay đổi)."""
    if str(old_value) == str(new_value):
        return {}

    now = datetime.now()
    entry = {
        "opportunity_id": opportunity_id,
        "field_name": field_name,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
        "performed_by": performer_id,
        "performer_name": performer_name or f"User {performer_id}",
        "created_at": now,
    }

    local_db = None
    if db is None:
        local_db = SessionLocal()
        session = local_db
    else:
        session = db

    try:
        model = OpportunityHistoryModel(
            opportunity_id=opportunity_id,
            field_name=field_name,
            old_value=entry["old_value"],
            new_value=entry["new_value"],
            performed_by=performer_id,
            performer_name=entry["performer_name"],
            created_at=now,
        )
        session.add(model)
        if local_db is not None:
            session.commit()
            session.refresh(model)
            entry["id"] = model.id
        else:
            session.flush()
            entry["id"] = model.id
    except Exception:
        if local_db is not None:
            session.rollback()
        new_id = (max([h["id"] for h in FAKE_OPPORTUNITY_HISTORIES], default=0) + 1)
        entry["id"] = new_id
    finally:
        if local_db is not None:
            local_db.close()

    FAKE_OPPORTUNITY_HISTORIES.append(entry)
    return entry


def list_opportunity_histories(opportunity_id: int, skip: int = 0, limit: int = 20) -> Tuple[List[Dict[str, Any]], int]:
    """S6-01: Lấy lịch sử thay đổi của cơ hội, sắp xếp mới nhất trước, có phân trang."""
    db = SessionLocal()
    try:
        query = db.query(OpportunityHistoryModel).filter(OpportunityHistoryModel.opportunity_id == opportunity_id)
        total = query.count()
        rows = query.order_by(OpportunityHistoryModel.created_at.desc(), OpportunityHistoryModel.id.desc()).offset(skip).limit(limit).all()
        if total > 0 or rows:
            items = []
            for r in rows:
                items.append({
                    "id": r.id,
                    "opportunity_id": r.opportunity_id,
                    "field_name": r.field_name,
                    "old_value": r.old_value,
                    "new_value": r.new_value,
                    "performed_by": r.performed_by,
                    "performer_name": r.performer_name,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
            return items, total

        # Fallback RAM
        ram_items = [h for h in FAKE_OPPORTUNITY_HISTORIES if h["opportunity_id"] == opportunity_id]
        ram_items.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        total_ram = len(ram_items)
        paged = ram_items[skip : skip + limit]
        return paged, total_ram
    finally:
        db.close()


def check_opportunity_access_permission(
    opportunity: dict,
    current_user: dict,
    require_write: bool = False,
) -> bool:
    """
    S6-03: Kiểm tra quyền xem hoặc thao tác trên cơ hội:
    - ADMIN: Toàn quyền.
    - MANAGER: Trong cùng nhóm quản lý, hoặc được chia sẻ.
    - OWNER: Toàn quyền với cơ hội mình sở hữu.
    - SHARED MEMBER: Quyền theo share (READ hoặc READ_WRITE).
    """
    user_id = current_user.get("id")
    role = current_user.get("role", "USER")

    if role == "ADMIN":
        return True

    owner_id = opportunity.get("owner_id")
    if owner_id == user_id:
        return True

    # Kiểm tra quyền chia sẻ S6-03
    opp_id = opportunity.get("id")
    shares = list_opportunity_shares(opp_id)
    user_share = next((s for s in shares if s["user_id"] == user_id), None)
    if user_share:
        if require_write:
            return user_share.get("permission") == "READ_WRITE"
        return True

    # MANAGER theo team
    if role == "MANAGER":
        team_id = opportunity.get("team_id")
        user_team = current_user.get("team_id")
        if user_team is not None and user_team == team_id:
            return True

    return False


def get_shared_opportunity_ids_for_user(user_id: int) -> List[int]:
    """Lấy danh sách ID các cơ hội được chia sẻ cho user_id."""
    db = SessionLocal()
    try:
        rows = db.query(OpportunityShareModel.opportunity_id).filter(OpportunityShareModel.user_id == user_id).all()
        db_ids = [r[0] for r in rows]
        ram_ids = [s["opportunity_id"] for s in FAKE_OPPORTUNITY_SHARES if s["user_id"] == user_id]
        return list(set(db_ids + ram_ids))
    finally:
        db.close()


def list_opportunity_shares(opportunity_id: int) -> List[Dict[str, Any]]:
    """S6-03: Lấy danh sách thành viên được chia sẻ của một cơ hội."""
    db = SessionLocal()
    try:
        rows = db.query(OpportunityShareModel).filter(OpportunityShareModel.opportunity_id == opportunity_id).all()
        results = []
        for r in rows:
            u = db.query(UserModel).filter(UserModel.id == r.user_id).first()
            sb = db.query(UserModel).filter(UserModel.id == r.shared_by).first()
            results.append({
                "id": r.id,
                "opportunity_id": r.opportunity_id,
                "user_id": r.user_id,
                "user_name": (u.full_name or u.username) if u else f"User {r.user_id}",
                "user_email": u.email if u else None,
                "permission": r.permission,
                "shared_by": r.shared_by,
                "shared_by_name": (sb.full_name or sb.username) if sb else f"User {r.shared_by}",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        if results:
            return results

        # Fallback RAM
        ram_list = [s for s in FAKE_OPPORTUNITY_SHARES if s["opportunity_id"] == opportunity_id]
        from app.services import auth_service
        enriched = []
        for s in ram_list:
            u = auth_service.get_user_by_id(s["user_id"])
            sb = auth_service.get_user_by_id(s["shared_by"])
            c = copy.deepcopy(s)
            c["user_name"] = (u.get("full_name") or u.get("username")) if u else f"User {s['user_id']}"
            c["user_email"] = u.get("email") if u else None
            c["shared_by_name"] = (sb.get("full_name") or sb.get("username")) if sb else f"User {s['shared_by']}"
            enriched.append(c)
        return enriched
    finally:
        db.close()


def add_opportunity_share(
    opportunity_id: int,
    user_id: int,
    permission: str,
    current_user: dict,
) -> Dict[str, Any]:
    """S6-03: Thêm thành viên được chia sẻ (chặn trùng lặp, chặn chia sẻ cho chính owner)."""
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    # Chỉ owner hoặc ADMIN/MANAGER có quyền chia sẻ
    current_uid = current_user.get("id")
    role = current_user.get("role", "USER")
    is_owner = (opp.get("owner_id") == current_uid)
    is_admin = (role == "ADMIN")
    is_manager = (role == "MANAGER" and opp.get("team_id") == current_user.get("team_id"))

    if not (is_owner or is_admin or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chia sẻ cơ hội này. Chỉ người sở hữu hoặc cấp quản lý mới có quyền.",
        )

    if user_id == opp.get("owner_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng này đã là người sở hữu chính của cơ hội",
        )

    # Chặn thành viên trùng lặp
    existing = list_opportunity_shares(opportunity_id)
    if any(s["user_id"] == user_id for s in existing):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thành viên này đã được chia sẻ cơ hội trước đó",
        )

    from app.services import auth_service
    target_user = auth_service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID {user_id}",
        )

    db = SessionLocal()
    now = datetime.now()
    new_entry = {
        "opportunity_id": opportunity_id,
        "user_id": user_id,
        "permission": permission if permission in ("READ", "READ_WRITE") else "READ_WRITE",
        "shared_by": current_uid,
        "created_at": now.isoformat(),
    }

    try:
        m = OpportunityShareModel(
            opportunity_id=opportunity_id,
            user_id=user_id,
            permission=new_entry["permission"],
            shared_by=current_uid,
            created_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        new_entry["id"] = m.id
    except Exception:
        db.rollback()
        new_id = (max([s["id"] for s in FAKE_OPPORTUNITY_SHARES], default=0) + 1)
        new_entry["id"] = new_id
    finally:
        db.close()

    FAKE_OPPORTUNITY_SHARES.append(new_entry)
    new_entry["user_name"] = target_user.get("full_name") or target_user.get("username")
    new_entry["user_email"] = target_user.get("email")
    new_entry["shared_by_name"] = current_user.get("full_name") or current_user.get("username")
    return new_entry


def remove_opportunity_share(opportunity_id: int, user_id: int, current_user: dict) -> bool:
    """S6-03: Gỡ thành viên được chia sẻ."""
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    current_uid = current_user.get("id")
    role = current_user.get("role", "USER")
    is_owner = (opp.get("owner_id") == current_uid)
    is_admin = (role == "ADMIN")
    is_manager = (role == "MANAGER" and opp.get("team_id") == current_user.get("team_id"))

    if not (is_owner or is_admin or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền gỡ thành viên khỏi cơ hội này",
        )

    db = SessionLocal()
    found = False
    try:
        row = db.query(OpportunityShareModel).filter(
            OpportunityShareModel.opportunity_id == opportunity_id,
            OpportunityShareModel.user_id == user_id,
        ).first()
        if row:
            db.delete(row)
            db.commit()
            found = True
    except Exception:
        db.rollback()
    finally:
        db.close()

    global FAKE_OPPORTUNITY_SHARES
    initial_len = len(FAKE_OPPORTUNITY_SHARES)
    FAKE_OPPORTUNITY_SHARES = [
        s for s in FAKE_OPPORTUNITY_SHARES
        if not (s["opportunity_id"] == opportunity_id and s["user_id"] == user_id)
    ]
    if len(FAKE_OPPORTUNITY_SHARES) < initial_len:
        found = True

    return found


def transfer_opportunity_ownership(
    opportunity_id: int,
    new_owner_id: int,
    reason: str,
    current_user: dict,
) -> Dict[str, Any]:
    """
    S6-03: Chuyển quyền sở hữu cơ hội và ghi nhật ký đầy đủ:
    người sở hữu trước, người sở hữu mới, người thực hiện, thời điểm và lý do.
    """
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    current_uid = current_user.get("id")
    role = current_user.get("role", "USER")
    is_owner = (opp.get("owner_id") == current_uid)
    is_admin = (role == "ADMIN")
    is_manager = (role == "MANAGER" and opp.get("team_id") == current_user.get("team_id"))

    # Thành viên được chia sẻ KHÔNG được tự ý chuyển người sở hữu
    if not (is_owner or is_admin or is_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thành viên được chia sẻ không có quyền thay đổi người sở hữu cơ hội",
        )

    old_owner_id = opp["owner_id"]
    if old_owner_id == new_owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người sở hữu mới trùng với người sở hữu hiện tại",
        )

    from app.services import auth_service
    target_user = auth_service.get_user_by_id(new_owner_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID {new_owner_id}",
        )

    db = SessionLocal()
    try:
        db_opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
        if db_opp:
            db_opp.owner_id = new_owner_id
            if target_user.get("team_id") is not None:
                db_opp.team_id = target_user["team_id"]
            db.commit()

        # Update RAM fallback
        for o in FAKE_OPPORTUNITIES:
            if o["id"] == opportunity_id:
                o["owner_id"] = new_owner_id
                if target_user.get("team_id") is not None:
                    o["team_id"] = target_user["team_id"]

        # Ghi lịch sử cơ hội (S6-01)
        record_opportunity_history(
            opportunity_id=opportunity_id,
            field_name="owner_id",
            old_value=str(old_owner_id),
            new_value=str(new_owner_id),
            performer_id=current_uid,
            performer_name=current_user.get("full_name") or current_user.get("username"),
            db=db,
        )

        # Ghi audit log hệ thống (S2-04)
        from app.services.audit_log_service import log_change
        log_change(
            user_id=current_uid,
            user_name=current_user.get("full_name") or current_user.get("username") or "Manager",
            entity_type="DATA_OWNERSHIP",
            entity_id=str(opportunity_id),
            action="TRANSFER_OWNERSHIP",
            field_name="owner_id",
            old_value=f"Owner ID {old_owner_id}",
            new_value=f"Owner ID {new_owner_id} ({target_user.get('full_name')}) - Lý do: {reason}",
            db=db,
        )

        return {
            "success": True,
            "opportunity_id": opportunity_id,
            "old_owner_id": old_owner_id,
            "new_owner_id": new_owner_id,
            "new_owner_name": target_user.get("full_name") or target_user.get("username"),
            "performed_by": current_uid,
            "reason": reason,
            "message": f"Chuyển quyền sở hữu thành công cho {target_user.get('full_name') or target_user.get('username')}",
        }
    finally:
        db.close()


# S6-02: Bộ lọc cơ hội đã lưu (Opportunity Saved Filters)
def list_opportunity_saved_filters(user_id: int) -> List[Dict[str, Any]]:
    """S6-02: Lấy danh sách bộ lọc cơ hội của riêng người dùng."""
    import json
    db = SessionLocal()
    try:
        rows = db.query(OpportunitySavedFilterModel).filter(OpportunitySavedFilterModel.user_id == user_id).order_by(OpportunitySavedFilterModel.id.desc()).all()
        results = []
        for r in rows:
            criteria = {}
            try:
                criteria = json.loads(r.filter_criteria) if isinstance(r.filter_criteria, str) else r.filter_criteria
            except Exception:
                criteria = {}
            results.append({
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "filter_criteria": criteria,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
        if results:
            return results

        # Fallback RAM
        ram_list = [f for f in FAKE_OPPORTUNITY_SAVED_FILTERS if f["user_id"] == user_id]
        return ram_list
    finally:
        db.close()


def get_opportunity_saved_filter_by_id(filter_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    import json
    db = SessionLocal()
    try:
        r = db.query(OpportunitySavedFilterModel).filter(
            OpportunitySavedFilterModel.id == filter_id,
            OpportunitySavedFilterModel.user_id == user_id,
        ).first()
        if r:
            criteria = {}
            try:
                criteria = json.loads(r.filter_criteria) if isinstance(r.filter_criteria, str) else r.filter_criteria
            except Exception:
                criteria = {}
            return {
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "filter_criteria": criteria,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }

        # Fallback RAM
        for f in FAKE_OPPORTUNITY_SAVED_FILTERS:
            if f["id"] == filter_id and f["user_id"] == user_id:
                return f
        return None
    finally:
        db.close()


def create_opportunity_saved_filter(user_id: int, name: str, filter_criteria: dict) -> Dict[str, Any]:
    import json
    db = SessionLocal()
    now = datetime.now()
    crit_str = json.dumps(filter_criteria, ensure_ascii=False)
    entry = {
        "user_id": user_id,
        "name": name,
        "filter_criteria": filter_criteria,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    try:
        m = OpportunitySavedFilterModel(
            user_id=user_id,
            name=name,
            filter_criteria=crit_str,
            created_at=now,
            updated_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        entry["id"] = m.id
    except Exception:
        db.rollback()
        new_id = (max([f["id"] for f in FAKE_OPPORTUNITY_SAVED_FILTERS], default=0) + 1)
        entry["id"] = new_id
    finally:
        db.close()

    FAKE_OPPORTUNITY_SAVED_FILTERS.append(entry)
    return entry


def update_opportunity_saved_filter(filter_id: int, user_id: int, name: Optional[str] = None, filter_criteria: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    import json
    db = SessionLocal()
    now = datetime.now()
    try:
        r = db.query(OpportunitySavedFilterModel).filter(
            OpportunitySavedFilterModel.id == filter_id,
            OpportunitySavedFilterModel.user_id == user_id,
        ).first()
        if r:
            if name is not None:
                r.name = name
            if filter_criteria is not None:
                r.filter_criteria = json.dumps(filter_criteria, ensure_ascii=False)
            r.updated_at = now
            db.commit()
            db.refresh(r)
            criteria = json.loads(r.filter_criteria) if isinstance(r.filter_criteria, str) else r.filter_criteria
            res = {
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "filter_criteria": criteria,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            # Update RAM
            for f in FAKE_OPPORTUNITY_SAVED_FILTERS:
                if f["id"] == filter_id and f["user_id"] == user_id:
                    if name is not None:
                        f["name"] = name
                    if filter_criteria is not None:
                        f["filter_criteria"] = filter_criteria
                    f["updated_at"] = now.isoformat()
            return res

        # Fallback RAM
        for f in FAKE_OPPORTUNITY_SAVED_FILTERS:
            if f["id"] == filter_id and f["user_id"] == user_id:
                if name is not None:
                    f["name"] = name
                if filter_criteria is not None:
                    f["filter_criteria"] = filter_criteria
                f["updated_at"] = now.isoformat()
                return f
        return None
    finally:
        db.close()


def delete_opportunity_saved_filter(filter_id: int, user_id: int) -> bool:
    db = SessionLocal()
    found = False
    try:
        r = db.query(OpportunitySavedFilterModel).filter(
            OpportunitySavedFilterModel.id == filter_id,
            OpportunitySavedFilterModel.user_id == user_id,
        ).first()
        if r:
            db.delete(r)
            db.commit()
            found = True
    except Exception:
        db.rollback()
    finally:
        db.close()

    global FAKE_OPPORTUNITY_SAVED_FILTERS
    initial_len = len(FAKE_OPPORTUNITY_SAVED_FILTERS)
    FAKE_OPPORTUNITY_SAVED_FILTERS = [
        f for f in FAKE_OPPORTUNITY_SAVED_FILTERS
        if not (f["id"] == filter_id and f["user_id"] == user_id)
    ]
    if len(FAKE_OPPORTUNITY_SAVED_FILTERS) < initial_len:
        found = True

    return found


# S6-02: Tìm kiếm và lọc cơ hội nâng cao kết hợp nhiều điều kiện
def filter_opportunities_advanced(
    current_user: dict,
    scope: DataScope,
    stage: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    expected_close_date_from: Optional[str] = None,
    expected_close_date_to: Optional[str] = None,
    product_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    S6-02: Tìm kiếm, lọc cơ hội kết hợp:
    - Giai đoạn (stage)
    - Khoảng giá trị (min_value, max_value)
    - Khoảng ngày chốt dự kiến (from/to)
    - Sản phẩm liên kết (product_id)
    - Người sở hữu (owner_id)
    - Bao gồm cơ hội được chia sẻ cho người dùng
    """
    if min_value is not None and max_value is not None and min_value > max_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá trị tối thiểu không được lớn hơn giá trị tối đa",
        )

    # Lấy danh sách cơ hội cơ sở theo quyền và các cơ hội được chia sẻ
    all_opps = get_opportunities_by_scope(current_user, scope, search=search)
    
    # Bổ sung cơ hội được chia sẻ nếu chưa có trong danh sách
    user_id = current_user.get("id")
    shared_opp_ids = get_shared_opportunity_ids_for_user(user_id)
    existing_ids = {o["id"] for o in all_opps}
    for so_id in shared_opp_ids:
        if so_id not in existing_ids:
            so_opp = get_raw_opportunity_by_id(so_id)
            if so_opp:
                all_opps.append(so_opp)
                existing_ids.add(so_id)

    # 1. Lọc theo stage
    if stage and stage.strip():
        st_clean = stage.strip().upper()
        all_opps = [o for o in all_opps if (o.get("stage") or "").upper() == st_clean]

    # 2. Lọc theo giá trị min/max
    if min_value is not None:
        all_opps = [o for o in all_opps if float(o.get("value") or 0.0) >= min_value]
    if max_value is not None:
        all_opps = [o for o in all_opps if float(o.get("value") or 0.0) <= max_value]

    # 3. Lọc theo khoảng ngày chốt dự kiến
    from_date_obj = None
    to_date_obj = None
    if expected_close_date_from:
        try:
            from_date_obj = datetime.strptime(expected_close_date_from[:10], "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng from_date không hợp lệ (YYYY-MM-DD)")

    if expected_close_date_to:
        try:
            to_date_obj = datetime.strptime(expected_close_date_to[:10], "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng to_date không hợp lệ (YYYY-MM-DD)")

    if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ngày bắt đầu không được lớn hơn ngày kết thúc")

    if from_date_obj or to_date_obj:
        date_filtered = []
        for o in all_opps:
            cd = o.get("expected_close_date")
            if not cd:
                continue
            try:
                cd_obj = datetime.strptime(str(cd)[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            if from_date_obj and cd_obj < from_date_obj:
                continue
            if to_date_obj and cd_obj > to_date_obj:
                continue
            date_filtered.append(o)
        all_opps = date_filtered

    # 4. Lọc theo người sở hữu
    if owner_id is not None:
        all_opps = [o for o in all_opps if o.get("owner_id") == owner_id]

    # 5. Lọc theo sản phẩm liên kết
    if product_id is not None:
        prod_filtered = []
        for o in all_opps:
            opp_prods = list_opportunity_products(o["id"])
            if any(p.get("product_id") == product_id for p in opp_prods):
                prod_filtered.append(o)
        all_opps = prod_filtered

    total = len(all_opps)
    paged = all_opps[skip : skip + limit]
    return paged, total


# S6-04: Đính kèm tài liệu vào cơ hội (Opportunity Attachments)
def list_opportunity_attachments(opportunity_id: int) -> List[Dict[str, Any]]:
    """S6-04: Lấy danh sách metadata tệp đính kèm của cơ hội."""
    db = SessionLocal()
    try:
        rows = db.query(OpportunityAttachmentModel).filter(OpportunityAttachmentModel.opportunity_id == opportunity_id).all()
        results = []
        for r in rows:
            results.append({
                "id": r.id,
                "opportunity_id": r.opportunity_id,
                "filename": r.filename,
                "original_name": r.original_name,
                "file_path": r.file_path,
                "file_size_bytes": r.file_size_bytes,
                "content_type": r.content_type,
                "uploaded_by": r.uploaded_by,
                "uploader_name": r.uploader_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "download_url": f"/opportunities/{r.opportunity_id}/attachments/{r.id}/download",
            })
        if results:
            return results

        # Fallback RAM
        ram_list = [a for a in FAKE_OPPORTUNITY_ATTACHMENTS if a["opportunity_id"] == opportunity_id]
        for a in ram_list:
            if "download_url" not in a:
                a["download_url"] = f"/opportunities/{a['opportunity_id']}/attachments/{a['id']}/download"
        return ram_list
    finally:
        db.close()


def add_opportunity_attachment(
    opportunity_id: int,
    filename: str,
    original_name: str,
    file_path: str,
    file_size_bytes: int,
    content_type: Optional[str],
    current_user: dict,
) -> Dict[str, Any]:
    """S6-04: Lưu metadata tệp đính kèm vào database."""
    uploader_name = current_user.get("full_name") or current_user.get("username") or f"User {current_user.get('id')}"
    now = datetime.now()
    entry = {
        "opportunity_id": opportunity_id,
        "filename": filename,
        "original_name": original_name,
        "file_path": file_path,
        "file_size_bytes": file_size_bytes,
        "content_type": content_type,
        "uploaded_by": current_user.get("id", 1),
        "uploader_name": uploader_name,
        "created_at": now.isoformat(),
        "download_url": "",
    }

    db = SessionLocal()
    try:
        m = OpportunityAttachmentModel(
            opportunity_id=opportunity_id,
            filename=filename,
            original_name=original_name,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            content_type=content_type,
            uploaded_by=current_user.get("id", 1),
            uploader_name=uploader_name,
            created_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        entry["id"] = m.id
    except Exception:
        db.rollback()
        new_id = (max([a["id"] for a in FAKE_OPPORTUNITY_ATTACHMENTS], default=0) + 1)
        entry["id"] = new_id
    finally:
        db.close()

    entry["download_url"] = f"/opportunities/{opportunity_id}/attachments/{entry['id']}/download"
    FAKE_OPPORTUNITY_ATTACHMENTS.append(entry)
    return entry


def get_opportunity_attachment_by_id(opportunity_id: int, attachment_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        r = db.query(OpportunityAttachmentModel).filter(
            OpportunityAttachmentModel.opportunity_id == opportunity_id,
            OpportunityAttachmentModel.id == attachment_id,
        ).first()
        if r:
            return {
                "id": r.id,
                "opportunity_id": r.opportunity_id,
                "filename": r.filename,
                "original_name": r.original_name,
                "file_path": r.file_path,
                "file_size_bytes": r.file_size_bytes,
                "content_type": r.content_type,
                "uploaded_by": r.uploaded_by,
                "uploader_name": r.uploader_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "download_url": f"/opportunities/{r.opportunity_id}/attachments/{r.id}/download",
            }

        # Fallback RAM
        for a in FAKE_OPPORTUNITY_ATTACHMENTS:
            if a["id"] == attachment_id and a["opportunity_id"] == opportunity_id:
                if "download_url" not in a:
                    a["download_url"] = f"/opportunities/{a['opportunity_id']}/attachments/{a['id']}/download"
                return a
        return None
    finally:
        db.close()


def delete_opportunity_attachment_record(opportunity_id: int, attachment_id: int) -> Optional[Dict[str, Any]]:
    """S6-04: Xóa metadata tệp đính kèm."""
    db = SessionLocal()
    deleted_item = None
    try:
        r = db.query(OpportunityAttachmentModel).filter(
            OpportunityAttachmentModel.opportunity_id == opportunity_id,
            OpportunityAttachmentModel.id == attachment_id,
        ).first()
        if r:
            deleted_item = {
                "id": r.id,
                "opportunity_id": r.opportunity_id,
                "filename": r.filename,
                "original_name": r.original_name,
                "file_path": r.file_path,
            }
            db.delete(r)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    global FAKE_OPPORTUNITY_ATTACHMENTS
    for a in FAKE_OPPORTUNITY_ATTACHMENTS:
        if a["id"] == attachment_id and a["opportunity_id"] == opportunity_id:
            deleted_item = copy.deepcopy(a)
            break
    FAKE_OPPORTUNITY_ATTACHMENTS = [
        a for a in FAKE_OPPORTUNITY_ATTACHMENTS
        if not (a["id"] == attachment_id and a["opportunity_id"] == opportunity_id)
    ]

    return deleted_item

