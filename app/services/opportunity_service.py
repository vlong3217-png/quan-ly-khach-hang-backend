"""
Opportunity service with data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
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
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "arr": 0.0,
        "has_products": False,
        "products": [],
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

