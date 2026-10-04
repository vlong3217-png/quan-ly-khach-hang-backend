import copy
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.master_data import (
    MasterDataCreate,
    MasterDataReorderRequest,
    MasterDataType,
    MasterDataUpdate,
)

INITIAL_MASTER_DATA = [
    # INDUSTRY (Ngành nghề)
    {
        "id": 1,
        "category": "INDUSTRY",
        "code": "TECH",
        "name": "Công nghệ thông tin & Viễn thông",
        "sort_order": 1,
        "is_active": True,
        "description": "Doanh nghiệp trong lĩnh vực IT/Telco",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "category": "INDUSTRY",
        "code": "FINANCE",
        "name": "Tài chính - Ngân hàng - Bảo hiểm",
        "sort_order": 2,
        "is_active": True,
        "description": "Ngân hàng và tổ chức tín dụng",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 3,
        "category": "INDUSTRY",
        "code": "RETAIL",
        "name": "Bán lẻ & Thương mại điện tử",
        "sort_order": 3,
        "is_active": True,
        "description": "Các chuỗi bán lẻ và sàn TMĐT",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    # COMPANY_SIZE (Quy mô)
    {
        "id": 4,
        "category": "COMPANY_SIZE",
        "code": "SIZE_MICRO",
        "name": "Dưới 10 nhân sự (Siêu nhỏ)",
        "sort_order": 1,
        "is_active": True,
        "description": "Doanh nghiệp siêu nhỏ",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 5,
        "category": "COMPANY_SIZE",
        "code": "SIZE_SME",
        "name": "10 - 100 nhân sự (Vừa và nhỏ)",
        "sort_order": 2,
        "is_active": True,
        "description": "Doanh nghiệp SME",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 6,
        "category": "COMPANY_SIZE",
        "code": "SIZE_ENT",
        "name": "Trên 100 nhân sự (Doanh nghiệp lớn)",
        "sort_order": 3,
        "is_active": True,
        "description": "Enterprise",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    # LEAD_SOURCE (Nguồn lead)
    {
        "id": 7,
        "category": "LEAD_SOURCE",
        "code": "WEBSITE",
        "name": "Website / Form đăng ký",
        "sort_order": 1,
        "is_active": True,
        "description": "Khách hàng đăng ký trực tiếp trên web",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 8,
        "category": "LEAD_SOURCE",
        "code": "REFERRAL",
        "name": "Giới thiệu từ đối tác",
        "sort_order": 2,
        "is_active": True,
        "description": "Khách hàng do đối tác giới thiệu",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    # ACTIVITY_TYPE (Loại hoạt động)
    {
        "id": 9,
        "category": "ACTIVITY_TYPE",
        "code": "CALL",
        "name": "Gọi điện thoại",
        "sort_order": 1,
        "is_active": True,
        "description": "Cuộc gọi trao đổi công việc",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 10,
        "category": "ACTIVITY_TYPE",
        "code": "MEETING",
        "name": "Gặp mặt trực tiếp",
        "sort_order": 2,
        "is_active": True,
        "description": "Họp trực tiếp với khách hàng",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
]

# Giả lập danh sách ID master data đang được tham chiếu trong các thực thể (Customer, Lead, Activity...)
# AC S2-07: Kiểm tra ràng buộc không cho phép xóa danh mục đang có bản ghi tham chiếu
REFERENCED_MASTER_DATA_IDS = {1, 4, 7, 9}

fake_master_data_db = copy.deepcopy(INITIAL_MASTER_DATA)


def reset_fake_master_data():
    global fake_master_data_db
    fake_master_data_db = copy.deepcopy(INITIAL_MASTER_DATA)


def get_master_data(
    category: Optional[str] = None,
    active_only: bool = False,
) -> List[dict]:
    results = fake_master_data_db
    if category:
        cat_upper = category.upper()
        results = [m for m in results if m["category"] == cat_upper]

    if active_only:
        results = [m for m in results if m.get("is_active", True)]

    # Sắp xếp theo sort_order tăng dần
    results = sorted(results, key=lambda x: (x.get("sort_order", 0), x["id"]))
    
    enriched = []
    for item in results:
        it = copy.deepcopy(item)
        it["in_use_count"] = 5 if it["id"] in REFERENCED_MASTER_DATA_IDS else 0
        enriched.append(it)
    return enriched


def get_master_data_by_id(item_id: int) -> dict:
    for item in fake_master_data_db:
        if item["id"] == item_id:
            res = copy.deepcopy(item)
            res["in_use_count"] = 5 if res["id"] in REFERENCED_MASTER_DATA_IDS else 0
            return res
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy danh mục dữ liệu với ID {item_id}",
    )


def create_master_data(data_in: MasterDataCreate) -> dict:
    clean_code = data_in.code.strip().upper()
    cat_val = data_in.category.value

    # Kiểm tra trùng code trong cùng category
    if any(m["category"] == cat_val and m["code"].upper() == clean_code for m in fake_master_data_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã '{clean_code}' đã tồn tại trong danh mục {cat_val}",
        )

    next_id = max([m["id"] for m in fake_master_data_db], default=0) + 1
    new_item = {
        "id": next_id,
        "category": cat_val,
        "code": clean_code,
        "name": data_in.name.strip(),
        "sort_order": data_in.sort_order,
        "is_active": data_in.is_active,
        "description": data_in.description.strip() if data_in.description else None,
        "created_at": datetime.utcnow(),
    }
    fake_master_data_db.append(new_item)
    res = copy.deepcopy(new_item)
    res["in_use_count"] = 0
    return res


def update_master_data(item_id: int, data_in: MasterDataUpdate) -> dict:
    item = next((m for m in fake_master_data_db if m["id"] == item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy danh mục dữ liệu với ID {item_id}",
        )

    if data_in.name is not None:
        item["name"] = data_in.name.strip()
    if data_in.sort_order is not None:
        item["sort_order"] = data_in.sort_order
    if data_in.is_active is not None:
        item["is_active"] = data_in.is_active
    if data_in.description is not None:
        item["description"] = data_in.description.strip()

    res = copy.deepcopy(item)
    res["in_use_count"] = 5 if res["id"] in REFERENCED_MASTER_DATA_IDS else 0
    return res


def reorder_master_data(category: str, reorder_in: MasterDataReorderRequest) -> List[dict]:
    """Cập nhật thứ tự sắp xếp danh mục."""
    cat_upper = category.upper()
    order_dict = {item.id: item.sort_order for item in reorder_in.items}

    for m in fake_master_data_db:
        if m["category"] == cat_upper and m["id"] in order_dict:
            m["sort_order"] = order_dict[m["id"]]

    return get_master_data(category=cat_upper)


def delete_master_data(item_id: int) -> dict:
    """
    AC S2-07: Kiểm tra ràng buộc dữ liệu không cho phép xóa danh mục đang có bản ghi tham chiếu.
    (Chỉ cho phép ẩn/vô hiệu hóa is_active = False nếu đang được dùng).
    """
    item = next((m for m in fake_master_data_db if m["id"] == item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy danh mục dữ liệu với ID {item_id}",
        )

    if item_id in REFERENCED_MASTER_DATA_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể xoá danh mục '{item['name']}' do đang có các bản ghi khách hàng/cơ hội tham chiếu. Vui lòng chuyển trạng thái sang Ẩn (Inactive) thay vì xoá.",
        )

    fake_master_data_db.remove(item)
    return {
        "success": True,
        "message": f"Đã xoá danh mục '{item['name']}' thành công.",
    }
