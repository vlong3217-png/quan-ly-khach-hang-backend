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


def reset_fake_contracts() -> None:
    global FAKE_CONTRACTS
    FAKE_CONTRACTS = copy.deepcopy(INITIAL_CONTRACTS)


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
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Lấy danh sách hợp đồng theo quyền hạn (DataScope) và bộ lọc."""
    # Lấy từ RAM
    results = list(FAKE_CONTRACTS)

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
    """Lấy chi tiết một hợp đồng theo ID."""
    for c in FAKE_CONTRACTS:
        if c.get("id") == contract_id:
            return c
    return None


def get_contract_by_quote_id(quote_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """Tra cứu hợp đồng được sinh từ một báo giá."""
    for c in FAKE_CONTRACTS:
        if c.get("quote_id") == quote_id:
            return c
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
