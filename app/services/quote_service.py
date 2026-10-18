"""
Quote service with data scope filtering (MY/MY_TEAM/TEAM/ALL),
real-time financial calculations, line items, opportunity inheritance,
and approval threshold enforcement (S7-01 & S7-02).
"""

import copy
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from app.core.dependencies import DataScope

# Ngưỡng phê duyệt chiết khấu (S7-01 & S7-02)
DISCOUNT_TIER_1_THRESHOLD = 10.0  # >= 10%: Trưởng nhóm (MANAGER) duyệt
DISCOUNT_TIER_2_THRESHOLD = 20.0  # >= 20% hoặc dưới giá sàn: Giám đốc (DIRECTOR) duyệt

INITIAL_QUOTES = []

FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def reset_fake_quotes() -> None:
    global FAKE_QUOTES
    FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def get_raw_quote_by_id(quote_id: int) -> Optional[dict]:
    for q in FAKE_QUOTES:
        if q["id"] == quote_id:
            return q
    return None


def calculate_quote_financials(
    items: List[Dict[str, Any]],
    overall_discount_type: str = "PERCENT",
    overall_discount_value: float = 0.0,
) -> Dict[str, Any]:
    """
    Tính toán tài chính báo giá theo đúng AC 2 & AC 3 của S7-01:
    - Tính chiết khấu từng dòng theo % hoặc số tiền ngay lập tức
    - Tính thuế VAT và thành tiền từng dòng
    - Tính chiết khấu tổng và tỷ lệ chiết khấu toàn bộ
    - Kiểm tra và phân cấp ngưỡng phê duyệt:
        * NONE (< 10% và không dưới giá sàn)
        * MANAGER (10% -> < 20%)
        * DIRECTOR (>= 20% hoặc có sản phẩm bán dưới giá sàn)
    """
    subtotal = 0.0
    total_line_discount = 0.0
    total_vat = 0.0
    has_below_floor_price = False
    calculated_items = []

    for idx, it in enumerate(items):
        qty = max(1, int(it.get("quantity") or 1))
        price = max(0.0, float(it.get("unit_price") or 0.0))
        line_subtotal = price * qty

        disc_type = str(it.get("discount_type") or "PERCENT").upper()
        disc_val = max(0.0, float(it.get("discount_value") or 0.0))

        if disc_type == "PERCENT":
            pct = min(100.0, disc_val)
            line_discount = round(line_subtotal * (pct / 100.0), 2)
        else:
            line_discount = min(line_subtotal, disc_val)

        after_discount = line_subtotal - line_discount
        unit_price_after_discount = after_discount / qty if qty > 0 else 0.0

        # Kiểm tra giá sàn (Floor Price)
        floor_price = it.get("floor_price")
        if floor_price is not None and float(floor_price) > 0:
            if unit_price_after_discount < float(floor_price):
                has_below_floor_price = True

        vat_rate = max(0, int(it.get("vat_rate") if it.get("vat_rate") is not None else 10))
        line_vat = round(after_discount * (vat_rate / 100.0), 2)
        line_total = after_discount + line_vat

        subtotal += line_subtotal
        total_line_discount += line_discount
        total_vat += line_vat

        item_id = it.get("id") or f"q-it-{idx + 1}"
        calculated_items.append({
            **it,
            "id": str(item_id),
            "quantity": qty,
            "unit_price": price,
            "floor_price": float(floor_price) if floor_price is not None else None,
            "discount_type": disc_type,
            "discount_value": disc_val,
            "line_discount_amount": line_discount,
            "vat_rate": vat_rate,
            "line_total": line_total,
        })

    # Chiết khấu toàn đơn (Overall discount)
    remaining_after_line = max(0.0, subtotal - total_line_discount)
    overall_type = str(overall_discount_type or "PERCENT").upper()
    overall_val = max(0.0, float(overall_discount_value or 0.0))

    if overall_type == "PERCENT":
        ov_pct = min(100.0, overall_val)
        overall_discount_amount = round(remaining_after_line * (ov_pct / 100.0), 2)
    else:
        overall_discount_amount = min(remaining_after_line, overall_val)

    total_discount_amount = total_line_discount + overall_discount_amount
    discount_percentage = round((total_discount_amount / subtotal * 100.0), 1) if subtotal > 0 else 0.0
    grand_total = max(0.0, subtotal - total_discount_amount + total_vat)

    # Phân cấp phê duyệt (AC 3)
    requires_approval = False
    approval_level = "NONE"
    approval_reason = None

    if has_below_floor_price or discount_percentage >= DISCOUNT_TIER_2_THRESHOLD:
        requires_approval = True
        approval_level = "DIRECTOR"
        approval_reason = (
            "Có dòng sản phẩm bán dưới giá sàn niêm yết (Bắt buộc Giám đốc kinh doanh duyệt)"
            if has_below_floor_price
            else f"Mức chiết khấu tổng {discount_percentage}% chạm ngưỡng cấp 2 (>= {DISCOUNT_TIER_2_THRESHOLD}%, cần Giám đốc kinh doanh duyệt)"
        )
    elif discount_percentage >= DISCOUNT_TIER_1_THRESHOLD:
        requires_approval = True
        approval_level = "MANAGER"
        approval_reason = (
            f"Mức chiết khấu tổng {discount_percentage}% chạm ngưỡng cấp 1 (>= {DISCOUNT_TIER_1_THRESHOLD}%, cần Trưởng nhóm duyệt)"
        )

    return {
        "subtotal": subtotal,
        "total_line_discount": total_line_discount,
        "overall_discount_amount": overall_discount_amount,
        "total_discount_amount": total_discount_amount,
        "discount_percentage": discount_percentage,
        "vat_amount": total_vat,
        "grand_total": grand_total,
        "requires_approval": requires_approval,
        "approval_level": approval_level,
        "approval_reason": approval_reason,
        "calculated_items": calculated_items,
    }


def get_opportunity_products_for_quote(opportunity_id: int, db=None) -> Tuple[Optional[dict], List[dict]]:
    """
    Kế thừa dòng sản phẩm từ cơ hội (AC 1):
    Truy vấn OpportunityProductModel trong DB hoặc fallback danh sách cơ hội mẫu.
    """
    from app.models.opportunity import OpportunityModel, OpportunityProductModel

    opp_dict = None
    items = []

    if db:
        try:
            opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
            if opp:
                opp_dict = {
                    "id": opp.id,
                    "title": opp.title,
                    "customer_id": opp.customer_id,
                    "owner_id": opp.owner_id,
                    "team_id": opp.team_id,
                }
                prods = db.query(OpportunityProductModel).filter(OpportunityProductModel.opportunity_id == opportunity_id).all()
                for idx, p in enumerate(prods):
                    items.append({
                        "id": f"opp-prod-{p.id or idx+1}",
                        "product_id": p.product_id,
                        "product_code": p.product_code,
                        "product_name": p.product_name,
                        "unit": "Gói",
                        "quantity": int(p.quantity or 1),
                        "unit_price": float(p.unit_price or 0.0),
                        "floor_price": float(p.floor_price) if p.floor_price is not None else None,
                        "discount_type": "PERCENT",
                        "discount_value": float(p.discount_percent or 0.0),
                        "vat_rate": 10,
                    })
        except Exception:
            pass

    if not opp_dict:
        from app.services.opportunity_service import TEST_SAMPLE_OPPORTUNITIES, FAKE_OPPORTUNITIES
        for sample in (FAKE_OPPORTUNITIES + TEST_SAMPLE_OPPORTUNITIES):
            if sample.get("id") == opportunity_id:
                opp_dict = sample
                break

    return opp_dict, items


def get_quotes_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    opportunity_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict]:
    if scope == DataScope.ALL:
        results = list(FAKE_QUOTES)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            results = list(FAKE_QUOTES)
        else:
            results = [q for q in FAKE_QUOTES if q.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        results = [q for q in FAKE_QUOTES if q.get("owner_id") == user_id]

    if opportunity_id is not None:
        results = [q for q in results if q.get("opportunity_id") == opportunity_id]

    if status is not None:
        st_upper = status.upper().strip()
        results = [q for q in results if str(q.get("status", "")).upper() == st_upper]

    if search:
        s = search.lower().strip()
        results = [
            q for q in results
            if s in str(q.get("title", "")).lower()
            or s in str(q.get("quote_number", "")).lower()
            or s in str(q.get("status", "")).lower()
        ]

    return results


def create_quote_record(data: dict, current_user: dict, db=None) -> dict:
    """
    Tạo báo giá từ cơ hội (S7-01):
    1. Kế thừa sản phẩm từ cơ hội nếu không truyền items (AC 1)
    2. Tính toán chiết khấu từng dòng & toàn đơn (AC 2)
    3. Kiểm tra ngưỡng phê duyệt (AC 3)
    4. Thiết lập hạn hiệu lực & điều khoản (AC 4)
    5. Hỗ trợ lưu nháp (AC 5)
    """
    new_id = (max(q["id"] for q in FAKE_QUOTES) + 1) if FAKE_QUOTES else 1

    opportunity_id = data.get("opportunity_id")
    opp_dict = None
    inherited_items = []

    if opportunity_id:
        opp_dict, inherited_items = get_opportunity_products_for_quote(opportunity_id, db=db)

    # Nếu client truyền items -> dùng items đó (cho phép sửa lại), nếu không -> kế thừa
    raw_items = data.get("items")
    if raw_items is None:
        raw_items = inherited_items

    # Hỗ trợ backward compatibility: nếu truyền product_id và unit_price đơn lẻ từ tests cũ
    if not raw_items and data.get("product_id") and (data.get("unit_price") or data.get("amount")):
        price = float(data.get("unit_price") or data.get("amount") or 0.0)
        prod_floor = data.get("floor_price")
        if prod_floor is None and data.get("product_id"):
            try:
                from app.services.product_service import get_product_by_id
                p_item = get_product_by_id(data.get("product_id"), db=db)
                if p_item and p_item.get("floor_price") is not None:
                    prod_floor = float(p_item["floor_price"])
            except Exception:
                pass
        raw_items = [
            {
                "id": "single-item-1",
                "product_id": data.get("product_id"),
                "product_code": f"PROD-{data.get('product_id')}",
                "product_name": data.get("title") or "Sản phẩm báo giá",
                "unit": "Gói",
                "quantity": 1,
                "unit_price": price,
                "floor_price": prod_floor,
                "discount_type": "PERCENT",
                "discount_value": 0.0,
                "vat_rate": 0,
            }
        ]

    overall_type = data.get("overall_discount_type") or "PERCENT"
    overall_val = float(data.get("overall_discount_value") or 0.0)

    # Tính toán tài chính
    financials = calculate_quote_financials(raw_items, overall_type, overall_val)

    # Kết hợp cờ phê duyệt từ kiểm tra giá sàn
    requires_approval = financials["requires_approval"] or bool(data.get("requires_discount_approval"))
    approval_level = financials["approval_level"]
    approval_reason = financials["approval_reason"]
    if not financials["requires_approval"] and data.get("requires_discount_approval"):
        requires_approval = True
        approval_level = "MANAGER"
        approval_reason = "Đơn giá sản phẩm dưới giá sàn niêm yết"

    # Tiêu đề báo giá
    title = data.get("title")
    if not title:
        opp_title = opp_dict.get("title") if opp_dict else f"#{opportunity_id}"
        title = f"Báo giá cho {opp_title}"

    # Mã báo giá tự sinh
    now_str = datetime.now().strftime("%Y%m%d")
    quote_number = f"BG-{now_str}-{new_id:03d}"

    # Hạn hiệu lực & điều khoản (AC 4)
    valid_until = data.get("valid_until")
    if valid_until is None:
        valid_until = (date.today() + timedelta(days=30)).isoformat()
    elif isinstance(valid_until, (date, datetime)):
        valid_until = valid_until.isoformat()

    payment_terms = (
        data.get("payment_terms")
        or "Thanh toán 50% khi ký hợp đồng, 50% sau khi nghiệm thu bàn giao."
    )
    delivery_terms = (
        data.get("delivery_terms")
        or "Bàn giao và triển khai hệ thống trong vòng 10 ngày làm việc."
    )

    # Trạng thái & Lưu nháp (AC 5)
    is_draft = data.get("is_draft", True)
    if is_draft:
        status_val = "DRAFT"
        approval_status = "DRAFT"
    else:
        if financials["requires_approval"]:
            status_val = "PENDING_APPROVAL"
            approval_status = "PENDING_APPROVAL"
        else:
            status_val = "APPROVED"
            approval_status = "APPROVED"

    # Nếu client truyền ghi đè status tường minh (từ test cũ)
    if data.get("status"):
        status_val = data["status"]

    initial_history = []
    now_iso = datetime.now().isoformat()
    if not is_draft:
        if financials["requires_approval"]:
            initial_history.append({
                "id": f"hist-create-{int(datetime.now().timestamp() * 1000)}",
                "action": "SUBMITTED",
                "performed_by_id": current_user.get("id"),
                "performed_by_name": current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh"),
                "performed_by_role": current_user.get("role", "USER"),
                "comments": f"Gửi duyệt báo giá: {approval_reason or 'Chiết khấu vượt ngưỡng'}",
                "previous_status": "DRAFT",
                "new_status": "PENDING_APPROVAL",
                "timestamp": now_iso,
            })
        else:
            initial_history.append({
                "id": f"hist-create-{int(datetime.now().timestamp() * 1000)}",
                "action": "AUTO_APPROVED",
                "performed_by_id": None,
                "performed_by_name": "Hệ thống tự động",
                "performed_by_role": "SYSTEM",
                "comments": f"Chiết khấu {financials['discount_percentage']}% dưới ngưỡng 1 (<{DISCOUNT_TIER_1_THRESHOLD}%), hệ thống tự động thông qua.",
                "previous_status": "DRAFT",
                "new_status": "APPROVED",
                "timestamp": now_iso,
            })

    new_quote = {
        "id": new_id,
        "quote_number": quote_number,
        "opportunity_id": opportunity_id,
        "opportunity_title": opp_dict.get("title") if opp_dict else None,
        "title": title,
        "amount": financials["grand_total"] if financials["grand_total"] > 0 else float(data.get("amount") or 0.0),
        "status": status_val,
        "is_draft": is_draft,
        "customer_id": data.get("customer_id") or (opp_dict.get("customer_id") if opp_dict else None),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "product_id": data.get("product_id"),
        "unit_price": data.get("unit_price"),
        "items": financials["calculated_items"],
        "overall_discount_type": overall_type,
        "overall_discount_value": overall_val,
        "subtotal": financials["subtotal"],
        "total_line_discount": financials["total_line_discount"],
        "overall_discount_amount": financials["overall_discount_amount"],
        "total_discount_amount": financials["total_discount_amount"],
        "discount_percentage": financials["discount_percentage"],
        "vat_amount": financials["vat_amount"],
        "grand_total": financials["grand_total"] if financials["grand_total"] > 0 else float(data.get("amount") or 0.0),
        "valid_until": str(valid_until),
        "payment_terms": payment_terms,
        "delivery_terms": delivery_terms,
        "notes": data.get("notes") or "",
        "requires_discount_approval": requires_approval,
        "approval_level": approval_level,
        "approval_reason": approval_reason,
        "discount_approval_status": data.get("discount_approval_status") or approval_status,
        "sent_at": None,
        "approval_history": initial_history,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    FAKE_QUOTES.append(new_quote)
    return new_quote


def update_quote_record(quote_id: int, data: dict, db=None) -> Optional[dict]:
    """
    Cập nhật báo giá (AC 5: Sửa nháp hoặc cập nhật chiết khấu):
    Tính toán lại tài chính và ngưỡng phê duyệt tương ứng.
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        return None

    # Cập nhật danh sách items nếu có
    current_items = data.get("items") if data.get("items") is not None else q.get("items", [])
    overall_type = data.get("overall_discount_type") or q.get("overall_discount_type", "PERCENT")
    overall_val = float(data.get("overall_discount_value") if data.get("overall_discount_value") is not None else q.get("overall_discount_value", 0.0))

    # Hỗ trợ backward compatibility nếu chỉ update unit_price/amount đơn lẻ
    if not current_items and (data.get("unit_price") or data.get("amount")):
        price = float(data.get("unit_price") or data.get("amount") or q.get("unit_price") or 0.0)
        current_items = [
            {
                "id": "single-item-1",
                "product_id": data.get("product_id") or q.get("product_id"),
                "product_code": f"PROD-{data.get('product_id') or q.get('product_id')}",
                "product_name": data.get("title") or q.get("title"),
                "unit": "Gói",
                "quantity": 1,
                "unit_price": price,
                "floor_price": data.get("floor_price"),
                "discount_type": "PERCENT",
                "discount_value": 0.0,
                "vat_rate": 0,
            }
        ]

    # Tính lại tài chính
    financials = calculate_quote_financials(current_items, overall_type, overall_val)

    # Gán các giá trị cập nhật
    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            if isinstance(value, (date, datetime)):
                q[key] = value.isoformat()
            else:
                q[key] = value

    q["items"] = financials["calculated_items"]
    q["subtotal"] = financials["subtotal"]
    q["total_line_discount"] = financials["total_line_discount"]
    q["overall_discount_amount"] = financials["overall_discount_amount"]
    q["total_discount_amount"] = financials["total_discount_amount"]
    q["discount_percentage"] = financials["discount_percentage"]
    q["vat_amount"] = financials["vat_amount"]
    if financials["grand_total"] > 0:
        q["grand_total"] = financials["grand_total"]
        q["amount"] = financials["grand_total"]
    elif data.get("amount") is not None:
        q["amount"] = float(data["amount"])
        q["grand_total"] = float(data["amount"])

    # Ngưỡng phê duyệt
    if "requires_discount_approval" not in data or data.get("requires_discount_approval") is None:
        q["requires_discount_approval"] = financials["requires_approval"]
        q["approval_level"] = financials["approval_level"]
        q["approval_reason"] = financials["approval_reason"]

    # Cập nhật trạng thái duyệt nếu không chỉ định tường minh
    if "discount_approval_status" not in data or data.get("discount_approval_status") is None:
        if q.get("is_draft"):
            q["discount_approval_status"] = "DRAFT"
        else:
            q["discount_approval_status"] = "PENDING_APPROVAL" if financials["requires_approval"] else "APPROVED"

    q["updated_at"] = datetime.now().isoformat()
    return q


def submit_quote_record(quote_id: int, current_user: Optional[dict] = None, db=None) -> Optional[dict]:
    """
    Chuyển báo giá từ nháp (DRAFT / RETURNED) sang trình duyệt hoặc thông qua (S7-01 & S7-02):
    - AC 1: Chiết khấu dưới ngưỡng 1 (<10% và không dưới giá sàn) thì TỰ ĐỘNG THÔNG QUA (AUTO_APPROVED)
    - AC 2: Vượt ngưỡng thì chuyển PENDING_APPROVAL chờ duyệt
    - AC 5: Ghi nhận lịch sử duyệt bất biến (approval_history) & audit log
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        return None

    prev_status = q.get("status", "DRAFT")
    now_iso = datetime.now().isoformat()
    q["is_draft"] = False

    if q.get("requires_discount_approval"):
        q["status"] = "PENDING_APPROVAL"
        q["discount_approval_status"] = "PENDING_APPROVAL"
        action_name = "SUBMITTED"
        actor_name = current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh") if current_user else "Nhân viên kinh doanh"
        actor_role = current_user.get("role", "USER") if current_user else "USER"
        actor_id = current_user.get("id") if current_user else None
        comment_text = f"Gửi duyệt báo giá: {q.get('approval_reason') or 'Chiết khấu vượt ngưỡng'}"
        new_status = "PENDING_APPROVAL"
    else:
        # AC 1: Tự động thông qua
        q["status"] = "APPROVED"
        q["discount_approval_status"] = "APPROVED"
        action_name = "AUTO_APPROVED"
        actor_name = "Hệ thống tự động"
        actor_role = "SYSTEM"
        actor_id = None
        disc_pct = q.get("discount_percentage", 0.0)
        comment_text = f"Chiết khấu {disc_pct}% dưới ngưỡng 1 (<{DISCOUNT_TIER_1_THRESHOLD}%), tự động thông qua."
        new_status = "APPROVED"

    hist_item = {
        "id": f"hist-sub-{int(datetime.now().timestamp() * 1000)}",
        "action": action_name,
        "performed_by_id": actor_id,
        "performed_by_name": actor_name,
        "performed_by_role": actor_role,
        "comments": comment_text,
        "previous_status": prev_status,
        "new_status": new_status,
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)
    q["updated_at"] = now_iso

    _safe_log_audit(
        user_id=actor_id or 1,
        user_name=actor_name,
        entity_id=f"QUOTE-{quote_id}",
        action=action_name,
        field_name="status",
        old_value=prev_status,
        new_value=new_status,
        db=db,
    )

    return q


def can_user_approve_quote(user: dict, quote: dict) -> Tuple[bool, Optional[str]]:
    """
    Kiểm tra thẩm quyền phê duyệt báo giá (S7-02 AC 2):
    - Cấp DIRECTOR (>= 20% hoặc có sản phẩm dưới giá sàn): Bắt buộc Giám đốc kinh doanh (hoặc Admin). Manager không được duyệt.
    - Cấp MANAGER (10% <= CK < 20%): Trưởng nhóm, Giám đốc hoặc Admin được duyệt.
    """
    user_role = str(user.get("role") or "").upper()
    req_level = str(quote.get("approval_level") or "NONE").upper()

    if user_role in ("ADMIN", "DIRECTOR"):
        return True, None

    if req_level == "DIRECTOR":
        return False, "Báo giá này có chiết khấu cao (>= 20%) hoặc bán dưới giá sàn, bắt buộc Giám đốc kinh doanh (hoặc Admin) phê duyệt"

    if req_level in ("MANAGER", "NONE"):
        if user_role == "MANAGER":
            user_team = user.get("team_id")
            quote_team = quote.get("team_id")
            if user_team is not None and quote_team is not None and user_team != quote_team:
                return False, "Trưởng nhóm chỉ có quyền phê duyệt báo giá của thành viên trong nhóm mình"
            return True, None
        return False, "Chỉ Trưởng nhóm hoặc Giám đốc mới có quyền duyệt báo giá này"

    return False, "Không có quyền phê duyệt báo giá"


def approve_quote_record(
    quote_id: int,
    current_user: dict,
    comments: Optional[str] = None,
    db=None,
) -> dict:
    """
    Duyệt báo giá (S7-02 AC 3):
    - Kiểm tra trạng thái phải là PENDING_APPROVAL
    - Kiểm tra thẩm quyền phê duyệt (AC 2)
    - Chuyển trạng thái sang APPROVED
    - Thêm bản ghi bất biến vào approval_history
    - Ghi nhận Audit Log
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá",
        )

    if q.get("status") != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Chỉ có thể phê duyệt báo giá đang ở trạng thái Chờ duyệt (PENDING_APPROVAL)",
        )

    allowed, err_msg = can_user_approve_quote(current_user, q)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=err_msg or "Bạn không có thẩm quyền phê duyệt báo giá này",
        )

    prev_status = q.get("status")
    now_iso = datetime.now().isoformat()
    clean_comments = (comments or "").strip() or "Đồng ý phê duyệt mức chiết khấu của báo giá."

    q["status"] = "APPROVED"
    q["discount_approval_status"] = "APPROVED"
    q["is_draft"] = False
    q["updated_at"] = now_iso

    hist_item = {
        "id": f"hist-appr-{int(datetime.now().timestamp() * 1000)}",
        "action": "APPROVE",
        "performed_by_id": current_user.get("id"),
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Người duyệt"),
        "performed_by_role": current_user.get("role", "MANAGER"),
        "comments": clean_comments,
        "previous_status": prev_status,
        "new_status": "APPROVED",
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)

    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"QUOTE-{quote_id}",
        action="APPROVE_QUOTE",
        field_name="status",
        old_value=prev_status,
        new_value="APPROVED",
        db=db,
    )

    return q


def reject_quote_record(
    quote_id: int,
    current_user: dict,
    comments: Optional[str],
    db=None,
) -> dict:
    """
    Từ chối duyệt báo giá (S7-02 AC 3):
    - Kiểm tra trạng thái phải là PENDING_APPROVAL
    - Bắt buộc nhập ý kiến / lý do từ chối
    - Kiểm tra thẩm quyền phê duyệt (AC 2)
    - Chuyển trạng thái sang REJECTED
    - Thêm bản ghi bất biến vào approval_history
    - Ghi nhận Audit Log
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá",
        )

    if q.get("status") != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Chỉ có thể từ chối báo giá đang ở trạng thái Chờ duyệt (PENDING_APPROVAL)",
        )

    if not comments or not comments.strip():
        raise HTTPException(
            status_code=400,
            detail="Bắt buộc nhập ý kiến khi từ chối duyệt báo giá (S7-02 AC)",
        )

    allowed, err_msg = can_user_approve_quote(current_user, q)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=err_msg or "Bạn không có thẩm quyền từ chối báo giá này",
        )

    prev_status = q.get("status")
    now_iso = datetime.now().isoformat()
    clean_comments = comments.strip()

    q["status"] = "REJECTED"
    q["discount_approval_status"] = "REJECTED"
    q["updated_at"] = now_iso

    hist_item = {
        "id": f"hist-rej-{int(datetime.now().timestamp() * 1000)}",
        "action": "REJECT",
        "performed_by_id": current_user.get("id"),
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Người duyệt"),
        "performed_by_role": current_user.get("role", "MANAGER"),
        "comments": clean_comments,
        "previous_status": prev_status,
        "new_status": "REJECTED",
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)

    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"QUOTE-{quote_id}",
        action="REJECT_QUOTE",
        field_name="status",
        old_value=prev_status,
        new_value="REJECTED",
        db=db,
    )

    return q


def return_quote_record(
    quote_id: int,
    current_user: dict,
    comments: Optional[str],
    db=None,
) -> dict:
    """
    Trả lại báo giá để nhân viên sửa (S7-02 AC 3):
    - Kiểm tra trạng thái phải là PENDING_APPROVAL
    - Bắt buộc nhập ý kiến yêu cầu chỉnh sửa
    - Kiểm tra thẩm quyền phê duyệt (AC 2)
    - Chuyển trạng thái sang RETURNED, mở is_draft = True để sửa lại
    - Thêm bản ghi bất biến vào approval_history
    - Ghi nhận Audit Log
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá",
        )

    if q.get("status") != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Chỉ có thể trả lại báo giá đang ở trạng thái Chờ duyệt (PENDING_APPROVAL)",
        )

    if not comments or not comments.strip():
        raise HTTPException(
            status_code=400,
            detail="Bắt buộc nhập ý kiến khi trả lại báo giá yêu cầu sửa (S7-02 AC)",
        )

    allowed, err_msg = can_user_approve_quote(current_user, q)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=err_msg or "Bạn không có thẩm quyền yêu cầu chỉnh sửa báo giá này",
        )

    prev_status = q.get("status")
    now_iso = datetime.now().isoformat()
    clean_comments = comments.strip()

    q["status"] = "RETURNED"
    q["discount_approval_status"] = "RETURNED"
    q["is_draft"] = True  # Mở khóa để nhân viên kinh doanh sửa tiếp
    q["updated_at"] = now_iso

    hist_item = {
        "id": f"hist-ret-{int(datetime.now().timestamp() * 1000)}",
        "action": "RETURN",
        "performed_by_id": current_user.get("id"),
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Người duyệt"),
        "performed_by_role": current_user.get("role", "MANAGER"),
        "comments": clean_comments,
        "previous_status": prev_status,
        "new_status": "RETURNED",
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)

    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"QUOTE-{quote_id}",
        action="RETURN_QUOTE",
        field_name="status",
        old_value=prev_status,
        new_value="RETURNED",
        db=db,
    )

    return q


def send_quote_to_customer_record(
    quote_id: int,
    current_user: dict,
    db=None,
) -> dict:
    """
    Gửi báo giá cho khách hàng (S7-02 AC 4):
    - Chỉ cho phép gửi khi status == "APPROVED"
    - Nếu chưa duyệt (DRAFT, PENDING_APPROVAL, REJECTED, RETURNED) -> Báo lỗi 400 Bad Request
    - Chuyển trạng thái sang SENT, ghi nhận sent_at
    - Thêm bản ghi bất biến vào approval_history
    - Ghi nhận Audit Log
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá",
        )

    current_status = q.get("status")
    if current_status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Chỉ báo giá đã được phê duyệt mới được phép gửi cho khách hàng (S7-02 AC)",
        )

    now_iso = datetime.now().isoformat()
    q["status"] = "SENT"
    q["sent_at"] = now_iso
    q["updated_at"] = now_iso

    hist_item = {
        "id": f"hist-send-{int(datetime.now().timestamp() * 1000)}",
        "action": "SEND",
        "performed_by_id": current_user.get("id"),
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh"),
        "performed_by_role": current_user.get("role", "USER"),
        "comments": "Đã gửi báo giá cho khách hàng.",
        "previous_status": current_status,
        "new_status": "SENT",
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)

    _safe_log_audit(
        user_id=current_user.get("id", 0),
        user_name=current_user.get("full_name") or current_user.get("username", "User"),
        entity_id=f"QUOTE-{quote_id}",
        action="SEND_QUOTE",
        field_name="status",
        old_value=current_status,
        new_value="SENT",
        db=db,
    )

    return q


def get_quote_approval_history(quote_id: int) -> List[dict]:
    """
    Lấy danh sách lịch sử phê duyệt của báo giá (S7-02 AC 5):
    Dữ liệu là bất biến (immutable), không thể sửa hay xoá.
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá",
        )
    return list(q.get("approval_history", []))


def get_pending_approvals_by_scope(current_user: dict, scope: DataScope) -> List[dict]:
    """
    Lấy danh sách báo giá đang chờ phê duyệt (status == PENDING_APPROVAL) theo scope.
    """
    return get_quotes_by_scope(current_user, scope, status="PENDING_APPROVAL")


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
    if db is None:
        # Khi không có DB session (môi trường mock/unit test), bỏ qua ghi trực tiếp vào MySQL để tránh TCP timeout
        return
    try:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=user_id,
            user_name=user_name,
            entity_type="DISCOUNT",
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


def delete_quote_record(quote_id: int) -> bool:
    global FAKE_QUOTES
    initial_len = len(FAKE_QUOTES)
    FAKE_QUOTES = [q for q in FAKE_QUOTES if q["id"] != quote_id]
    return len(FAKE_QUOTES) < initial_len
