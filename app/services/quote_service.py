"""
Quote service with data scope filtering (MY/MY_TEAM/TEAM/ALL),
real-time financial calculations, line items, opportunity inheritance,
and approval threshold enforcement (S7-01).
"""

import copy
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from app.core.dependencies import DataScope

# Ngưỡng phê duyệt chiết khấu (S7-01 AC 3)
DISCOUNT_TIER_1_THRESHOLD = 10.0  # >= 10%: Trưởng nhóm (MANAGER) duyệt
DISCOUNT_TIER_2_THRESHOLD = 20.0  # >= 20% hoặc dưới giá sàn: Giám đốc (DIRECTOR) duyệt

INITIAL_QUOTES = [
    {
        "id": 1,
        "quote_number": "BG-20261015-001",
        "opportunity_id": 1,
        "opportunity_title": "Hợp đồng phần mềm Admin",
        "title": "Báo giá phần mềm Admin",
        "amount": 55000000.0,
        "status": "SENT",
        "is_draft": False,
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
        "items": [],
        "overall_discount_type": "PERCENT",
        "overall_discount_value": 0.0,
        "subtotal": 55000000.0,
        "total_line_discount": 0.0,
        "overall_discount_amount": 0.0,
        "total_discount_amount": 0.0,
        "discount_percentage": 0.0,
        "vat_amount": 0.0,
        "grand_total": 55000000.0,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "payment_terms": "Thanh toán 50% khi ký hợp đồng, 50% sau nghiệm thu bàn giao.",
        "delivery_terms": "Bàn giao và triển khai hệ thống trong vòng 10 ngày làm việc.",
        "notes": "",
        "requires_discount_approval": False,
        "approval_level": "NONE",
        "approval_reason": None,
        "discount_approval_status": "APPROVED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 2,
        "quote_number": "BG-20261015-002",
        "opportunity_id": 2,
        "opportunity_title": "Hợp đồng dịch vụ Manager",
        "title": "Báo giá dịch vụ Manager",
        "amount": 32000000.0,
        "status": "ACCEPTED",
        "is_draft": False,
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
        "items": [],
        "overall_discount_type": "PERCENT",
        "overall_discount_value": 0.0,
        "subtotal": 32000000.0,
        "total_line_discount": 0.0,
        "overall_discount_amount": 0.0,
        "total_discount_amount": 0.0,
        "discount_percentage": 0.0,
        "vat_amount": 0.0,
        "grand_total": 32000000.0,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "payment_terms": "Thanh toán 100% trước khi kích hoạt dịch vụ.",
        "delivery_terms": "Kích hoạt dịch vụ ngay trong ngày làm việc.",
        "notes": "",
        "requires_discount_approval": False,
        "approval_level": "NONE",
        "approval_reason": None,
        "discount_approval_status": "APPROVED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 3,
        "quote_number": "BG-20261015-003",
        "opportunity_id": 3,
        "opportunity_title": "Cung cấp thiết bị User1",
        "title": "Báo giá thiết bị User1",
        "amount": 16000000.0,
        "status": "DRAFT",
        "is_draft": True,
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
        "items": [],
        "overall_discount_type": "PERCENT",
        "overall_discount_value": 0.0,
        "subtotal": 16000000.0,
        "total_line_discount": 0.0,
        "overall_discount_amount": 0.0,
        "total_discount_amount": 0.0,
        "discount_percentage": 0.0,
        "vat_amount": 0.0,
        "grand_total": 16000000.0,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "payment_terms": "Thanh toán 50% khi ký, 50% sau nghiệm thu.",
        "delivery_terms": "Giao hàng trong vòng 7 ngày làm việc.",
        "notes": "Đang soạn nháp điều khoản chiết khấu thêm",
        "requires_discount_approval": False,
        "approval_level": "NONE",
        "approval_reason": None,
        "discount_approval_status": "DRAFT",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 4,
        "quote_number": "BG-20261015-004",
        "opportunity_id": 4,
        "opportunity_title": "Bảo trì hệ thống User2",
        "title": "Báo giá bảo trì User2",
        "amount": 22000000.0,
        "status": "REJECTED",
        "is_draft": False,
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
        "items": [],
        "overall_discount_type": "PERCENT",
        "overall_discount_value": 0.0,
        "subtotal": 22000000.0,
        "total_line_discount": 0.0,
        "overall_discount_amount": 0.0,
        "total_discount_amount": 0.0,
        "discount_percentage": 0.0,
        "vat_amount": 0.0,
        "grand_total": 22000000.0,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "payment_terms": "Thanh toán định kỳ hàng quý.",
        "delivery_terms": "Hỗ trợ kỹ thuật 24/7.",
        "notes": "",
        "requires_discount_approval": False,
        "approval_level": "NONE",
        "approval_reason": None,
        "discount_approval_status": "REJECTED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
]

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
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
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


def submit_quote_record(quote_id: int) -> Optional[dict]:
    """
    Chuyển báo giá từ nháp (DRAFT) sang trình duyệt hoặc thông qua (AC 5)
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        return None

    q["is_draft"] = False
    if q.get("requires_discount_approval"):
        q["status"] = "PENDING_APPROVAL"
        q["discount_approval_status"] = "PENDING_APPROVAL"
    else:
        q["status"] = "APPROVED"
        q["discount_approval_status"] = "APPROVED"

    q["updated_at"] = datetime.now().isoformat()
    return q


def delete_quote_record(quote_id: int) -> bool:
    global FAKE_QUOTES
    initial_len = len(FAKE_QUOTES)
    FAKE_QUOTES = [q for q in FAKE_QUOTES if q["id"] != quote_id]
    return len(FAKE_QUOTES) < initial_len
