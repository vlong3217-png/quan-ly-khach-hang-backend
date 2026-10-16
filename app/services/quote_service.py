"""
Quote service with data scope filtering (MY/MY_TEAM/TEAM/ALL),
real-time financial calculations, line items, opportunity inheritance,
and approval threshold enforcement (S7-01 & S7-02).
"""

import copy
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from app.core.dependencies import DataScope

# Ngưỡng phê duyệt chiết khấu (S7-01 & S7-02)
DISCOUNT_TIER_1_THRESHOLD = 10.0  # >= 10%: Trưởng nhóm (MANAGER) duyệt
DISCOUNT_TIER_2_THRESHOLD = 20.0  # >= 20% hoặc dưới giá sàn: Giám đốc (DIRECTOR) duyệt

INITIAL_QUOTES = [
    {
        "id": 1,
        "quote_number": "BG-20261015-001",
        "version": 1,
        "is_active_version": True,
        "parent_quote_id": None,
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
        "sent_at": datetime.now().isoformat(),
        "approval_history": [
            {
                "id": "hist-1-1",
                "action": "AUTO_APPROVED",
                "performed_by_id": None,
                "performed_by_name": "Hệ thống tự động",
                "performed_by_role": "SYSTEM",
                "comments": "Chiết khấu 0.0% dưới ngưỡng 1 (<10%), hệ thống tự động thông qua.",
                "previous_status": "DRAFT",
                "new_status": "APPROVED",
                "timestamp": datetime.now().isoformat(),
            },
            {
                "id": "hist-1-2",
                "action": "SEND",
                "performed_by_id": 1,
                "performed_by_name": "Admin",
                "performed_by_role": "ADMIN",
                "comments": "Đã gửi báo giá cho khách hàng.",
                "previous_status": "APPROVED",
                "new_status": "SENT",
                "timestamp": datetime.now().isoformat(),
            },
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 2,
        "quote_number": "BG-20261015-002",
        "version": 1,
        "is_active_version": True,
        "parent_quote_id": None,
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
        "sent_at": datetime.now().isoformat(),
        "approval_history": [
            {
                "id": "hist-2-1",
                "action": "AUTO_APPROVED",
                "performed_by_id": None,
                "performed_by_name": "Hệ thống tự động",
                "performed_by_role": "SYSTEM",
                "comments": "Chiết khấu 0.0% dưới ngưỡng 1 (<10%), hệ thống tự động thông qua.",
                "previous_status": "DRAFT",
                "new_status": "APPROVED",
                "timestamp": datetime.now().isoformat(),
            }
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 3,
        "quote_number": "BG-20261015-003",
        "version": 1,
        "is_active_version": True,
        "parent_quote_id": None,
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
        "sent_at": None,
        "approval_history": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
    {
        "id": 4,
        "quote_number": "BG-20261015-004",
        "version": 1,
        "is_active_version": True,
        "parent_quote_id": None,
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
        "sent_at": None,
        "approval_history": [
            {
                "id": "hist-4-1",
                "action": "REJECT",
                "performed_by_id": 2,
                "performed_by_name": "Manager",
                "performed_by_role": "MANAGER",
                "comments": "Chiết khấu quá cao, ảnh hưởng biên lợi nhuận của quý.",
                "previous_status": "PENDING_APPROVAL",
                "new_status": "REJECTED",
                "timestamp": datetime.now().isoformat(),
            }
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    },
]

FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def reset_fake_quotes() -> None:
    global FAKE_QUOTES
    FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def _record_opportunity_timeline_activity(
    opportunity_id: int,
    customer_id: Optional[int],
    owner_id: int,
    title: str,
    activity_type: str,
    description: str,
    db=None,
):
    """
    Ghi nhận một hoạt động (Activity) vào dòng thời gian của Cơ hội (S7-06 AC 1 & AC 3):
    - Cập nhật thời điểm tương tác gần nhất last_activity_at trên Cơ hội
    - Tạo bản ghi Activity để nhân viên kinh doanh theo dõi ngay trên dòng thời gian
    """
    now_iso = datetime.now().isoformat()
    # 1. Ghi vào Activity service (In-memory mock)
    try:
        from app.services import activity_service
        actor = {"id": owner_id, "role": "SYSTEM", "full_name": "Hệ thống Báo giá"}
        activity_service.create_activity_record({
            "title": title,
            "type": activity_type,
            "description": description,
            "customer_id": customer_id,
            "opportunity_id": opportunity_id,
        }, current_user=actor)
    except Exception:
        pass

    # 2. Cập nhật last_activity_at trên Cơ hội (In-memory mock)
    try:
        from app.services import opportunity_service
        for opp in (getattr(opportunity_service, "FAKE_OPPORTUNITIES", []) + getattr(opportunity_service, "TEST_SAMPLE_OPPORTUNITIES", [])):
            if opp.get("id") == opportunity_id:
                opp["last_activity_at"] = now_iso
                break
    except Exception:
        pass

    # 3. Nếu có DB session
    if db:
        try:
            from app.models.opportunity import OpportunityModel
            from app.models.activity import Activity as ActivityModel
            db_opp = db.query(OpportunityModel).filter(OpportunityModel.id == opportunity_id).first()
            if db_opp:
                db_opp.last_activity_at = datetime.utcnow()
            db_act = ActivityModel(
                title=title,
                type=activity_type,
                description=description,
                customer_id=customer_id,
                opportunity_id=opportunity_id,
                owner_id=owner_id,
                created_at=datetime.utcnow(),
            )
            db.add(db_act)
            db.commit()
        except Exception:
            pass


def check_and_expire_quotes(db=None) -> List[dict]:
    """
    Quá hạn hiệu lực mà không phản hồi thì báo giá tự chuyển sang Hết hiệu lực (S7-06 AC 4):
    - Kiểm tra valid_until < date.today()
    - Trạng thái chưa hoàn tất (SENT, VIEWED, APPROVED, DRAFT, PENDING_APPROVAL, RETURNED)
    - Tự động chuyển sang EXPIRED
    - Ghi nhận vào approval_history (AUTO_EXPIRED)
    - Tự động ghi Activity vào dòng thời gian cơ hội liên kết
    """
    expired_quotes = []
    today_str = str(date.today())
    now_iso = datetime.now().isoformat()

    for q in FAKE_QUOTES:
        valid_until = q.get("valid_until")
        if not valid_until:
            continue
        v_date_str = str(valid_until)[:10]
        # Nếu đã quá hạn hiệu lực và chưa được chốt (ACCEPTED, DECLINED, REJECTED, EXPIRED, CONVERTED)
        if v_date_str < today_str and q.get("status") in ("SENT", "VIEWED", "APPROVED", "DRAFT", "PENDING_APPROVAL", "RETURNED"):
            prev_status = q.get("status")
            q["status"] = "EXPIRED"
            q["updated_at"] = now_iso

            hist_item = {
                "id": f"hist-exp-{int(datetime.now().timestamp() * 1000)}-{q['id']}",
                "action": "AUTO_EXPIRED",
                "performed_by_id": None,
                "performed_by_name": "Hệ thống tự động",
                "performed_by_role": "SYSTEM",
                "comments": f"Báo giá tự động chuyển sang Hết hiệu lực do quá hạn hiệu lực ({v_date_str}) mà chưa có phản hồi từ khách hàng (S7-06 AC 4).",
                "previous_status": prev_status,
                "new_status": "EXPIRED",
                "timestamp": now_iso,
            }
            q.setdefault("approval_history", []).append(hist_item)

            if q.get("opportunity_id"):
                _record_opportunity_timeline_activity(
                    opportunity_id=q["opportunity_id"],
                    customer_id=q.get("customer_id"),
                    owner_id=q.get("owner_id", 1),
                    title=f"Báo giá {q.get('quote_number')} đã hết hiệu lực",
                    activity_type="NOTE",
                    description=f"Báo giá {q.get('quote_number')} đã quá hạn hiệu lực ({v_date_str}) mà chưa nhận được phản hồi từ khách hàng. Trạng thái đã chuyển sang Hết hiệu lực (EXPIRED).",
                    db=db,
                )
            expired_quotes.append(q)

    return expired_quotes


def get_raw_quote_by_id(quote_id: int) -> Optional[dict]:
    check_and_expire_quotes()
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
    check_and_expire_quotes()
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
        "version": int(data.get("version") or 1),
        "is_active_version": bool(data.get("is_active_version", True) if data.get("is_active_version") is not None else True),
        "parent_quote_id": data.get("parent_quote_id"),
        "sent_at": None,
        "approval_history": initial_history,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    FAKE_QUOTES.append(new_quote)
    return new_quote


def update_quote_record(quote_id: int, data: dict, current_user: Optional[dict] = None, db=None) -> Optional[dict]:
    """
    Cập nhật báo giá (AC 5: Sửa nháp hoặc cập nhật chiết khấu):
    Tính toán lại tài chính và ngưỡng phê duyệt tương ứng.
    S7-03 AC 1: Không sửa trực tiếp báo giá đã gửi (SENT), yêu cầu tạo phiên bản mới.
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        return None

    # S7-03 AC 1: Mỗi lần sửa sau khi đã gửi tạo phiên bản mới, phiên bản cũ được giữ nguyên
    # Quản trị viên (ADMIN) hoặc cờ force=True được phép cập nhật trực tiếp cho mục đích quản trị hệ thống
    user_role = current_user.get("role") if current_user else None
    if q.get("status") in ("SENT", "ACCEPTED", "DECLINED") and not data.get("force", False) and user_role != "ADMIN":
        raise HTTPException(
            status_code=400,
            detail="Báo giá đã gửi cho khách hàng không thể chỉnh sửa trực tiếp. Vui lòng tạo phiên bản mới (S7-03 AC 1).",
        )

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


def create_new_quote_version(
    quote_id: int,
    data: Optional[dict] = None,
    current_user: Optional[dict] = None,
    reason: Optional[str] = None,
    db=None,
) -> dict:
    """
    Tạo phiên bản sửa đổi mới từ báo giá hiện có (S7-03 AC 1 & AC 3):
    - Kế thừa: quote_number, parent_quote_id = quote_id
    - version = max(version hiện có cùng quote_number) + 1
    - Sao chép danh sách dòng sản phẩm độc lập (gán ID mới)
    - status = "DRAFT", is_draft = True
    - Đặt is_active_version = True cho bản mới, tắt is_active_version = False cho các bản cũ
    - Bản cũ được giữ nguyên trạng thái, lịch sử và nội dung
    """
    parent_quote = get_raw_quote_by_id(quote_id)
    if parent_quote is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá để tạo phiên bản mới",
        )

    quote_number = parent_quote.get("quote_number")
    related_versions = [q for q in FAKE_QUOTES if q.get("quote_number") == quote_number]
    max_version = max((q.get("version") or 1) for q in related_versions) if related_versions else 1
    next_version = max_version + 1

    payload_data = data or {}
    set_active = payload_data.get("set_active", True)
    if set_active:
        for old_q in related_versions:
            old_q["is_active_version"] = False

    new_id = (max(q["id"] for q in FAKE_QUOTES) + 1) if FAKE_QUOTES else 1

    # Dòng sản phẩm
    if payload_data.get("items") is not None:
        raw_items = payload_data["items"]
    else:
        raw_items = []
        for idx, it in enumerate(parent_quote.get("items", [])):
            cloned = copy.deepcopy(it)
            cloned["id"] = f"q-it-{new_id}-{idx + 1}"
            raw_items.append(cloned)

    overall_type = payload_data.get("overall_discount_type") or parent_quote.get("overall_discount_type", "PERCENT")
    overall_val = float(
        payload_data.get("overall_discount_value")
        if payload_data.get("overall_discount_value") is not None
        else parent_quote.get("overall_discount_value", 0.0)
    )

    financials = calculate_quote_financials(raw_items, overall_type, overall_val)

    now_iso = datetime.now().isoformat()
    valid_until = payload_data.get("valid_until") or parent_quote.get("valid_until")
    if isinstance(valid_until, (date, datetime)):
        valid_until = valid_until.isoformat()

    new_quote = {
        "id": new_id,
        "quote_number": quote_number,
        "version": next_version,
        "is_active_version": set_active,
        "parent_quote_id": parent_quote["id"],
        "opportunity_id": parent_quote.get("opportunity_id"),
        "opportunity_title": parent_quote.get("opportunity_title"),
        "title": payload_data.get("title") or parent_quote.get("title"),
        "amount": financials["grand_total"],
        "status": "DRAFT",
        "is_draft": True,
        "customer_id": parent_quote.get("customer_id"),
        "owner_id": current_user["id"] if current_user else parent_quote["owner_id"],
        "team_id": parent_quote.get("team_id"),
        "product_id": parent_quote.get("product_id"),
        "unit_price": parent_quote.get("unit_price"),
        "items": financials["calculated_items"],
        "overall_discount_type": overall_type,
        "overall_discount_value": overall_val,
        "subtotal": financials["subtotal"],
        "total_line_discount": financials["total_line_discount"],
        "overall_discount_amount": financials["overall_discount_amount"],
        "total_discount_amount": financials["total_discount_amount"],
        "discount_percentage": financials["discount_percentage"],
        "vat_amount": financials["vat_amount"],
        "grand_total": financials["grand_total"],
        "valid_until": str(valid_until) if valid_until else None,
        "payment_terms": payload_data.get("payment_terms") or parent_quote.get("payment_terms"),
        "delivery_terms": payload_data.get("delivery_terms") or parent_quote.get("delivery_terms"),
        "notes": payload_data.get("notes") or parent_quote.get("notes") or "",
        "requires_discount_approval": financials["requires_approval"],
        "approval_level": financials["approval_level"],
        "approval_reason": financials["approval_reason"],
        "discount_approval_status": "DRAFT",
        "sent_at": None,
        "approval_history": [
            {
                "id": f"hist-ver-{int(datetime.now().timestamp() * 1000)}",
                "action": "SUBMITTED",
                "performed_by_id": current_user.get("id") if current_user else None,
                "performed_by_name": current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh") if current_user else "Nhân viên kinh doanh",
                "performed_by_role": current_user.get("role", "USER") if current_user else "USER",
                "comments": f"Khởi tạo phiên bản sửa đổi mới v{next_version} từ phiên bản v{parent_quote.get('version', 1)}: {reason}" if reason else f"Khởi tạo phiên bản sửa đổi mới v{next_version} từ phiên bản v{parent_quote.get('version', 1)}. Bản cũ được lưu giữ nguyên trạng.",
                "previous_status": None,
                "new_status": "DRAFT",
                "timestamp": now_iso,
            }
        ],
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    FAKE_QUOTES.append(new_quote)

    _safe_log_audit(
        user_id=current_user.get("id", 0) if current_user else 1,
        user_name=current_user.get("full_name") or current_user.get("username", "User") if current_user else "System",
        entity_id=f"QUOTE-{new_id}",
        action="CREATE_VERSION",
        field_name="version",
        old_value=str(parent_quote.get("version", 1)),
        new_value=str(next_version),
        db=db,
    )

    return new_quote


def set_active_quote_version(
    quote_id: int,
    current_user: Optional[dict] = None,
    db=None,
) -> dict:
    """
    Đặt một phiên bản làm phiên bản hiệu lực duy nhất của báo giá (S7-03 AC 3):
    - Đặt is_active_version = True cho bản ghi quote_id
    - Tự động tắt is_active_version = False cho tất cả các phiên bản khác cùng quote_number
    """
    target = get_raw_quote_by_id(quote_id)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá để đặt làm phiên bản hiệu lực",
        )

    quote_number = target.get("quote_number")
    for q in FAKE_QUOTES:
        if q.get("quote_number") == quote_number:
            q["is_active_version"] = (q["id"] == quote_id)

    target["is_active_version"] = True
    now_iso = datetime.now().isoformat()
    target["updated_at"] = now_iso

    hist_item = {
        "id": f"hist-act-{int(datetime.now().timestamp() * 1000)}",
        "action": "SET_ACTIVE",
        "performed_by_id": current_user.get("id") if current_user else None,
        "performed_by_name": current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh") if current_user else "Nhân viên kinh doanh",
        "performed_by_role": current_user.get("role", "USER") if current_user else "USER",
        "comments": f"Đặt phiên bản v{target.get('version', 1)} làm phiên bản hiệu lực duy nhất của báo giá {quote_number}.",
        "previous_status": target.get("status"),
        "new_status": target.get("status"),
        "timestamp": now_iso,
    }
    target.setdefault("approval_history", []).append(hist_item)

    _safe_log_audit(
        user_id=current_user.get("id", 0) if current_user else 1,
        user_name=current_user.get("full_name") or current_user.get("username", "User") if current_user else "System",
        entity_id=f"QUOTE-{quote_id}",
        action="SET_ACTIVE_VERSION",
        field_name="is_active_version",
        old_value="False",
        new_value="True",
        db=db,
    )

    return target


def get_all_quote_versions(quote_id_or_number: Any) -> Tuple[str, List[dict], Optional[int]]:
    """
    Lấy danh sách tất cả các phiên bản của báo giá (S7-03 AC 3):
    - Trả về danh sách sắp xếp theo version giảm dần (v3 -> v2 -> v1)
    - Kèm mã báo giá và ID phiên bản đang hiệu lực
    """
    quote_num = None
    if isinstance(quote_id_or_number, int) or (isinstance(quote_id_or_number, str) and quote_id_or_number.isdigit()):
        q_item = get_raw_quote_by_id(int(quote_id_or_number))
        if q_item is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy báo giá",
            )
        quote_num = q_item.get("quote_number")
    else:
        quote_num = str(quote_id_or_number)

    versions = [q for q in FAKE_QUOTES if q.get("quote_number") == quote_num]
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy phiên bản nào cho số báo giá '{quote_num}'",
        )

    # Sắp xếp version giảm dần
    versions.sort(key=lambda x: (x.get("version") or 1), reverse=True)
    active_id = None
    for v in versions:
        if v.get("is_active_version"):
            active_id = v["id"]
            break

    return {
        "quote_number": quote_num,
        "total_versions": len(versions),
        "active_version_id": active_id,
        "versions": versions,
    }


def compare_quote_versions(version_a_id: int, version_b_id: int) -> dict:
    """
    So sánh cạnh nhau hai phiên bản của báo giá (S7-03 AC 2):
    - Tài chính: delta_subtotal, delta_discount_amount, delta_discount_percentage, delta_vat, delta_grand_total
    - Dòng sản phẩm: ADDED, REMOVED, MODIFIED, UNCHANGED
    - Điều khoản: valid_until, payment_terms, delivery_terms, notes
    """
    quote_a = get_raw_quote_by_id(version_a_id)
    quote_b = get_raw_quote_by_id(version_b_id)

    if not quote_a or not quote_b:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy phiên bản báo giá để so sánh",
        )

    # 1. So sánh tài chính
    financials_diff = {
        "subtotal_a": quote_a.get("subtotal", 0.0),
        "subtotal_b": quote_b.get("subtotal", 0.0),
        "delta_subtotal": round(quote_b.get("subtotal", 0.0) - quote_a.get("subtotal", 0.0), 2),
        "discount_amount_a": quote_a.get("total_discount_amount", 0.0),
        "discount_amount_b": quote_b.get("total_discount_amount", 0.0),
        "delta_discount_amount": round(quote_b.get("total_discount_amount", 0.0) - quote_a.get("total_discount_amount", 0.0), 2),
        "discount_percentage_a": quote_a.get("discount_percentage", 0.0),
        "discount_percentage_b": quote_b.get("discount_percentage", 0.0),
        "delta_discount_percentage": round(quote_b.get("discount_percentage", 0.0) - quote_a.get("discount_percentage", 0.0), 1),
        "vat_amount_a": quote_a.get("vat_amount", 0.0),
        "vat_amount_b": quote_b.get("vat_amount", 0.0),
        "delta_vat_amount": round(quote_b.get("vat_amount", 0.0) - quote_a.get("vat_amount", 0.0), 2),
        "grand_total_a": quote_a.get("grand_total", 0.0),
        "grand_total_b": quote_b.get("grand_total", 0.0),
        "delta_grand_total": round(quote_b.get("grand_total", 0.0) - quote_a.get("grand_total", 0.0), 2),
    }

    # 2. So sánh từng dòng sản phẩm (Row-by-row Item Matching)
    items_a = quote_a.get("items", [])
    items_b = quote_b.get("items", [])

    def _get_key(it):
        return (it.get("product_code") or str(it.get("product_id") or "") or it.get("product_name", "")).strip().lower()

    map_a = {}
    for it in items_a:
        key = _get_key(it)
        map_a[key] = it

    map_b = {}
    for it in items_b:
        key = _get_key(it)
        map_b[key] = it

    all_keys = list(dict.fromkeys(list(map_a.keys()) + list(map_b.keys())))
    items_diff = []

    for k in all_keys:
        it_a = map_a.get(k)
        it_b = map_b.get(k)

        if it_a and not it_b:
            p_name = it_a.get("product_name", "")
            p_code = it_a.get("product_code")
            unit = it_a.get("unit")
            items_diff.append({
                "key": k,
                "product_code": p_code,
                "product_name": p_name,
                "unit": unit,
                "status": "REMOVED",
                "item_a": it_a,
                "item_b": None,
                "qty_diff": -int(it_a.get("quantity") or 1),
                "price_diff": -float(it_a.get("unit_price") or 0.0),
                "discount_diff": -float(it_a.get("line_discount_amount") or 0.0),
                "total_diff": -float(it_a.get("line_total") or 0.0),
            })
        elif not it_a and it_b:
            p_name = it_b.get("product_name", "")
            p_code = it_b.get("product_code")
            unit = it_b.get("unit")
            items_diff.append({
                "key": k,
                "product_code": p_code,
                "product_name": p_name,
                "unit": unit,
                "status": "ADDED",
                "item_a": None,
                "item_b": it_b,
                "qty_diff": int(it_b.get("quantity") or 1),
                "price_diff": float(it_b.get("unit_price") or 0.0),
                "discount_diff": float(it_b.get("line_discount_amount") or 0.0),
                "total_diff": float(it_b.get("line_total") or 0.0),
            })
        else:
            p_name = it_b.get("product_name", it_a.get("product_name", ""))
            p_code = it_b.get("product_code", it_a.get("product_code"))
            unit = it_b.get("unit", it_a.get("unit"))

            qty_a = int(it_a.get("quantity") or 1)
            qty_b = int(it_b.get("quantity") or 1)
            price_a = float(it_a.get("unit_price") or 0.0)
            price_b = float(it_b.get("unit_price") or 0.0)
            disc_val_a = float(it_a.get("discount_value") or 0.0)
            disc_val_b = float(it_b.get("discount_value") or 0.0)
            disc_type_a = str(it_a.get("discount_type") or "PERCENT").upper()
            disc_type_b = str(it_b.get("discount_type") or "PERCENT").upper()
            line_total_a = float(it_a.get("line_total") or 0.0)
            line_total_b = float(it_b.get("line_total") or 0.0)
            line_disc_a = float(it_a.get("line_discount_amount") or 0.0)
            line_disc_b = float(it_b.get("line_discount_amount") or 0.0)

            is_modified = (
                qty_a != qty_b
                or price_a != price_b
                or disc_val_a != disc_val_b
                or disc_type_a != disc_type_b
            )

            items_diff.append({
                "key": k,
                "product_code": p_code,
                "product_name": p_name,
                "unit": unit,
                "status": "MODIFIED" if is_modified else "UNCHANGED",
                "item_a": it_a,
                "item_b": it_b,
                "qty_diff": qty_b - qty_a,
                "price_diff": round(price_b - price_a, 2),
                "discount_diff": round(line_disc_b - line_disc_a, 2),
                "total_diff": round(line_total_b - line_total_a, 2),
            })

    # 3. So sánh điều khoản & thời hạn
    terms_diff = {
        "valid_until": {
            "value_a": str(quote_a.get("valid_until") or ""),
            "value_b": str(quote_b.get("valid_until") or ""),
            "has_changed": str(quote_a.get("valid_until") or "") != str(quote_b.get("valid_until") or ""),
        },
        "payment_terms": {
            "value_a": str(quote_a.get("payment_terms") or ""),
            "value_b": str(quote_b.get("payment_terms") or ""),
            "has_changed": str(quote_a.get("payment_terms") or "") != str(quote_b.get("payment_terms") or ""),
        },
        "delivery_terms": {
            "value_a": str(quote_a.get("delivery_terms") or ""),
            "value_b": str(quote_b.get("delivery_terms") or ""),
            "has_changed": str(quote_a.get("delivery_terms") or "") != str(quote_b.get("delivery_terms") or ""),
        },
        "notes": {
            "value_a": str(quote_a.get("notes") or ""),
            "value_b": str(quote_b.get("notes") or ""),
            "has_changed": str(quote_a.get("notes") or "") != str(quote_b.get("notes") or ""),
        },
    }

    return {
        "quote_number": quote_b.get("quote_number") or quote_a.get("quote_number"),
        "version_a_id": quote_a["id"],
        "version_b_id": quote_b["id"],
        "quote_a": quote_a,
        "quote_b": quote_b,
        "financials": financials_diff,
        "items": items_diff,
        "terms": terms_diff,
    }


# ============================================================================
# S7-06: Online Quote Link Sharing, Public View & Customer Response
# ============================================================================

def send_quote_link_to_customer(
    quote_id: int,
    recipient_email: Optional[str] = None,
    email_subject: Optional[str] = None,
    message: Optional[str] = None,
    current_user: Optional[dict] = None,
    db=None,
) -> dict:
    """
    Gửi email kèm liên kết xem báo giá, liên kết chỉ dùng cho đúng báo giá đó (S7-06 AC 1):
    - Sinh mã bảo mật share_token ngẫu nhiên, độc nhất
    - Trạng thái báo giá chuyển sang SENT
    - Lưu recipient_email, share_token, share_link, sent_at
    - Ghi nhận lịch sử duyệt (SEND_LINK)
    - Tự động ghi nhận Activity loại EMAIL vào dòng thời gian cơ hội liên kết
    """
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy báo giá để gửi liên kết",
        )

    # Chỉ cho phép gửi khi báo giá đã duyệt hoặc đang gửi lại
    if q.get("status") in ("DRAFT", "PENDING_APPROVAL", "RETURNED", "REJECTED"):
        raise HTTPException(
            status_code=400,
            detail="Chỉ báo giá đã được phê duyệt mới được phép gửi cho khách hàng (S7-02 & S7-06 AC 1)",
        )

    # Kiểm tra quá hạn
    today_str = str(date.today())
    v_date = str(q.get("valid_until", ""))[:10]
    if q.get("status") == "EXPIRED" or (v_date and v_date < today_str):
        q["status"] = "EXPIRED"
        raise HTTPException(
            status_code=400,
            detail="Báo giá này đã hết hạn hiệu lực, không thể gửi cho khách hàng (S7-06 AC 4)",
        )

    # Sinh mã bảo mật độc nhất nếu chưa có
    share_token = q.get("share_token") or f"sq_{secrets.token_urlsafe(24)}"
    share_link = f"/public/quotes/{share_token}"
    email_to = recipient_email or q.get("recipient_email") or f"customer_{q.get('customer_id', 1)}@example.com"

    now_iso = datetime.now().isoformat()
    prev_status = q.get("status")
    q["share_token"] = share_token
    q["share_link"] = share_link
    q["recipient_email"] = email_to
    q["status"] = "SENT"
    q["sent_at"] = now_iso
    q["updated_at"] = now_iso

    actor_id = current_user.get("id") if current_user else q.get("owner_id", 1)
    actor_name = (current_user.get("full_name") or current_user.get("username", "Nhân viên kinh doanh")) if current_user else "Nhân viên kinh doanh"
    actor_role = current_user.get("role", "USER") if current_user else "USER"

    hist_item = {
        "id": f"hist-sendlink-{int(datetime.now().timestamp() * 1000)}",
        "action": "SEND_LINK",
        "performed_by_id": actor_id,
        "performed_by_name": actor_name,
        "performed_by_role": actor_role,
        "comments": f"Đã gửi email kèm liên kết trực tuyến xem báo giá tới {email_to} (S7-06 AC 1).",
        "previous_status": prev_status,
        "new_status": "SENT",
        "timestamp": now_iso,
    }
    q.setdefault("approval_history", []).append(hist_item)

    # Ghi nhận vào dòng thời gian cơ hội (AC 1 & AC 3)
    if q.get("opportunity_id"):
        _record_opportunity_timeline_activity(
            opportunity_id=q["opportunity_id"],
            customer_id=q.get("customer_id"),
            owner_id=actor_id,
            title=f"Gửi email báo giá {q['quote_number']}",
            activity_type="EMAIL",
            description=f"Nhân viên kinh doanh đã gửi email kèm liên kết xem báo giá trực tuyến tới: {email_to}.\nTiêu đề email: {email_subject or q.get('title')}\nLiên kết xem báo giá: {share_link}\nNội dung thư: {message or 'Kính gửi Quý khách hàng báo giá giải pháp chi tiết.'}",
            db=db,
        )

    _safe_log_audit(
        user_id=actor_id,
        user_name=actor_name,
        entity_id=f"QUOTE-{quote_id}",
        action="SEND_QUOTE_LINK",
        field_name="status",
        old_value=prev_status,
        new_value="SENT",
        db=db,
    )

    return {
        "quote_id": q["id"],
        "quote_number": q.get("quote_number") or f"BG-{q['id']}",
        "recipient_email": email_to,
        "share_token": share_token,
        "share_link": share_link,
        "sent_at": now_iso,
        "message": "Đã gửi email kèm liên kết xem báo giá thành công (S7-06 AC 1)",
    }


def get_quote_by_share_token(share_token: str, mark_viewed: bool = True, db=None) -> dict:
    """
    Xem chi tiết báo giá qua liên kết công khai (S7-06 AC 2):
    - Kiểm tra token duy nhất
    - Kiểm tra quá hạn hiệu lực -> tự động chuyển EXPIRED
    - Đánh dấu đã xem (viewed_at, view_count, chuyển status SENT -> VIEWED)
    - Ghi nhận Activity trên dòng thời gian cơ hội
    """
    check_and_expire_quotes(db=db)
    target_q = None
    for q in FAKE_QUOTES:
        if q.get("share_token") == share_token:
            target_q = q
            break

    if not target_q:
        raise HTTPException(
            status_code=404,
            detail="Liên kết xem báo giá không tồn tại hoặc không hợp lệ (S7-06 AC 1)",
        )

    now_iso = datetime.now().isoformat()
    today_str = str(date.today())
    v_date = str(target_q.get("valid_until", ""))[:10]

    # Kiểm tra quá hạn hiệu lực (AC 4)
    if v_date and v_date < today_str and target_q.get("status") in ("SENT", "VIEWED", "APPROVED", "DRAFT"):
        target_q["status"] = "EXPIRED"
        target_q["updated_at"] = now_iso
        hist_item = {
            "id": f"hist-exp-{int(datetime.now().timestamp() * 1000)}",
            "action": "AUTO_EXPIRED",
            "performed_by_id": None,
            "performed_by_name": "Hệ thống tự động",
            "performed_by_role": "SYSTEM",
            "comments": f"Báo giá tự động chuyển sang Hết hiệu lực do quá hạn hiệu lực ({v_date}) mà chưa có phản hồi từ khách hàng (S7-06 AC 4).",
            "previous_status": "SENT",
            "new_status": "EXPIRED",
            "timestamp": now_iso,
        }
        target_q.setdefault("approval_history", []).append(hist_item)
        if target_q.get("opportunity_id"):
            _record_opportunity_timeline_activity(
                opportunity_id=target_q["opportunity_id"],
                customer_id=target_q.get("customer_id"),
                owner_id=target_q.get("owner_id", 1),
                title=f"Báo giá {target_q.get('quote_number')} đã hết hiệu lực",
                activity_type="NOTE",
                description=f"Báo giá {target_q.get('quote_number')} đã hết hạn hiệu lực ({v_date}).",
                db=db,
            )

    is_expired = (target_q.get("status") == "EXPIRED") or (bool(v_date) and v_date < today_str)

    # Đánh dấu đã xem nếu còn hiệu lực (AC 2)
    if mark_viewed and not is_expired:
        target_q["view_count"] = int(target_q.get("view_count") or 0) + 1
        target_q["viewed_at"] = now_iso
        if target_q.get("status") == "SENT":
            target_q["status"] = "VIEWED"
            target_q["updated_at"] = now_iso

            hist_item = {
                "id": f"hist-view-{int(datetime.now().timestamp() * 1000)}",
                "action": "CUSTOMER_VIEWED",
                "performed_by_id": None,
                "performed_by_name": "Khách hàng",
                "performed_by_role": "CUSTOMER",
                "comments": "Khách hàng đã mở xem báo giá trực tuyến qua liên kết (S7-06 AC 2).",
                "previous_status": "SENT",
                "new_status": "VIEWED",
                "timestamp": now_iso,
            }
            target_q.setdefault("approval_history", []).append(hist_item)

            if target_q.get("opportunity_id"):
                _record_opportunity_timeline_activity(
                    opportunity_id=target_q["opportunity_id"],
                    customer_id=target_q.get("customer_id"),
                    owner_id=target_q.get("owner_id", 1),
                    title=f"Khách hàng đã xem báo giá {target_q.get('quote_number')}",
                    activity_type="NOTE",
                    description=f"Khách hàng đã mở xem chi tiết báo giá {target_q.get('quote_number')} qua liên kết trực tuyến lúc {now_iso}.",
                    db=db,
                )

    # Lấy tên khách hàng nếu có
    cust_name = None
    if target_q.get("customer_id"):
        try:
            from app.services.customer_service import get_raw_customer_by_id
            cust = get_raw_customer_by_id(target_q["customer_id"])
            if cust:
                cust_name = cust.get("name")
        except Exception:
            pass

    # Chuyển đổi số tiền sang chữ tiếng Việt
    from app.utils.number_to_words import number_to_vietnamese_words
    amt_words = number_to_vietnamese_words(target_q.get("grand_total") or target_q.get("amount") or 0.0)

    # Dòng sản phẩm
    public_items = []
    for it in target_q.get("items", []):
        public_items.append({
            "id": str(it.get("id")),
            "product_code": it.get("product_code"),
            "product_name": it.get("product_name", "Sản phẩm"),
            "unit": it.get("unit") or "Gói",
            "quantity": int(it.get("quantity") or 1),
            "unit_price": float(it.get("unit_price") or 0.0),
            "discount_type": str(it.get("discount_type") or "PERCENT"),
            "discount_value": float(it.get("discount_value") or 0.0),
            "line_discount_amount": float(it.get("line_discount_amount") or 0.0),
            "vat_rate": int(it.get("vat_rate") or 10),
            "line_total": float(it.get("line_total") or 0.0),
        })

    return {
        "id": target_q["id"],
        "quote_number": target_q.get("quote_number") or f"BG-{target_q['id']}",
        "title": target_q.get("title", "Báo giá thương mại"),
        "status": target_q.get("status", "SENT"),
        "is_expired": is_expired,
        "valid_until": target_q.get("valid_until"),
        "payment_terms": target_q.get("payment_terms"),
        "delivery_terms": target_q.get("delivery_terms"),
        "notes": target_q.get("notes"),
        "customer_id": target_q.get("customer_id"),
        "customer_name": cust_name,
        "items": public_items,
        "subtotal": float(target_q.get("subtotal") or target_q.get("amount") or 0.0),
        "total_line_discount": float(target_q.get("total_line_discount") or 0.0),
        "total_discount_amount": float(target_q.get("total_discount_amount") or 0.0),
        "discount_percentage": float(target_q.get("discount_percentage") or 0.0),
        "vat_amount": float(target_q.get("vat_amount") or 0.0),
        "grand_total": float(target_q.get("grand_total") or target_q.get("amount") or 0.0),
        "amount_in_words": amt_words,
        "viewed_at": target_q.get("viewed_at"),
        "view_count": int(target_q.get("view_count") or 0),
        "customer_response_status": target_q.get("customer_response_status"),
        "customer_feedback": target_q.get("customer_feedback"),
        "customer_responded_at": target_q.get("customer_responded_at"),
        "customer_responder_name": target_q.get("customer_responder_name"),
        "created_at": target_q.get("created_at"),
    }


def customer_respond_quote(
    share_token: str,
    action: str,
    feedback: Optional[str] = None,
    responder_name: Optional[str] = None,
    db=None,
) -> dict:
    """
    Khách bấm Chấp nhận hoặc Từ chối, có ô ghi ý kiến (S7-06 AC 2 & AC 3):
    - Cập nhật ngay trạng thái báo giá: ACCEPTED hoặc DECLINED
    - Ghi nhận ý kiến khách hàng (customer_feedback)
    - Ghi nhận lịch sử bất biến (CUSTOMER_ACCEPTED / CUSTOMER_REJECTED)
    - Ghi nhận Activity vào dòng thời gian Cơ hội & cập nhật last_activity_at
    """
    check_and_expire_quotes(db=db)
    target_q = None
    for q in FAKE_QUOTES:
        if q.get("share_token") == share_token:
            target_q = q
            break

    if not target_q:
        raise HTTPException(
            status_code=404,
            detail="Liên kết xem báo giá không tồn tại hoặc không hợp lệ (S7-06 AC 1)",
        )

    now_iso = datetime.now().isoformat()
    today_str = str(date.today())
    v_date = str(target_q.get("valid_until", ""))[:10]

    # Kiểm tra quá hạn hiệu lực (AC 4)
    if (v_date and v_date < today_str) or target_q.get("status") == "EXPIRED":
        target_q["status"] = "EXPIRED"
        target_q["updated_at"] = now_iso
        raise HTTPException(
            status_code=400,
            detail="Báo giá này đã hết hạn hiệu lực, không thể gửi phản hồi (S7-06 AC 4)",
        )

    current_status = target_q.get("status")
    if current_status in ("ACCEPTED", "DECLINED", "REJECTED", "CONVERTED"):
        raise HTTPException(
            status_code=400,
            detail=f"Báo giá này đã được phản hồi trước đó (trạng thái hiện tại: {current_status}).",
        )

    action_upper = str(action).upper().strip()
    clean_feedback = feedback.strip() if feedback else None
    clean_responder = responder_name.strip() if responder_name else "Đại diện Khách hàng"

    if action_upper == "ACCEPT":
        new_status = "ACCEPTED"
        hist_action = "CUSTOMER_ACCEPTED"
        default_comment = "Khách hàng đã CHẤP NHẬN báo giá qua liên kết trực tuyến."
        activity_title = f"Phản hồi báo giá {target_q['quote_number']}: CHẤP NHẬN"
    elif action_upper == "REJECT":
        new_status = "DECLINED"
        hist_action = "CUSTOMER_REJECTED"
        default_comment = "Khách hàng đã TỪ CHỐI báo giá qua liên kết trực tuyến."
        activity_title = f"Phản hồi báo giá {target_q['quote_number']}: TỪ CHỐI"
    else:
        raise HTTPException(
            status_code=400,
            detail="Hành động phản hồi không hợp lệ. Chỉ chấp nhận 'ACCEPT' hoặc 'REJECT'.",
        )

    # Cập nhật báo giá ngay lập tức (AC 3)
    target_q["status"] = new_status
    target_q["customer_response_status"] = action_upper
    target_q["customer_feedback"] = clean_feedback
    target_q["customer_responded_at"] = now_iso
    target_q["customer_responder_name"] = clean_responder
    target_q["updated_at"] = now_iso

    full_comment = f"{default_comment} Người phản hồi: {clean_responder}."
    if clean_feedback:
        full_comment += f" Ý kiến: {clean_feedback}"

    hist_item = {
        "id": f"hist-resp-{int(datetime.now().timestamp() * 1000)}",
        "action": hist_action,
        "performed_by_id": None,
        "performed_by_name": clean_responder,
        "performed_by_role": "CUSTOMER",
        "comments": full_comment,
        "previous_status": current_status,
        "new_status": new_status,
        "timestamp": now_iso,
    }
    target_q.setdefault("approval_history", []).append(hist_item)

    # Ghi nhận vào dòng thời gian cơ hội (AC 3)
    if target_q.get("opportunity_id"):
        desc_lines = [
            f"Khách hàng đã gửi phản hồi trực tuyến qua liên kết:",
            f"- Quyết định: {'CHẤP NHẬN' if action_upper == 'ACCEPT' else 'TỪ CHỐI'}",
            f"- Người phản hồi: {clean_responder}",
            f"- Ý kiến phản hồi: {clean_feedback or '(Không có ý kiến bổ sung)'}",
            f"- Thời gian phản hồi: {now_iso[:19]}",
        ]
        _record_opportunity_timeline_activity(
            opportunity_id=target_q["opportunity_id"],
            customer_id=target_q.get("customer_id"),
            owner_id=target_q.get("owner_id", 1),
            title=activity_title,
            activity_type="NOTE",
            description="\n".join(desc_lines),
            db=db,
        )

    _safe_log_audit(
        user_id=1,
        user_name=clean_responder,
        entity_id=f"QUOTE-{target_q['id']}",
        action=hist_action,
        field_name="status",
        old_value=current_status,
        new_value=new_status,
        db=db,
    )

    return {
        "success": True,
        "quote_number": target_q.get("quote_number") or f"BG-{target_q['id']}",
        "new_status": new_status,
        "action": action_upper,
        "message": f"Quý khách đã {'chấp nhận' if action_upper == 'ACCEPT' else 'từ chối'} báo giá thành công (S7-06 AC 2 & AC 3)",
        "customer_feedback": clean_feedback,
        "responded_at": now_iso,
    }
