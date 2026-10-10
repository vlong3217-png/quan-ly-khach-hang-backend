"""
Opportunity service with data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
from datetime import datetime
from typing import Optional
from app.core.dependencies import DataScope

INITIAL_OPPORTUNITIES = [
    {
        "id": 1,
        "title": "Hợp đồng phần mềm Admin",
        "value": 50000000.0,
        "stage": "PROPOSAL",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
    },
    {
        "id": 2,
        "title": "Hợp đồng dịch vụ Manager",
        "value": 30000000.0,
        "stage": "QUALIFICATION",
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
    },
    {
        "id": 3,
        "title": "Cung cấp thiết bị User1",
        "value": 15000000.0,
        "stage": "PROSPECTING",
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
    },
    {
        "id": 4,
        "title": "Bảo trì hệ thống User2",
        "value": 20000000.0,
        "stage": "CLOSED_WON",
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
    },
]

INITIAL_OPPORTUNITY_PRODUCTS = []

FAKE_OPPORTUNITIES = copy.deepcopy(INITIAL_OPPORTUNITIES)
FAKE_OPPORTUNITY_PRODUCTS = copy.deepcopy(INITIAL_OPPORTUNITY_PRODUCTS)


def reset_fake_opportunities() -> None:
    global FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS
    FAKE_OPPORTUNITIES.clear()
    FAKE_OPPORTUNITIES.extend(copy.deepcopy(INITIAL_OPPORTUNITIES))
    FAKE_OPPORTUNITY_PRODUCTS.clear()
    FAKE_OPPORTUNITY_PRODUCTS.extend(copy.deepcopy(INITIAL_OPPORTUNITY_PRODUCTS))


def recalculate_opportunity_value(opportunity_id: int) -> Optional[dict]:
    """
    AC S5-03: Tự động tính lại giá trị cơ hội:
    - Tổng giá trị cơ hội (value) = Tổng thành tiền của tất cả sản phẩm/dịch vụ.
    - Dịch vụ thuê bao: Tổng giá trị hợp đồng theo năm (arr).
    """
    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
        return None

    items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]
    if items:
        total_value = sum(i["amount"] for i in items)
        total_arr = sum(i["arr"] for i in items if i.get("arr") is not None)
        opp["value"] = round(total_value, 2)
        opp["arr"] = round(total_arr, 2)
        opp["has_products"] = True
    else:
        opp["value"] = 0.0
        opp["has_products"] = False
        opp["arr"] = 0.0

    return opp


def get_raw_opportunity_by_id(opportunity_id: int) -> Optional[dict]:
    for opp in FAKE_OPPORTUNITIES:
        if opp["id"] == opportunity_id:
            items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]
            opp_copy = copy.deepcopy(opp)
            opp_copy["products"] = items
            opp_copy["has_products"] = len(items) > 0
            opp_copy["arr"] = opp.get("arr", 0.0)
            return opp_copy
    return None


def get_opportunities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
) -> list[dict]:
    if scope == DataScope.ALL:
        raw_list = list(FAKE_OPPORTUNITIES)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            raw_list = list(FAKE_OPPORTUNITIES)
        else:
            raw_list = [o for o in FAKE_OPPORTUNITIES if o.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        raw_list = [o for o in FAKE_OPPORTUNITIES if o.get("owner_id") == user_id]

    results = []
    for opp in raw_list:
        items = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opp["id"]]
        c = copy.deepcopy(opp)
        c["products"] = items
        c["has_products"] = len(items) > 0
        c["arr"] = opp.get("arr", 0.0)
        results.append(c)

    if search:
        s = search.lower().strip()
        results = [
            o for o in results
            if s in o.get("title", "").lower() or s in o.get("stage", "").lower()
        ]

    return results


def create_opportunity_record(data: dict, current_user: dict) -> dict:
    new_id = (max(o["id"] for o in FAKE_OPPORTUNITIES) + 1) if FAKE_OPPORTUNITIES else 1
    new_opp = {
        "id": new_id,
        "title": data["title"],
        "value": data["value"],
        "stage": data.get("stage", "PROSPECTING"),
        "customer_id": data.get("customer_id"),
        "campaign_id": data.get("campaign_id"),
        "lead_id": data.get("lead_id"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "expected_close_date": data.get("expected_close_date"),
        "arr": 0.0,
        "has_products": False,
        "products": [],
        "status": "OPEN",
        "expected_close_date": data.get("expected_close_date"),
        "created_at": datetime.utcnow().isoformat(),
    }
    FAKE_OPPORTUNITIES.append(new_opp)
    return new_opp


def update_opportunity_record(opportunity_id: int, data: dict) -> Optional[dict]:
    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if opp is None:
        return None
    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            opp[key] = value
    return get_raw_opportunity_by_id(opportunity_id)


def delete_opportunity_record(opportunity_id: int) -> bool:
    global FAKE_OPPORTUNITIES, FAKE_OPPORTUNITY_PRODUCTS
    initial_len = len(FAKE_OPPORTUNITIES)
    FAKE_OPPORTUNITIES = [o for o in FAKE_OPPORTUNITIES if o["id"] != opportunity_id]
    FAKE_OPPORTUNITY_PRODUCTS = [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] != opportunity_id]
    return len(FAKE_OPPORTUNITIES) < initial_len


# ============================================================================
# QUẢN LÝ SẢN PHẨM / DỊCH VỤ TRONG CƠ HỘI (OPPORTUNITY PRODUCTS - S5-03)
# ============================================================================

def list_opportunity_products(opportunity_id: int) -> list[dict]:
    """Lấy danh sách sản phẩm/dịch vụ trong cơ hội."""
    return [p for p in FAKE_OPPORTUNITY_PRODUCTS if p["opportunity_id"] == opportunity_id]


def add_product_to_opportunity(
    opportunity_id: int,
    payload_data: dict,
    current_user: dict,
) -> dict:
    """
    AC S5-03: Thêm sản phẩm/dịch vụ vào cơ hội:
    - Chọn sản phẩm từ danh mục.
    - Nhập số lượng và đơn giá (mặc định lấy từ bảng giá list_price).
    - Kiểm tra giá sàn (không thấp hơn floor_price).
    - Dịch vụ thuê bao (SUBSCRIPTION): tính số kỳ, MRR, ARR.
    - Tự động tính lại tổng giá trị cơ hội.
    """
    from fastapi import HTTPException, status
    from app.services.product_service import get_product_by_id, fake_products_db

    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
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

    # Đơn giá: Mặc định lấy từ bảng giá niêm yết (list_price) nếu không nhập
    unit_price = float(payload_data.get("unit_price")) if payload_data.get("unit_price") is not None and float(payload_data.get("unit_price")) > 0 else list_price

    # Kiểm tra giá sàn
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
            num_cycles = default_cycles

        term_months = num_cycles if cycle == "MONTHLY" else (num_cycles * 3 if cycle == "QUARTERLY" else num_cycles * 12)
        amount = round(quantity * unit_price * num_cycles * (1 - discount / 100), 2)

        # Tính MRR và ARR
        if cycle == "MONTHLY":
            mrr = round(quantity * unit_price * (1 - discount / 100), 2)
            arr = round(mrr * 12, 2)
        elif cycle == "QUARTERLY":
            arr = round(quantity * unit_price * 4 * (1 - discount / 100), 2)
            mrr = round(arr / 12, 2)
        else: # ANNUALLY
            arr = round(quantity * unit_price * (1 - discount / 100), 2)
            mrr = round(arr / 12, 2)
    else:
        cycle = None
        num_cycles = None
        term_months = None
        arr = None
        mrr = None
        amount = round(quantity * unit_price * (1 - discount / 100), 2)

    new_id = (max([p["id"] for p in FAKE_OPPORTUNITY_PRODUCTS], default=0) + 1)
    new_item = {
        "id": new_id,
        "opportunity_id": opportunity_id,
        "product_id": product_id,
        "product_code": product.get("code", f"PROD-{product_id}"),
        "product_name": product["name"],
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

    FAKE_OPPORTUNITY_PRODUCTS.append(new_item)
    # Tự động tính lại tổng giá trị cơ hội
    recalculate_opportunity_value(opportunity_id)
    return new_item


def update_opportunity_product(
    opportunity_id: int,
    item_id: int,
    payload_data: dict,
) -> dict:
    """Cập nhật sản phẩm trong cơ hội và tính lại giá trị."""
    from fastapi import HTTPException, status
    item = next((p for p in FAKE_OPPORTUNITY_PRODUCTS if p["id"] == item_id and p["opportunity_id"] == opportunity_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy dòng sản phẩm với ID {item_id} trong cơ hội #{opportunity_id}",
        )

    if payload_data.get("quantity") is not None:
        q = float(payload_data["quantity"])
        if q <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số lượng phải lớn hơn 0")
        item["quantity"] = q

    if payload_data.get("unit_price") is not None:
        p = float(payload_data["unit_price"])
        if p < item["floor_price"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn giá {p:,.0f} đ không được thấp hơn giá sàn {item['floor_price']:,.0f} đ",
            )
        item["unit_price"] = p

    if payload_data.get("discount_percent") is not None:
        d = float(payload_data["discount_percent"])
        if d < 0 or d > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chiết khấu phải từ 0% đến 100%")
        item["discount_percent"] = d

    if item["product_type"] == "SUBSCRIPTION":
        if payload_data.get("billing_cycle") is not None:
            c = payload_data["billing_cycle"].upper()
            if c in ("MONTHLY", "QUARTERLY", "ANNUALLY"):
                item["billing_cycle"] = c
        if payload_data.get("number_of_cycles") is not None:
            nc = int(payload_data["number_of_cycles"])
            if nc > 0:
                item["number_of_cycles"] = nc

        cycle = item["billing_cycle"] or "MONTHLY"
        num_cycles = item["number_of_cycles"] or 12
        item["term_months"] = num_cycles if cycle == "MONTHLY" else (num_cycles * 3 if cycle == "QUARTERLY" else num_cycles * 12)
        item["amount"] = round(item["quantity"] * item["unit_price"] * num_cycles * (1 - item["discount_percent"] / 100), 2)

        if cycle == "MONTHLY":
            mrr = round(item["quantity"] * item["unit_price"] * (1 - item["discount_percent"] / 100), 2)
            item["mrr"] = mrr
            item["arr"] = round(mrr * 12, 2)
        elif cycle == "QUARTERLY":
            arr = round(item["quantity"] * item["unit_price"] * 4 * (1 - item["discount_percent"] / 100), 2)
            item["arr"] = arr
            item["mrr"] = round(arr / 12, 2)
        else: # ANNUALLY
            arr = round(item["quantity"] * item["unit_price"] * (1 - item["discount_percent"] / 100), 2)
            item["arr"] = arr
            item["mrr"] = round(arr / 12, 2)
    else:
        item["amount"] = round(item["quantity"] * item["unit_price"] * (1 - item["discount_percent"] / 100), 2)

    recalculate_opportunity_value(opportunity_id)
    return item


def delete_opportunity_product(opportunity_id: int, item_id: int) -> bool:
    """Xóa sản phẩm khỏi cơ hội và tự động tính lại tổng giá trị."""
    global FAKE_OPPORTUNITY_PRODUCTS
    initial_len = len(FAKE_OPPORTUNITY_PRODUCTS)
    FAKE_OPPORTUNITY_PRODUCTS = [
        p for p in FAKE_OPPORTUNITY_PRODUCTS
        if not (p["id"] == item_id and p["opportunity_id"] == opportunity_id)
    ]
    if len(FAKE_OPPORTUNITY_PRODUCTS) < initial_len:
        recalculate_opportunity_value(opportunity_id)
        return True
    return False


def reassign_opportunities(
    opportunity_ids: list[int],
    new_owner_id: int,
    reason: str,
    current_user: dict,
) -> dict:
    """
    S5-08: Phân bổ lại một hoặc nhiều cơ hội bán hàng cho nhân viên khác trong nhóm.
    - Validate danh sách cơ hội (không rỗng, tồn tại).
    - Validate người nhận mới (tồn tại trong hệ thống, đang hoạt động).
    - Validate lý do chuyển quyền (bắt buộc nhập lý do, không được để trống).
    - Validate quyền thực hiện (ADMIN, hoặc MANAGER phụ trách cơ hội đó).
    - Cập nhật owner_id và team_id của người nhận mới cho các cơ hội.
    - Cập nhật quyền sở hữu và gán người nhận mới vào các hoạt động (Activities) liên quan.
    - Ghi nhật ký hệ thống (Audit Log) cho từng cơ hội được chuyển quyền kèm lý do.
    """
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

    # Validate người nhận mới
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

    # Tìm danh sách cơ hội
    matched_opps = []
    missing_ids = []
    for oid in opportunity_ids:
        found = False
        for opp in FAKE_OPPORTUNITIES:
            if opp["id"] == oid:
                matched_opps.append(opp)
                found = True
                break
        if not found:
            missing_ids.append(oid)

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy các cơ hội với ID: {missing_ids}",
        )

    current_role = current_user.get("role", "USER")
    current_uid = current_user.get("id")
    current_team = current_user.get("team_id")

    # Kiểm tra quyền: ADMIN hoặc MANAGER
    # Nếu là MANAGER: chỉ được phân bổ các cơ hội thuộc team của mình hoặc do mình sở hữu
    for opp in matched_opps:
        if current_role == "ADMIN":
            continue
        elif current_role == "MANAGER":
            opp_team = opp.get("team_id")
            opp_owner = opp.get("owner_id")
            if opp_owner != current_uid and (opp_team is None or opp_team != current_team):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Bạn không có quyền phân bổ lại cơ hội '{opp.get('title')}' (ID {opp['id']}) ngoài nhóm quản lý",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ Trưởng nhóm kinh doanh hoặc Quản trị viên mới có quyền phân bổ lại cơ hội",
            )

    # Thực hiện chuyển quyền sở hữu
    reassigned_ids = []
    for opp in matched_opps:
        old_owner_id = opp["owner_id"]
        opp["owner_id"] = new_owner_id
        if target_user.get("team_id") is not None:
            opp["team_id"] = target_user["team_id"]
        reassigned_ids.append(opp["id"])

        # Chuyển quyền / cập nhật các activity liên quan để người nhận thấy toàn bộ lịch sử
        for act in FAKE_ACTIVITIES:
            if act.get("opportunity_id") == opp["id"]:
                if target_user.get("team_id") is not None:
                    act["team_id"] = target_user["team_id"]

        # Ghi nhật ký Audit Log
        log_change(
            user_id=current_uid,
            user_name=current_user.get("full_name") or current_user.get("username") or "Manager",
            entity_type="DATA_OWNERSHIP",
            entity_id=str(opp["id"]),
            action="REASSIGN_OPPORTUNITY",
            field_name="owner_id",
            old_value=f"Owner ID {old_owner_id}",
            new_value=f"Owner ID {new_owner_id} ({target_user.get('full_name')}) - Lý do: {clean_reason}",
        )

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


# ============================================================================
# NGHIỆP VỤ S5-05: ĐÓNG THẮNG, ĐÓNG THUA & MỞ LẠI CƠ HỘI
# ============================================================================

def close_opportunity_won(
    opportunity_id: int,
    actual_revenue: float,
    contract_signed_date: str,
    note: Optional[str],
    current_user: dict,
) -> dict:
    """
    AC S5-05: Đóng Thắng (Closed Won)
    - Bắt buộc nhập giá trị chốt thực tế (> 0) và ngày ký hợp đồng (YYYY-MM-DD).
    - Cơ hội đã đóng không được sửa/đóng lại nếu chưa mở.
    - Cập nhật stage = 'CLOSED_WON', status = 'CLOSED_WON', actual_revenue, contract_signed_date.
    - Ghi nhận Audit Log.
    - Doanh số thực tế được cộng/tính vào chỉ tiêu của người sở hữu cơ hội.
    """
    from fastapi import HTTPException, status
    from app.services.audit_log_service import log_change

    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cơ hội bán hàng với ID {opportunity_id}",
        )

    # Kiểm tra trạng thái đã đóng
    if opp.get("stage") in ("CLOSED_WON", "CLOSED_LOST") or opp.get("status") in ("CLOSED_WON", "CLOSED_LOST"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cơ hội này đã được đóng trước đó. Cần liên hệ Trưởng nhóm trở lên để mở lại nếu muốn thay đổi.",
        )

    # Validate giá trị thực tế
    if actual_revenue is None or float(actual_revenue) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đóng Thắng bắt buộc nhập giá trị chốt thực tế (actual_revenue > 0)",
        )

    # Validate ngày ký hợp đồng
    if not contract_signed_date or not str(contract_signed_date).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đóng Thắng bắt buộc nhập ngày ký hợp đồng (contract_signed_date)",
        )
    date_str = str(contract_signed_date).strip()
    try:
        # Kiểm tra định dạng ngày
        datetime.fromisoformat(date_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày ký hợp đồng không đúng định dạng chuẩn (YYYY-MM-DD)",
        )

    now_iso = datetime.utcnow().isoformat()
    old_stage = opp.get("stage")
    old_value = opp.get("value")

    opp["stage"] = "CLOSED_WON"
    opp["status"] = "CLOSED_WON"
    opp["actual_revenue"] = float(actual_revenue)
    opp["value"] = float(actual_revenue)  # Đồng bộ giá trị cơ hội thành giá trị thực tế
    opp["contract_signed_date"] = date_str
    opp["closed_date"] = date_str
    opp["closed_at"] = now_iso
    opp["closed_by"] = current_user.get("id")
    if note:
        opp["close_note"] = note.strip()

    # Xóa cờ cảnh báo nếu có (S5-07)
    opp["is_flagged"] = False
    opp["is_stagnant"] = False
    opp["is_overdue"] = False

    # Ghi Audit Log
    user_name = current_user.get("full_name") or current_user.get("username") or f"User {current_user.get('id')}"
    log_change(
        user_id=current_user.get("id"),
        user_name=user_name,
        entity_type="DATA_OWNERSHIP",
        entity_id=str(opportunity_id),
        action="CLOSE_OPPORTUNITY_WON",
        field_name="stage",
        old_value=f"Stage: {old_stage}, Value: {old_value}",
        new_value=f"CLOSED_WON: Doanh thu thực tế {actual_revenue:,.0f} đ, Ngày ký {date_str}",
    )

    return get_raw_opportunity_by_id(opportunity_id)


def close_opportunity_lost(
    opportunity_id: int,
    loss_reason: str,
    competitor: Optional[str],
    note: Optional[str],
    current_user: dict,
) -> dict:
    """
    AC S5-05: Đóng Thua (Closed Lost)
    - Bắt buộc chọn lý do thua (loss_reason).
    - Đối thủ thắng thầu nếu có (competitor).
    - Cập nhật stage = 'CLOSED_LOST', status = 'CLOSED_LOST'.
    - Ghi nhận Audit Log.
    """
    from fastapi import HTTPException, status
    from app.services.audit_log_service import log_change

    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cơ hội bán hàng với ID {opportunity_id}",
        )

    # Kiểm tra trạng thái đã đóng
    if opp.get("stage") in ("CLOSED_WON", "CLOSED_LOST") or opp.get("status") in ("CLOSED_WON", "CLOSED_LOST"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cơ hội này đã được đóng trước đó. Cần liên hệ Trưởng nhóm trở lên để mở lại nếu muốn thay đổi.",
        )

    # Validate lý do thua
    clean_loss_reason = (loss_reason or "").strip()
    if not clean_loss_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đóng Thua bắt buộc nhập hoặc chọn lý do thất bại (loss_reason)",
        )

    now_iso = datetime.utcnow().isoformat()
    old_stage = opp.get("stage")

    opp["stage"] = "CLOSED_LOST"
    opp["status"] = "CLOSED_LOST"
    opp["loss_reason"] = clean_loss_reason
    opp["competitor"] = competitor.strip() if competitor else None
    opp["closed_date"] = datetime.utcnow().date().isoformat()
    opp["closed_at"] = now_iso
    opp["closed_by"] = current_user.get("id")
    if note:
        opp["close_note"] = note.strip()

    # Xóa cờ cảnh báo nếu có
    opp["is_flagged"] = False
    opp["is_stagnant"] = False
    opp["is_overdue"] = False

    # Ghi Audit Log
    user_name = current_user.get("full_name") or current_user.get("username") or f"User {current_user.get('id')}"
    log_detail = f"Lý do: {clean_loss_reason}"
    if opp["competitor"]:
        log_detail += f", Đối thủ thắng: {opp['competitor']}"

    log_change(
        user_id=current_user.get("id"),
        user_name=user_name,
        entity_type="DATA_OWNERSHIP",
        entity_id=str(opportunity_id),
        action="CLOSE_OPPORTUNITY_LOST",
        field_name="stage",
        old_value=f"Stage: {old_stage}",
        new_value=f"CLOSED_LOST: {log_detail}",
    )

    return get_raw_opportunity_by_id(opportunity_id)


def reopen_opportunity(
    opportunity_id: int,
    reason: str,
    target_stage: Optional[str],
    current_user: dict,
) -> dict:
    """
    AC S5-05: Mở lại cơ hội đã đóng
    - Chỉ Trưởng nhóm trở lên (MANAGER, ADMIN) mới được mở lại.
    - Nhân viên thường (USER) không được phép mở lại (HTTP 403).
    - Bắt buộc nhập lý do mở lại (reason).
    - Chuyển trạng thái từ CLOSED_WON/CLOSED_LOST về giai đoạn mở (mặc định PROPOSAL hoặc target_stage).
    - Ghi nhận Audit Log.
    """
    from fastapi import HTTPException, status
    from app.services.audit_log_service import log_change

    opp = next((o for o in FAKE_OPPORTUNITIES if o["id"] == opportunity_id), None)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cơ hội bán hàng với ID {opportunity_id}",
        )

    current_role = current_user.get("role", "USER")
    current_uid = current_user.get("id")
    current_team = current_user.get("team_id")

    # Phân quyền: Chỉ ADMIN hoặc MANAGER
    if current_role not in ("ADMIN", "MANAGER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cơ hội đã đóng không sửa được. Chỉ Trưởng nhóm trở lên mới có quyền mở lại kèm lý do.",
        )

    # Manager chỉ được mở cơ hội trong nhóm mình
    if current_role == "MANAGER":
        opp_team = opp.get("team_id")
        opp_owner = opp.get("owner_id")
        if opp_owner != current_uid and (opp_team is None or opp_team != current_team):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền mở lại cơ hội thuộc nhóm khác",
            )

    # Phải đang ở trạng thái đã đóng
    if opp.get("stage") not in ("CLOSED_WON", "CLOSED_LOST") and opp.get("status") not in ("CLOSED_WON", "CLOSED_LOST"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cơ hội này chưa bị đóng, không cần mở lại.",
        )

    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mở lại cơ hội bắt buộc phải nhập lý do (reason)",
        )

    now_iso = datetime.utcnow().isoformat()
    old_stage = opp.get("stage")
    new_stage = target_stage.strip() if target_stage and target_stage.strip() else "PROPOSAL"

    opp["stage"] = new_stage
    opp["status"] = "OPEN"
    opp["reopened_at"] = now_iso
    opp["reopened_by"] = current_uid
    opp["reopen_reason"] = clean_reason

    # Ghi Audit Log
    user_name = current_user.get("full_name") or current_user.get("username") or f"Manager {current_uid}"
    log_change(
        user_id=current_uid,
        user_name=user_name,
        entity_type="DATA_OWNERSHIP",
        entity_id=str(opportunity_id),
        action="REOPEN_OPPORTUNITY",
        field_name="stage",
        old_value=f"Stage: {old_stage}",
        new_value=f"Reopened to {new_stage} - Lý do: {clean_reason}",
    )

    return get_raw_opportunity_by_id(opportunity_id)


def get_user_won_quota_achievement(user_id: int) -> dict:
    """
    AC S5-05: Thống kê cơ hội thắng được tính vào chỉ tiêu (monthly_quota) của người sở hữu.
    """
    from app.services.auth_service import fake_users_db

    user = next((u for u in fake_users_db if u["id"] == user_id), None)
    monthly_quota = float(user.get("monthly_quota", 0.0)) if user else 0.0

    won_opps = [
        o for o in FAKE_OPPORTUNITIES
        if o.get("owner_id") == user_id and o.get("stage") == "CLOSED_WON"
    ]

    total_won_value = sum(
        float(o.get("actual_revenue") if o.get("actual_revenue") is not None else o.get("value", 0.0))
        for o in won_opps
    )

    achievement_percent = round((total_won_value / monthly_quota) * 100, 2) if monthly_quota > 0 else None

    return {
        "user_id": user_id,
        "monthly_quota": monthly_quota,
        "total_won_opportunities": len(won_opps),
        "total_won_value": total_won_value,
        "achievement_percent": achievement_percent,
        "won_opportunities": won_opps,
    }



