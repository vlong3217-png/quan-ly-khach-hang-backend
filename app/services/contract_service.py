"""
Contract service with dual-mode (MySQL Database persistence & in-memory fallback) (S7-04).
Handles conversion of accepted quotes into contracts, product inheritance,
unique contract numbers, dates validation, and automatic opportunity win closing.
"""

import copy
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.dependencies import DataScope
from app.models.contract import ContractModel, ContractItemModel
from app.models.opportunity import OpportunityModel
from app.services.quote_service import get_raw_quote_by_id, FAKE_QUOTES


INITIAL_CONTRACTS: List[Dict[str, Any]] = []
FAKE_CONTRACTS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_CONTRACTS)

DEFAULT_RENEWAL_THRESHOLD = 30
CURRENT_RENEWAL_SETTINGS = {
    "threshold_days": 30,
    "updated_at": None,
    "updated_by": "Hệ thống mặc định",
}


def reset_fake_contracts() -> None:
    global FAKE_CONTRACTS, CURRENT_RENEWAL_SETTINGS
    FAKE_CONTRACTS.clear()
    FAKE_CONTRACTS.extend(copy.deepcopy(INITIAL_CONTRACTS))
    CURRENT_RENEWAL_SETTINGS["threshold_days"] = 30
    CURRENT_RENEWAL_SETTINGS["updated_at"] = None
    CURRENT_RENEWAL_SETTINGS["updated_by"] = "Hệ thống mặc định"
    try:
        db = SessionLocal()
        try:
            db.query(ContractItemModel).delete()
            db.query(ContractModel).delete()
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _contract_model_to_dict(m: ContractModel, db: Optional[Session] = None) -> dict:
    items = []
    own_session = False
    if db is None:
        try:
            db = SessionLocal()
            own_session = True
        except Exception:
            db = None

    if db is not None:
        try:
            it_rows = db.query(ContractItemModel).filter(ContractItemModel.contract_id == m.id).all()
            for it in it_rows:
                items.append({
                    "id": it.id,
                    "contract_id": it.contract_id,
                    "product_id": it.product_id,
                    "product_code": it.product_code,
                    "product_name": it.product_name,
                    "unit": it.unit,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "floor_price": it.floor_price,
                    "discount_type": it.discount_type,
                    "discount_value": it.discount_value,
                    "line_discount_amount": it.line_discount_amount,
                    "vat_rate": it.vat_rate,
                    "line_vat_amount": it.line_vat_amount,
                    "line_total": it.line_total,
                    "notes": it.notes,
                })
        except Exception:
            pass
        finally:
            if own_session:
                db.close()

    return {
        "id": m.id,
        "contract_number": m.contract_number,
        "title": m.title,
        "quote_id": m.quote_id,
        "quote_number": m.quote_number,
        "customer_id": m.customer_id,
        "customer_name": m.customer_name,
        "opportunity_id": m.opportunity_id,
        "opportunity_title": m.opportunity_title,
        "owner_id": m.owner_id,
        "team_id": m.team_id,
        "status": m.status or "ACTIVE",
        "signed_date": m.signed_date.isoformat() if m.signed_date else None,
        "effective_date": m.effective_date.isoformat() if m.effective_date else None,
        "expiration_date": m.expiration_date.isoformat() if m.expiration_date else None,
        "payment_terms": m.payment_terms,
        "delivery_terms": m.delivery_terms,
        "notes": m.notes,
        "items": items,
        "subtotal": float(m.subtotal or 0.0),
        "total_line_discount": float(m.total_line_discount or 0.0),
        "overall_discount_type": m.overall_discount_type or "PERCENT",
        "overall_discount_value": float(m.overall_discount_value or 0.0),
        "overall_discount_amount": float(m.overall_discount_amount or 0.0),
        "total_discount_amount": float(m.total_discount_amount or 0.0),
        "discount_percentage": float(m.discount_percentage or 0.0),
        "vat_amount": float(m.vat_amount or 0.0),
        "grand_total": float(m.grand_total or 0.0),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _get_all_contracts(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    own_session = False
    if db is None:
        try:
            db = SessionLocal()
            own_session = True
        except Exception:
            db = None

    if db is not None:
        try:
            rows = db.query(ContractModel).order_by(ContractModel.id.desc()).all()
            if rows or not FAKE_CONTRACTS:
                res = [_contract_model_to_dict(r, db) for r in rows]
                FAKE_CONTRACTS.clear()
                FAKE_CONTRACTS.extend(copy.deepcopy(res))
                return res
        except Exception:
            pass
        finally:
            if own_session:
                db.close()

    return list(FAKE_CONTRACTS)


def get_renewal_threshold_setting() -> dict:
    """Lấy cấu hình ngưỡng cảnh báo hợp đồng sắp hết hạn hiện tại (S7-07 AC 2)."""
    return dict(CURRENT_RENEWAL_SETTINGS)


def update_renewal_threshold_setting(new_threshold: int, current_user: Optional[dict] = None) -> dict:
    """Cập nhật ngưỡng cảnh báo hợp đồng sắp hết hạn (S7-07 AC 2)."""
    if new_threshold < 1 or new_threshold > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngưỡng cảnh báo hết hạn phải từ 1 đến 365 ngày (S7-07 AC 2)",
        )
    user_name = "Quản trị viên"
    if current_user:
        user_name = current_user.get("full_name") or current_user.get("username", "Quản trị viên")
    now_iso = datetime.now().isoformat()
    CURRENT_RENEWAL_SETTINGS["threshold_days"] = int(new_threshold)
    CURRENT_RENEWAL_SETTINGS["updated_at"] = now_iso
    CURRENT_RENEWAL_SETTINGS["updated_by"] = user_name
    return dict(CURRENT_RENEWAL_SETTINGS)


def _enrich_contract_expiration_info(c: dict, threshold_days: Optional[int] = None) -> dict:
    """
    Bổ sung thông tin hiệu lực và thời hạn cho hợp đồng (S7-07 AC 1 & AC 2):
    - days_remaining: Số ngày còn lại đến hạn hết hạn (tính từ date.today()).
    - validity_status: ACTIVE, EXPIRING_SOON, EXPIRED, RENEWED, TERMINATED.
    - is_expiring_soon: True nếu 0 <= days_remaining <= threshold_days và chưa tạo cơ hội gia hạn.
    - is_expired: True nếu days_remaining < 0.
    - urgency_level: CRITICAL (<= 7 ngày), HIGH (8 - 15 ngày), MEDIUM (> 15 ngày).
    """
    threshold = threshold_days if threshold_days is not None else CURRENT_RENEWAL_SETTINGS["threshold_days"]
    today = date.today()
    exp_raw = c.get("expiration_date")

    days_remaining = 365
    is_expired = False
    urgency_level = "MEDIUM"

    if exp_raw:
        try:
            exp_str = str(exp_raw)[:10]
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            days_remaining = (exp_date - today).days
            is_expired = days_remaining < 0
        except Exception:
            days_remaining = 365

    is_renewal_created = bool(c.get("is_renewal_created", False))
    is_expiring_soon = (0 <= days_remaining <= threshold) and not is_renewal_created

    # Xác định mức độ khẩn cấp (AC 2)
    if days_remaining <= 7:
        urgency_level = "CRITICAL"
    elif days_remaining <= 15:
        urgency_level = "HIGH"
    else:
        urgency_level = "MEDIUM"

    # Xác định trạng thái hiệu lực (AC 1)
    status_upper = str(c.get("status", "")).upper()
    if is_renewal_created or status_upper == "RENEWED":
        validity_status = "RENEWED"
    elif status_upper in ("TERMINATED", "CANCELLED"):
        validity_status = "TERMINATED"
    elif is_expired:
        validity_status = "EXPIRED"
    elif is_expiring_soon:
        validity_status = "EXPIRING_SOON"
    else:
        validity_status = "ACTIVE"

    c["days_remaining"] = days_remaining
    c["is_expired"] = is_expired
    c["is_expiring_soon"] = is_expiring_soon
    c["validity_status"] = validity_status
    c["urgency_level"] = urgency_level
    c.setdefault("is_renewal_created", is_renewal_created)
    c.setdefault("renewal_opportunity_id", c.get("renewal_opportunity_id"))
    return c


def _safe_log_audit(
    user_id: int,
    user_name: str,
    entity_id: str,
    action: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    db=None,
):
    """Ghi nhận Audit Log an toàn, không gây timeout khi database MySQL offline."""
    if db is None:
        return
    try:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=user_id,
            user_name=user_name,
            entity_type="CONTRACT",
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            db=db,
        )
        db.commit()
    except Exception:
        pass


def check_contract_number_exists(contract_number: str, db: Optional[Session] = None) -> bool:
    """Kiểm tra số hợp đồng đã tồn tại trong hệ thống chưa (S7-04 AC 4)."""
    clean_num = contract_number.strip().upper()

    # 1. Kiểm tra RAM
    for c in FAKE_CONTRACTS:
        if str(c.get("contract_number", "")).strip().upper() == clean_num:
            return True

    # 2. Kiểm tra Database MySQL nếu có DB session
    if db is not None:
        try:
            exists = db.query(ContractModel).filter(
                ContractModel.contract_number == clean_num
            ).first()
            if exists:
                return True
        except Exception:
            pass

    return False


def generate_unique_contract_number(db: Optional[Session] = None) -> str:
    """Tự động sinh số hợp đồng gợi ý duy nhất theo ngày: HD-YYYYMMDD-XXX (S7-04 AC 4)."""
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"HD-{today_str}-"

    counter = 1
    while True:
        candidate = f"{prefix}{counter:03d}"
        if not check_contract_number_exists(candidate, db=db):
            return candidate
        counter += 1


def get_contracts_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    is_expiring_soon: Optional[bool] = None,
    expiring_within_days: Optional[int] = None,
    validity_status: Optional[str] = None,
    threshold_days: Optional[int] = None,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Lấy danh sách hợp đồng theo quyền hạn (DataScope) và bộ lọc kèm thông tin thời hạn."""
    # Lấy từ MySQL / RAM và làm giàu thông tin thời hạn (S7-07 AC 1)
    all_stored = _get_all_contracts(db=db)
    results = [_enrich_contract_expiration_info(c, threshold_days=threshold_days) for c in all_stored]

    # Lọc theo DataScope
    if scope == DataScope.ALL:
        pass
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is not None:
            results = [c for c in results if c.get("team_id") == user_team_id]
    else:  # DataScope.MY
        user_id = current_user["id"]
        results = [c for c in results if c.get("owner_id") == user_id]

    # Lọc theo khách hàng
    if customer_id is not None:
        results = [c for c in results if c.get("customer_id") == customer_id]

    # Lọc theo trạng thái
    if status_filter:
        sf = status_filter.upper().strip()
        results = [c for c in results if str(c.get("status", "")).upper() == sf]

    # Lọc theo hợp đồng sắp hết hạn (S7-07 AC 1)
    if is_expiring_soon is not None:
        results = [c for c in results if c.get("is_expiring_soon") == is_expiring_soon]

    # Lọc theo số ngày còn lại (S7-07 AC 1)
    if expiring_within_days is not None:
        results = [c for c in results if 0 <= c.get("days_remaining", 9999) <= expiring_within_days]

    # Lọc theo trạng thái hiệu lực (ACTIVE, EXPIRING_SOON, EXPIRED, RENEWED)
    if validity_status:
        vs = validity_status.upper().strip()
        results = [c for c in results if str(c.get("validity_status", "")).upper() == vs]

    # Tìm kiếm
    if search and search.strip():
        kw = search.lower().strip()
        results = [
            c for c in results
            if kw in str(c.get("contract_number", "")).lower()
            or kw in str(c.get("title", "")).lower()
            or kw in str(c.get("customer_name", "")).lower()
            or kw in str(c.get("quote_number", "")).lower()
        ]

    # Sắp xếp mới nhất lên đầu
    results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return results


def get_contract_by_id(contract_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết một hợp đồng theo ID kèm thông tin thời hạn (S7-07 AC 1)."""
    contracts = _get_all_contracts(db=db)
    for c in contracts:
        if c.get("id") == contract_id:
            return _enrich_contract_expiration_info(c)
    return None


def get_contract_by_quote_id(quote_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """Tra cứu hợp đồng được sinh từ một báo giá kèm thông tin thời hạn."""
    contracts = _get_all_contracts(db=db)
    for c in contracts:
        if c.get("quote_id") == quote_id:
            return _enrich_contract_expiration_info(c)
    return None


def convert_quote_to_contract(
    quote_id: int,
    data: dict,
    current_user: dict,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Chuyển báo giá được chấp nhận thành hợp đồng (S7-04):
    1. AC 1: Kế thừa toàn bộ dòng sản phẩm và giá đã chốt, không nhập lại.
    2. AC 2: Khai báo số hợp đồng, ngày ký, ngày hiệu lực, ngày hết hạn, điều khoản thanh toán.
    3. AC 3: Cơ hội tương ứng tự động chuyển sang Đóng thắng (CLOSED_WON) với giá trị đúng bằng giá trị hợp đồng.
    4. AC 4: Số hợp đồng là duy nhất.
    """
    quote = get_raw_quote_by_id(quote_id)
    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá để chuyển đổi thành hợp đồng",
        )

    # Kiểm tra nếu báo giá đã được chuyển đổi thành hợp đồng trước đó
    if quote.get("contract_id") or quote.get("is_converted_to_contract"):
        c_num = quote.get("contract_number") or f"ID {quote.get('contract_id')}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Báo giá {quote.get('quote_number')} đã được chuyển đổi thành hợp đồng {c_num} trước đó.",
        )

    # AC 1: Kiểm tra trạng thái báo giá hợp lệ (phải đã duyệt hoặc chấp nhận)
    quote_status = str(quote.get("status", "")).upper()
    if quote_status in ("DRAFT", "PENDING_APPROVAL", "REJECTED", "RETURNED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể chuyển đổi báo giá đã được phê duyệt hoặc đã được khách hàng chấp nhận thành hợp đồng (S7-04 AC 1).",
        )

    # AC 4: Xử lý số hợp đồng và kiểm tra tính duy nhất
    contract_number = (data.get("contract_number") or "").strip()
    if not contract_number:
        contract_number = generate_unique_contract_number(db=db)
    else:
        if check_contract_number_exists(contract_number, db=db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số hợp đồng '{contract_number}' đã tồn tại trong hệ thống. Vui lòng nhập số hợp đồng khác (S7-04 AC 4).",
            )

    # AC 2: Khai báo & Kiểm tra tính hợp lệ của ngày tháng
    signed_date = data.get("signed_date")
    effective_date = data.get("effective_date")
    expiration_date = data.get("expiration_date")

    if not signed_date or not effective_date or not expiration_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc khai báo ngày ký, ngày hiệu lực và ngày hết hạn hợp đồng (S7-04 AC 2).",
        )

    # Chuyển đổi về date object nếu truyền vào dạng string
    def _parse_date(d_val):
        if isinstance(d_val, str):
            return datetime.strptime(d_val[:10], "%Y-%m-%d").date()
        return d_val

    try:
        s_date = _parse_date(signed_date)
        eff_date = _parse_date(effective_date)
        exp_date = _parse_date(expiration_date)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng ngày không hợp lệ (YYYY-MM-DD): {str(e)}",
        )

    if exp_date < eff_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày hết hạn hợp đồng không thể trước ngày bắt đầu có hiệu lực (S7-04 AC 2).",
        )

    # AC 1: Kế thừa toàn bộ dòng sản phẩm từ báo giá (độc lập ID mới)
    new_contract_id = (max(c["id"] for c in FAKE_CONTRACTS) + 1) if FAKE_CONTRACTS else 1
    contract_items = []
    for idx, item in enumerate(quote.get("items", [])):
        c_item = copy.deepcopy(item)
        c_item["id"] = f"ct-it-{new_contract_id}-{idx + 1}"
        c_item["contract_id"] = new_contract_id
        contract_items.append(c_item)

    # AC 1: Kế thừa toàn bộ tính toán tài chính đã chốt
    subtotal = float(quote.get("subtotal") or 0.0)
    total_line_discount = float(quote.get("total_line_discount") or 0.0)
    overall_discount_type = quote.get("overall_discount_type") or "PERCENT"
    overall_discount_value = float(quote.get("overall_discount_value") or 0.0)
    overall_discount_amount = float(quote.get("overall_discount_amount") or 0.0)
    total_discount_amount = float(quote.get("total_discount_amount") or 0.0)
    discount_percentage = float(quote.get("discount_percentage") or 0.0)
    vat_amount = float(quote.get("vat_amount") or 0.0)
    grand_total = float(quote.get("grand_total") or quote.get("amount") or 0.0)

    # Điều khoản thanh toán & giao hàng (kế thừa nếu client không nhập đè)
    payment_terms = (data.get("payment_terms") or "").strip() or quote.get("payment_terms") or "Thanh toán theo tiến độ hợp đồng."
    delivery_terms = (data.get("delivery_terms") or "").strip() or quote.get("delivery_terms") or ""
    title = (data.get("title") or "").strip() or f"Hợp đồng kinh tế - {quote.get('title') or quote.get('quote_number')}"
    notes = (data.get("notes") or "").strip() or quote.get("notes") or ""

    now_iso = datetime.now().isoformat()

    new_contract = {
        "id": new_contract_id,
        "contract_number": contract_number,
        "title": title,
        "quote_id": quote["id"],
        "quote_number": quote.get("quote_number"),
        "customer_id": quote.get("customer_id") or 1,
        "customer_name": quote.get("customer_name") or f"Khách hàng ID {quote.get('customer_id')}",
        "opportunity_id": quote.get("opportunity_id"),
        "opportunity_title": quote.get("opportunity_title"),
        "owner_id": quote.get("owner_id") or current_user.get("id", 1),
        "team_id": quote.get("team_id"),
        "status": "ACTIVE",
        "signed_date": str(s_date),
        "effective_date": str(eff_date),
        "expiration_date": str(exp_date),
        "payment_terms": payment_terms,
        "delivery_terms": delivery_terms,
        "notes": notes,
        "items": contract_items,
        "subtotal": subtotal,
        "total_line_discount": total_line_discount,
        "overall_discount_type": overall_discount_type,
        "overall_discount_value": overall_discount_value,
        "overall_discount_amount": overall_discount_amount,
        "total_discount_amount": total_discount_amount,
        "discount_percentage": discount_percentage,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    # Lưu vào In-Memory RAM
    FAKE_CONTRACTS.append(new_contract)

    # Lưu vào Database MySQL nếu có DB session
    if db is not None:
        try:
            db_contract = ContractModel(
                contract_number=contract_number,
                title=title,
                quote_id=quote["id"],
                quote_number=quote.get("quote_number"),
                customer_id=quote.get("customer_id") or 1,
                customer_name=new_contract["customer_name"],
                opportunity_id=quote.get("opportunity_id"),
                opportunity_title=quote.get("opportunity_title"),
                owner_id=new_contract["owner_id"],
                team_id=new_contract["team_id"],
                status="ACTIVE",
                signed_date=s_date,
                effective_date=eff_date,
                expiration_date=exp_date,
                payment_terms=payment_terms,
                delivery_terms=delivery_terms,
                notes=notes,
                subtotal=subtotal,
                total_line_discount=total_line_discount,
                overall_discount_type=overall_discount_type,
                overall_discount_value=overall_discount_value,
                overall_discount_amount=overall_discount_amount,
                total_discount_amount=total_discount_amount,
                discount_percentage=discount_percentage,
                vat_amount=vat_amount,
                grand_total=grand_total,
            )
            db.add(db_contract)
            db.commit()
            db.refresh(db_contract)
            new_contract["id"] = db_contract.id

            # Lưu dòng sản phẩm hợp đồng vào MySQL
            for it in contract_items:
                db_item = ContractItemModel(
                    contract_id=db_contract.id,
                    product_id=it.get("product_id"),
                    product_code=it.get("product_code", ""),
                    product_name=it.get("product_name", ""),
                    unit=it.get("unit", "Gói"),
                    quantity=int(it.get("quantity") or 1),
                    unit_price=float(it.get("unit_price") or 0.0),
                    floor_price=it.get("floor_price"),
                    discount_type=it.get("discount_type", "PERCENT"),
                    discount_value=float(it.get("discount_value") or 0.0),
                    line_discount_amount=float(it.get("line_discount_amount") or 0.0),
                    vat_rate=int(it.get("vat_rate") or 10),
                    line_vat_amount=float(it.get("line_vat_amount") or 0.0),
                    line_total=float(it.get("line_total") or 0.0),
                    notes=it.get("notes"),
                )
                db.add(db_item)
            db.commit()
        except Exception:
            if db:
                db.rollback()

    # AC 3: Tự động chuyển cơ hội tương ứng sang Đóng thắng với giá trị đúng bằng giá trị hợp đồng
    opp_id = quote.get("opportunity_id")
    if opp_id:
        _close_opportunity_as_won(
            opportunity_id=opp_id,
            contract_value=grand_total,
            contract_number=contract_number,
            current_user=current_user,
            db=db,
        )

    # Cập nhật trạng thái báo giá gốc
    prev_quote_status = quote.get("status")
    quote["status"] = "ACCEPTED"
    quote["contract_id"] = new_contract["id"]
    quote["contract_number"] = contract_number
    quote["is_converted_to_contract"] = True
    quote["updated_at"] = now_iso

    quote.setdefault("approval_history", []).append({
        "id": f"hist-contract-{int(datetime.now().timestamp() * 1000)}",
        "action": "CONVERT_TO_CONTRACT",
        "performed_by_id": current_user.get("id"),
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Kế toán"),
        "performed_by_role": current_user.get("role", "ACCOUNTANT"),
        "comments": f"Chuyển đổi báo giá thành hợp đồng số {contract_number}. Cơ hội liên kết tự động chốt Thắng (S7-04 AC 3).",
        "previous_status": prev_quote_status,
        "new_status": "ACCEPTED",
        "timestamp": now_iso,
    })

    # Ghi nhận Audit Log
    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"CONTRACT-{new_contract['id']}",
        action="CONVERT_QUOTE_TO_CONTRACT",
        field_name="contract_number",
        old_value=quote.get("quote_number"),
        new_value=contract_number,
        db=db,
    )

    return new_contract


def _close_opportunity_as_won(
    opportunity_id: int,
    contract_value: float,
    contract_number: str,
    current_user: dict,
    db: Optional[Session] = None,
) -> None:
    """
    S7-04 AC 3: Chuyển cơ hội tương ứng sang Đóng thắng (CLOSED_WON)
    với giá trị đúng bằng giá trị hợp đồng đã chốt.
    """
    # 1. Cập nhật trong Mock In-Memory RAM
    from app.services.opportunity_service import FAKE_OPPORTUNITIES, TEST_SAMPLE_OPPORTUNITIES
    for opp_list in (FAKE_OPPORTUNITIES, TEST_SAMPLE_OPPORTUNITIES):
        for o in opp_list:
            if o.get("id") == opportunity_id:
                o["stage"] = "CLOSED_WON"
                o["status"] = "CLOSED_WON"
                o["value"] = float(contract_value)
                o["win_probability"] = 100.0
                o["probability_notes"] = f"Tự động chuyển Thắng khi ký hợp đồng {contract_number} (S7-04 AC 3)"
                o["updated_at"] = datetime.now().isoformat()

    # 2. Cập nhật trong Database MySQL nếu có DB session
    if db is not None:
        try:
            opp_db = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
            if opp_db:
                opp_db.stage = "CLOSED_WON"
                opp_db.status = "CLOSED_WON"
                opp_db.value = float(contract_value)
                opp_db.win_probability = 100.0
                opp_db.probability_notes = f"Tự động chuyển Thắng khi ký hợp đồng {contract_number} (S7-04 AC 3)"
                db.commit()
        except Exception:
            if db:
                db.rollback()

    # 3. Ghi nhận Audit Log cho cơ hội
    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"OPPORTUNITY-{opportunity_id}",
        action="CLOSE_OPPORTUNITY_WON",
        field_name="stage",
        old_value="OPEN",
        new_value="CLOSED_WON",
        db=db,
    )


# ============================================================================
# S7-07: Expiring Alerts & Renewal Opportunity Creation Functions
# ============================================================================

def get_expiring_soon_contracts(
    threshold_days: Optional[int] = None,
    current_user: Optional[dict] = None,
    scope: Optional[DataScope] = None,
    customer_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Cảnh báo hợp đồng sắp hết hạn theo ngưỡng cấu hình được (S7-07 AC 2):
    - Tổng hợp số hợp đồng sắp hết hạn (0 <= days_remaining <= threshold_days)
    - Tính tổng doanh thu có nguy cơ mất nếu không gia hạn (total_revenue_at_risk)
    - Phân nhóm mức độ khẩn cấp (critical: <= 7 ngày, high: 8-15 ngày, medium: 16-threshold ngày)
    - Danh sách chi tiết hợp đồng sắp hết hạn
    """
    eff_threshold = threshold_days if threshold_days is not None else CURRENT_RENEWAL_SETTINGS["threshold_days"]

    user = current_user or {"id": 1, "role": "ADMIN", "team_id": None}
    eff_scope = scope or DataScope.ALL

    all_contracts = get_contracts_by_scope(
        current_user=user,
        scope=eff_scope,
        customer_id=customer_id,
        threshold_days=eff_threshold,
        db=db,
    )

    # Lọc các hợp đồng sắp hết hạn (chưa được tạo cơ hội gia hạn và chưa bị thanh lý)
    expiring_list = [
        c for c in all_contracts
        if c.get("is_expiring_soon") and not c.get("is_renewal_created") and c.get("validity_status") != "TERMINATED"
    ]

    # Sắp xếp theo số ngày còn lại tăng dần (gần hết hạn nhất lên đầu)
    expiring_list.sort(key=lambda x: x.get("days_remaining", 0))

    critical_count = len([c for c in expiring_list if c.get("days_remaining", 0) <= 7])
    high_count = len([c for c in expiring_list if 8 <= c.get("days_remaining", 0) <= 15])
    medium_count = len([c for c in expiring_list if c.get("days_remaining", 0) > 15])
    total_rev_risk = sum(float(c.get("grand_total") or 0.0) for c in expiring_list)

    return {
        "threshold_days": eff_threshold,
        "total_expiring": len(expiring_list),
        "total_revenue_at_risk": round(total_rev_risk, 2),
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "contracts": expiring_list,
    }


def create_renewal_opportunity_from_contract(
    contract_id: int,
    data: Optional[dict] = None,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Tạo cơ hội gia hạn từ một hợp đồng sắp hết hạn (S7-07 AC 3):
    - Kiểm tra hợp đồng tồn tại
    - Chặn tạo trùng lặp nếu hợp đồng đã có cơ hội gia hạn
    - Kế thừa toàn bộ dòng sản phẩm từ hợp đồng cũ sang cơ hội gia hạn mới
    - Kế thừa giá trị hợp đồng, ngày hết hạn làm ngày dự kiến chốt
    - Cập nhật hợp đồng: renewal_opportunity_id, is_renewal_created = True, status = "RENEWED"
    - Ghi nhận Activity vào dòng thời gian Cơ hội và Hợp đồng
    - Ghi nhận Audit Log
    """
    contract = get_contract_by_id(contract_id, db=db)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng để tạo cơ hội gia hạn (S7-07 AC 3)",
        )

    _enrich_contract_expiration_info(contract)

    if contract.get("is_renewal_created"):
        opp_id = contract.get("renewal_opportunity_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hợp đồng số '{contract.get('contract_number')}' đã được tạo cơ hội gia hạn #{opp_id} trước đó (S7-07 AC 3).",
        )

    payload = data or {}
    user = current_user or {"id": contract.get("owner_id", 1), "role": "ACCOUNTANT", "full_name": "Kế toán"}
    user_id = user.get("id", 1)

    opp_title = (payload.get("title") or "").strip() or f"Gia hạn hợp đồng {contract.get('contract_number')} - {contract.get('title')}"
    opp_value = float(payload.get("value") if payload.get("value") is not None else (contract.get("grand_total") or 0.0))
    exp_date_str = str(payload.get("expected_close_date") or contract.get("expiration_date"))[:10]
    opp_owner = payload.get("owner_id") or contract.get("owner_id") or user_id
    opp_stage = payload.get("stage") or "PROPOSAL"
    opp_notes = payload.get("notes") or f"Cơ hội gia hạn tự động khởi tạo từ hợp đồng {contract.get('contract_number')} (S7-07 AC 3)."

    from app.services.opportunity_service import create_opportunity_record, FAKE_OPPORTUNITY_PRODUCTS, FAKE_OPPORTUNITIES
    opp_create_payload = {
        "title": opp_title,
        "value": opp_value,
        "stage": opp_stage,
        "customer_id": contract.get("customer_id"),
        "expected_close_date": exp_date_str,
        "owner_id": opp_owner,
        "description": opp_notes,
    }

    actor_for_opp = {
        "id": opp_owner,
        "role": user.get("role", "ACCOUNTANT"),
        "full_name": user.get("full_name", "Kế toán"),
        "team_id": contract.get("team_id"),
    }
    new_opp = create_opportunity_record(opp_create_payload, current_user=actor_for_opp)
    new_opp_id = new_opp["id"]

    # Kế thừa toàn bộ dòng sản phẩm từ hợp đồng cũ sang cơ hội gia hạn (AC 3)
    inherited_products = []
    max_prod_id = max([p["id"] for p in FAKE_OPPORTUNITY_PRODUCTS if isinstance(p.get("id"), int)], default=0)
    for idx, item in enumerate(contract.get("items", [])):
        max_prod_id += 1
        unit_price = float(item.get("unit_price") or 0.0)
        floor_price = float(item.get("floor_price") or 0.0) if item.get("floor_price") is not None else 0.0
        prod_dict = {
            "id": max_prod_id,
            "opportunity_id": new_opp_id,
            "product_id": int(item.get("product_id") or 1),
            "product_code": item.get("product_code", ""),
            "product_name": item.get("product_name", ""),
            "product_type": "SUBSCRIPTION" if "bảo trì" in item.get("product_name", "").lower() or "cloud" in item.get("product_name", "").lower() else "ONE_TIME",
            "quantity": float(item.get("quantity") or 1.0),
            "unit_price": unit_price,
            "floor_price": floor_price,
            "discount_percent": float(item.get("discount_value") or 0.0) if item.get("discount_type") == "PERCENT" else 0.0,
            "amount": float(item.get("line_total") or 0.0),
        }
        FAKE_OPPORTUNITY_PRODUCTS.append(prod_dict)
        inherited_products.append(prod_dict)

    new_opp["products"] = inherited_products
    new_opp["has_products"] = len(inherited_products) > 0
    new_opp["is_renewal"] = True
    new_opp["original_contract_id"] = contract["id"]
    new_opp["original_contract_number"] = contract.get("contract_number")

    # Đảm bảo record trong RAM FAKE_OPPORTUNITIES cũng cập nhật đầy đủ cờ gia hạn
    for o in FAKE_OPPORTUNITIES:
        if o["id"] == new_opp_id:
            o["is_renewal"] = True
            o["original_contract_id"] = contract["id"]
            o["original_contract_number"] = contract.get("contract_number")
            o["products"] = inherited_products
            o["has_products"] = len(inherited_products) > 0
            break

    # Cập nhật hợp đồng
    now_iso = datetime.now().isoformat()
    contract["renewal_opportunity_id"] = new_opp_id
    contract["is_renewal_created"] = True
    contract["status"] = "RENEWED"
    contract["validity_status"] = "RENEWED"
    contract["updated_at"] = now_iso

    # Nếu có DB session
    if db is not None:
        try:
            db_c = db.query(ContractModel).filter(ContractModel.id == contract_id).first()
            if db_c:
                db_c.status = "RENEWED"
                db.commit()
        except Exception:
            pass

    # Ghi nhận Activity vào dòng thời gian Cơ hội và Hợp đồng
    try:
        from app.services import activity_service
        activity_service.create_activity_record({
            "title": f"Tạo cơ hội gia hạn từ hợp đồng {contract.get('contract_number')}",
            "type": "NOTE",
            "description": f"Đã khởi tạo cơ hội gia hạn #{new_opp_id} cho khách hàng từ hợp đồng số {contract.get('contract_number')} (hết hạn ngày {contract.get('expiration_date')}).\nGiá trị dự kiến: {opp_value:,.0f} VNĐ.",
            "customer_id": contract.get("customer_id"),
            "opportunity_id": new_opp_id,
        }, current_user=user)
    except Exception:
        pass

    _safe_log_audit(
        user_id=user_id,
        user_name=user.get("full_name") or "User",
        entity_id=f"CONTRACT-{contract_id}",
        action="CREATE_RENEWAL_OPPORTUNITY",
        field_name="renewal_opportunity_id",
        old_value=None,
        new_value=str(new_opp_id),
        db=db,
    )

    return {
        "contract_id": contract["id"],
        "contract_number": contract.get("contract_number"),
        "opportunity_id": new_opp_id,
        "opportunity_title": new_opp.get("title"),
        "customer_id": contract.get("customer_id"),
        "value": opp_value,
        "stage": opp_stage,
        "expected_close_date": exp_date_str,
        "is_renewal": True,
        "message": f"Đã tạo thành công cơ hội gia hạn #{new_opp_id} từ hợp đồng {contract.get('contract_number')} (S7-07 AC 3)",
    }


def create_direct_contract(
    data: dict,
    current_user: dict,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Tạo hợp đồng trực tiếp hoặc từ báo giá (nếu có quote_id)."""
    quote_id = data.get("quote_id")
    if quote_id and int(quote_id) > 0:
        return convert_quote_to_contract(
            quote_id=int(quote_id),
            data=data,
            current_user=current_user,
            db=db,
        )

    contract_number = (data.get("contract_number") or "").strip()
    if not contract_number:
        contract_number = generate_unique_contract_number(db=db)
    else:
        if check_contract_number_exists(contract_number, db=db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số hợp đồng '{contract_number}' đã tồn tại trong hệ thống.",
            )

    signed_date = data.get("signed_date") or data.get("sign_date")
    effective_date = data.get("effective_date")
    expiration_date = data.get("expiration_date")

    if not signed_date or not effective_date or not expiration_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc khai báo ngày ký, ngày hiệu lực và ngày hết hạn hợp đồng.",
        )

    def _parse_date(d_val):
        if isinstance(d_val, str):
            return datetime.strptime(d_val[:10], "%Y-%m-%d").date()
        return d_val

    s_date = _parse_date(signed_date)
    eff_date = _parse_date(effective_date)
    exp_date = _parse_date(expiration_date)

    if exp_date < eff_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày hết hạn hợp đồng không thể trước ngày bắt đầu có hiệu lực.",
        )

    title = (data.get("title") or "").strip() or f"Hợp đồng kinh tế - {contract_number}"
    payment_terms = (data.get("payment_terms") or "").strip() or "Thanh toán theo tiến độ hợp đồng."
    delivery_terms = (data.get("delivery_terms") or "").strip()
    notes = (data.get("notes") or "").strip()
    customer_id = int(data.get("customer_id") or 1)
    customer_name = data.get("customer_name") or f"Khách hàng ID {customer_id}"
    opportunity_id = data.get("opportunity_id")
    opportunity_title = data.get("opportunity_title")
    owner_id = current_user.get("id", 1)
    team_id = current_user.get("team_id")
    total_value = float(data.get("total_value") or data.get("grand_total") or 0.0)

    now_iso = datetime.now().isoformat()
    raw_items = data.get("items") or []

    new_contract_id = (max([c["id"] for c in FAKE_CONTRACTS], default=0) + 1)
    new_contract = {
        "id": new_contract_id,
        "contract_number": contract_number,
        "title": title,
        "quote_id": 0,
        "quote_number": None,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "opportunity_id": opportunity_id,
        "opportunity_title": opportunity_title,
        "owner_id": owner_id,
        "team_id": team_id,
        "status": "ACTIVE",
        "signed_date": str(s_date),
        "effective_date": str(eff_date),
        "expiration_date": str(exp_date),
        "payment_terms": payment_terms,
        "delivery_terms": delivery_terms,
        "notes": notes,
        "items": raw_items,
        "subtotal": total_value,
        "total_line_discount": 0.0,
        "overall_discount_type": "PERCENT",
        "overall_discount_value": 0.0,
        "overall_discount_amount": 0.0,
        "total_discount_amount": 0.0,
        "discount_percentage": 0.0,
        "vat_amount": 0.0,
        "grand_total": total_value,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    own_session = False
    if db is None:
        try:
            db = SessionLocal()
            own_session = True
        except Exception:
            db = None

    if db is not None:
        try:
            db_contract = ContractModel(
                contract_number=contract_number,
                title=title,
                quote_id=0,
                quote_number=None,
                customer_id=customer_id,
                customer_name=customer_name,
                opportunity_id=int(opportunity_id) if opportunity_id and str(opportunity_id).isdigit() else None,
                opportunity_title=opportunity_title,
                owner_id=owner_id,
                team_id=team_id,
                status="ACTIVE",
                signed_date=s_date,
                effective_date=eff_date,
                expiration_date=exp_date,
                payment_terms=payment_terms,
                delivery_terms=delivery_terms,
                notes=notes,
                subtotal=total_value,
                total_line_discount=0.0,
                overall_discount_type="PERCENT",
                overall_discount_value=0.0,
                overall_discount_amount=0.0,
                total_discount_amount=0.0,
                discount_percentage=0.0,
                vat_amount=0.0,
                grand_total=total_value,
            )
            db.add(db_contract)
            db.commit()
            db.refresh(db_contract)
            new_contract["id"] = db_contract.id

            for idx, it in enumerate(raw_items):
                db_item = ContractItemModel(
                    contract_id=db_contract.id,
                    product_id=it.get("product_id"),
                    product_code=it.get("product_code", f"SP-{idx+1}"),
                    product_name=it.get("product_name", f"Sản phẩm {idx+1}"),
                    unit=it.get("unit", "Gói"),
                    quantity=int(it.get("quantity") or 1),
                    unit_price=float(it.get("unit_price") or 0.0),
                    floor_price=it.get("floor_price"),
                    discount_type=it.get("discount_type", "PERCENT"),
                    discount_value=float(it.get("discount_value") or 0.0),
                    line_discount_amount=float(it.get("line_discount_amount") or 0.0),
                    vat_rate=int(it.get("vat_rate") or 10),
                    line_vat_amount=float(it.get("line_vat_amount") or 0.0),
                    line_total=float(it.get("line_total") or 0.0),
                    notes=it.get("notes"),
                )
                db.add(db_item)
            db.commit()
        except Exception:
            if db:
                db.rollback()
        finally:
            if own_session and db:
                db.close()

    FAKE_CONTRACTS.append(new_contract)
    return new_contract

