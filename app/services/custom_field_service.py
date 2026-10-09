import copy
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.custom_field import (
    CustomFieldCreate,
    CustomFieldType,
    CustomFieldUpdate,
    TargetEntity,
)

INITIAL_CUSTOM_FIELDS = [
    {
        "id": 1,
        "target_entity": "CUSTOMER",
        "field_key": "tax_code",
        "label": "Mã số thuế doanh nghiệp",
        "field_type": "TEXT",
        "options": None,
        "is_required": True,
        "sort_order": 1,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "target_entity": "CUSTOMER",
        "field_key": "customer_tier",
        "label": "Hạng hội viên VIP",
        "field_type": "SELECT",
        "options": ["Đồng", "Bạc", "Vàng", "Kim cương"],
        "is_required": False,
        "sort_order": 2,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 3,
        "target_entity": "OPPORTUNITY",
        "field_key": "expected_budget",
        "label": "Ngân sách dự kiến (VND)",
        "field_type": "NUMBER",
        "options": None,
        "is_required": False,
        "sort_order": 1,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 4,
        "target_entity": "OPPORTUNITY",
        "field_key": "tender_deadline",
        "label": "Hạn nộp hồ sơ thầu",
        "field_type": "DATE",
        "options": None,
        "is_required": False,
        "sort_order": 2,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
]

fake_custom_fields_db = copy.deepcopy(INITIAL_CUSTOM_FIELDS)


def reset_fake_custom_fields():
    global fake_custom_fields_db
    fake_custom_fields_db = copy.deepcopy(INITIAL_CUSTOM_FIELDS)


def get_custom_fields(target_entity: Optional[str] = None) -> List[dict]:
    results = fake_custom_fields_db
    if target_entity:
        te = target_entity.upper()
        results = [f for f in results if f["target_entity"] == te]
    return sorted(results, key=lambda x: (x.get("sort_order", 0), x["id"]))


def get_custom_field_by_id(field_id: int) -> dict:
    for f in fake_custom_fields_db:
        if f["id"] == field_id:
            return f
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy trường tùy chỉnh với ID {field_id}",
    )


def create_custom_field(field_in: CustomFieldCreate) -> dict:
    clean_key = field_in.field_key.strip().lower()
    entity = field_in.target_entity.value

    # Kiểm tra trùng field_key trong cùng entity
    if any(f["target_entity"] == entity and f["field_key"].lower() == clean_key for f in fake_custom_fields_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trường dữ liệu '{clean_key}' đã tồn tại cho đối tượng {entity}",
        )

    # Nếu field_type là SELECT thì bắt buộc phải có options
    if field_in.field_type == CustomFieldType.SELECT:
        if not field_in.options or len(field_in.options) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trường kiểu danh sách chọn (SELECT) bắt buộc phải có danh sách các lựa chọn (options)",
            )

    next_id = max([f["id"] for f in fake_custom_fields_db], default=0) + 1
    new_field = {
        "id": next_id,
        "target_entity": entity,
        "field_key": clean_key,
        "label": field_in.label.strip(),
        "field_type": field_in.field_type.value,
        "options": field_in.options,
        "is_required": field_in.is_required,
        "sort_order": field_in.sort_order,
        "created_at": datetime.utcnow(),
    }
    fake_custom_fields_db.append(new_field)
    return new_field


def update_custom_field(field_id: int, field_in: CustomFieldUpdate) -> dict:
    field = next((f for f in fake_custom_fields_db if f["id"] == field_id), None)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy trường tùy chỉnh với ID {field_id}",
        )

    if field_in.label is not None:
        field["label"] = field_in.label.strip()
    if field_in.options is not None:
        if field["field_type"] == "SELECT" and len(field_in.options) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trường kiểu danh sách chọn không thể có danh sách lựa chọn rỗng",
            )
        field["options"] = field_in.options
    if field_in.is_required is not None:
        field["is_required"] = field_in.is_required
    if field_in.sort_order is not None:
        field["sort_order"] = field_in.sort_order

    return field


def delete_custom_field(field_id: int) -> dict:
    field = next((f for f in fake_custom_fields_db if f["id"] == field_id), None)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy trường tùy chỉnh với ID {field_id}",
        )

    fake_custom_fields_db.remove(field)
    return {
        "success": True,
        "message": f"Đã xoá trường tùy chỉnh '{field['label']}' thành công.",
    }


def validate_custom_values(target_entity: str, values: Dict[str, Any]) -> dict:
    """
    AC S2-08: Validate tính hợp lệ của dữ liệu nhập vào các trường tùy biến
    (bắt buộc nhập, kiểu dữ liệu number/date, options của select).
    """
    entity = target_entity.upper()
    defined_fields = [f for f in fake_custom_fields_db if f["target_entity"] == entity]
    errors = {}

    for field in defined_fields:
        key = field["field_key"]
        val = values.get(key)

        # 1. Kiểm tra bắt buộc nhập
        if field.get("is_required", False):
            if val is None or (isinstance(val, str) and not val.strip()):
                errors[key] = f"Trường '{field['label']}' là bắt buộc nhập."
                continue

        if val is None or val == "":
            continue

        # 2. Kiểm tra kiểu NUMBER
        if field["field_type"] == "NUMBER":
            try:
                float(val)
            except (ValueError, TypeError):
                errors[key] = f"Trường '{field['label']}' phải là giá trị số hợp lệ."

        # 3. Kiểm tra kiểu SELECT
        elif field["field_type"] == "SELECT":
            opts = field.get("options") or []
            if str(val) not in opts:
                errors[key] = f"Giá trị '{val}' không nằm trong danh mục lựa chọn hợp lệ: {opts}"

        # 4. Kiểm tra kiểu DATE (YYYY-MM-DD)
        elif field["field_type"] == "DATE":
            try:
                datetime.strptime(str(val), "%Y-%m-%d")
            except ValueError:
                errors[key] = f"Trường '{field['label']}' phải có định dạng ngày hợp lệ (YYYY-MM-DD)."

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }
