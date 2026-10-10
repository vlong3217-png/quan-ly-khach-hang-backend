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
            opp_copy["customer_name"] = cust["name"] if cust else None
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
    for opp in FAKE_OPPORTUNITIES:
        if opp["id"] == opportunity_id:
            return _enrich_opportunity_record(opp)
    return None


def get_opportunities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
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

    if customer_id is not None:
        raw_list = [o for o in raw_list if o.get("customer_id") == customer_id]

    results = [_enrich_opportunity_record(opp) for opp in raw_list]

    if search:
        s = search.lower().strip()
        results = [
            o for o in results
            if s in o.get("title", "").lower() or s in o.get("stage", "").lower()
        ]

    return results


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


