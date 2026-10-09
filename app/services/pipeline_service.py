import copy
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.pipeline import (
    PipelineStageCreate,
    PipelineStageUpdate,
)

INITIAL_PIPELINE_STAGES = [
    {
        "id": 1,
        "code": "PROSPECTING",
        "name": "Tìm kiếm & Khảo sát nhu cầu",
        "win_probability": 10.0,
        "order_index": 1,
        "required_exit_fields": ["contact_person", "customer_need"],
        "is_won_stage": False,
        "is_lost_stage": False,
        "description": "Tiếp cận ban đầu và làm rõ nhu cầu sơ bộ",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "code": "QUALIFICATION",
        "name": "Đánh giá mức độ tiềm năng (BANT)",
        "win_probability": 25.0,
        "order_index": 2,
        "required_exit_fields": ["budget_confirmed", "decision_maker"],
        "is_won_stage": False,
        "is_lost_stage": False,
        "description": "Xác định ngân sách và người ra quyết định",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 3,
        "code": "PROPOSAL",
        "name": "Trình bày giải pháp & Báo giá",
        "win_probability": 50.0,
        "order_index": 3,
        "required_exit_fields": ["quote_id", "solution_document"],
        "is_won_stage": False,
        "is_lost_stage": False,
        "description": "Gửi báo giá chính thức kèm hồ sơ kỹ thuật",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 4,
        "code": "NEGOTIATION",
        "name": "Thương thảo hợp đồng",
        "win_probability": 80.0,
        "order_index": 4,
        "required_exit_fields": ["contract_draft", "payment_terms"],
        "is_won_stage": False,
        "is_lost_stage": False,
        "description": "Đàm phán điều khoản hợp đồng & phương thức thanh toán",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 5,
        "code": "CLOSED_WON",
        "name": "Thành công (Won)",
        "win_probability": 100.0,
        "order_index": 5,
        "required_exit_fields": ["signed_contract_url"],
        "is_won_stage": True,
        "is_lost_stage": False,
        "description": "Đã ký hợp đồng và bắt đầu triển khai",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 6,
        "code": "CLOSED_LOST",
        "name": "Thất bại (Lost)",
        "win_probability": 0.0,
        "order_index": 6,
        "required_exit_fields": ["lost_reason_id"],
        "is_won_stage": False,
        "is_lost_stage": True,
        "description": "Khách hàng từ chối hoặc chọn đối thủ",
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
]

fake_stages_db = copy.deepcopy(INITIAL_PIPELINE_STAGES)

INITIAL_STAGE_RULES = [
    {"id": 1, "stage_id": 1, "rule_name": "Người liên hệ", "field_name": "contact_person", "description": "Cần có người liên hệ đại diện khách hàng", "is_mandatory": True},
    {"id": 2, "stage_id": 1, "rule_name": "Nhu cầu khách hàng", "field_name": "customer_need", "description": "Làm rõ nhu cầu sơ bộ", "is_mandatory": True},
    {"id": 3, "stage_id": 2, "rule_name": "Xác nhận ngân sách", "field_name": "budget_confirmed", "description": "Xác nhận ngân sách dự kiến của khách hàng", "is_mandatory": True},
    {"id": 4, "stage_id": 2, "rule_name": "Người ra quyết định", "field_name": "decision_maker", "description": "Xác định người có thẩm quyền ký duyệt", "is_mandatory": True},
    {"id": 5, "stage_id": 3, "rule_name": "Báo giá cơ hội", "field_name": "quote_id", "description": "Gửi báo giá cho khách hàng", "is_mandatory": True},
    {"id": 6, "stage_id": 3, "rule_name": "Tài liệu giải pháp", "field_name": "solution_document", "description": "Hồ sơ kỹ thuật / giải pháp", "is_mandatory": True},
    {"id": 7, "stage_id": 4, "rule_name": "Dự thảo hợp đồng", "field_name": "contract_draft", "description": "Dự thảo hợp đồng các bên đồng ý", "is_mandatory": True},
    {"id": 8, "stage_id": 4, "rule_name": "Điều khoản thanh toán", "field_name": "payment_terms", "description": "Phương thức thanh toán đã chốt", "is_mandatory": True},
    {"id": 9, "stage_id": 5, "rule_name": "Hợp đồng đã ký", "field_name": "signed_contract_url", "description": "Bản quét hợp đồng đã ký 2 bên", "is_mandatory": True},
    {"id": 10, "stage_id": 6, "rule_name": "Lý do thất bại", "field_name": "lost_reason_id", "description": "Ghi nhận lý do thất bại", "is_mandatory": True},
]

fake_stage_rules_db = copy.deepcopy(INITIAL_STAGE_RULES)


def reset_fake_stages():
    global fake_stages_db, fake_stage_rules_db
    fake_stages_db = copy.deepcopy(INITIAL_PIPELINE_STAGES)
    fake_stage_rules_db = copy.deepcopy(INITIAL_STAGE_RULES)


def get_all_stages() -> List[dict]:
    return sorted(fake_stages_db, key=lambda x: x.get("order_index", 0))


def find_stage(identifier) -> Optional[dict]:
    """Tìm stage theo ID (int hoặc str digit) hoặc Code (str)."""
    if identifier is None:
        return None
    if isinstance(identifier, int):
        return next((s for s in fake_stages_db if s["id"] == identifier), None)
    ident_str = str(identifier).strip()
    if ident_str.isdigit():
        target_id = int(ident_str)
        return next((s for s in fake_stages_db if s["id"] == target_id), None)
    clean_code = ident_str.upper()
    return next((s for s in fake_stages_db if s["code"].upper() == clean_code), None)


def get_stage_by_id(stage_id: int) -> dict:
    stage = find_stage(stage_id)
    if stage:
        return stage
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy giai đoạn pipeline với ID {stage_id}",
    )


def create_stage(stage_in: PipelineStageCreate) -> dict:
    clean_code = stage_in.code.strip().upper()
    if any(s["code"].upper() == clean_code for s in fake_stages_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã giai đoạn '{clean_code}' đã tồn tại",
        )

    next_id = max([s["id"] for s in fake_stages_db], default=0) + 1
    new_stage = {
        "id": next_id,
        "code": clean_code,
        "name": stage_in.name.strip(),
        "win_probability": stage_in.win_probability,
        "order_index": stage_in.order_index,
        "required_exit_fields": stage_in.required_exit_fields,
        "is_won_stage": stage_in.is_won_stage,
        "is_lost_stage": stage_in.is_lost_stage,
        "description": stage_in.description.strip() if stage_in.description else None,
        "created_at": datetime.utcnow(),
    }
    fake_stages_db.append(new_stage)
    return new_stage


def update_stage(stage_id: int, stage_in: PipelineStageUpdate) -> dict:
    stage = next((s for s in fake_stages_db if s["id"] == stage_id), None)
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giai đoạn với ID {stage_id}",
        )

    if stage_in.name is not None:
        stage["name"] = stage_in.name.strip()
    if stage_in.win_probability is not None:
        stage["win_probability"] = stage_in.win_probability
    if stage_in.order_index is not None:
        stage["order_index"] = stage_in.order_index
    if stage_in.required_exit_fields is not None:
        stage["required_exit_fields"] = stage_in.required_exit_fields
    if stage_in.description is not None:
        stage["description"] = stage_in.description.strip()

    return stage


# ============================================================================
# CẤU HÌNH ĐIỀU KIỆN RỜI GIAI ĐOẠN (STAGE RULES - S5-04)
# ============================================================================

def get_stage_rules(stage_id: int) -> List[dict]:
    get_stage_by_id(stage_id)  # validate stage exists
    return [r for r in fake_stage_rules_db if r["stage_id"] == stage_id]


def add_stage_rule(stage_id: int, rule_in: dict) -> dict:
    stage = get_stage_by_id(stage_id)
    field_name = rule_in["field_name"].strip()
    rule_name = rule_in["rule_name"].strip()

    next_id = max([r["id"] for r in fake_stage_rules_db], default=0) + 1
    new_rule = {
        "id": next_id,
        "stage_id": stage_id,
        "rule_name": rule_name,
        "field_name": field_name,
        "description": rule_in.get("description"),
        "is_mandatory": rule_in.get("is_mandatory", True),
        "created_at": datetime.utcnow(),
    }
    fake_stage_rules_db.append(new_rule)

    # Đảm bảo field_name cũng nằm trong required_exit_fields của stage
    if field_name not in stage.get("required_exit_fields", []):
        stage.setdefault("required_exit_fields", []).append(field_name)

    return new_rule


def delete_stage_rule(stage_id: int, rule_id: int) -> bool:
    global fake_stage_rules_db
    get_stage_by_id(stage_id)
    rule = next((r for r in fake_stage_rules_db if r["id"] == rule_id and r["stage_id"] == stage_id), None)
    if not rule:
        return False
    fake_stage_rules_db = [r for r in fake_stage_rules_db if not (r["id"] == rule_id and r["stage_id"] == stage_id)]
    return True


def check_transition_criteria(from_stage_id, to_stage_id, opportunity_data: dict) -> dict:
    """
    AC S2-09 & S5-04: Kiểm tra điều kiện cần đạt (exit criteria) trước khi chuyển giai đoạn.
    """
    current_stage = find_stage(from_stage_id)
    if not current_stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giai đoạn nguồn với ID/Code: {from_stage_id}",
        )

    target_stage = find_stage(to_stage_id)
    if not target_stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giai đoạn đích với ID/Code: {to_stage_id}",
        )

    # Tổng hợp tất cả các trường/điều kiện bắt buộc của current_stage
    required_fields = set(current_stage.get("required_exit_fields", []))
    for r in fake_stage_rules_db:
        if r["stage_id"] == current_stage["id"] and r.get("is_mandatory", True):
            required_fields.add(r["field_name"])

    missing = []
    for field_name in sorted(required_fields):
        if field_name in ("has_products", "products"):
            has_prod = opportunity_data.get("has_products") or bool(opportunity_data.get("products"))
            if not has_prod:
                missing.append(field_name)
        else:
            val = opportunity_data.get(field_name)
            if val is None or val == "" or val is False:
                missing.append(field_name)

    if missing:
        return {
            "can_transition": False,
            "missing_fields": missing,
            "message": f"Không thể chuyển sang giai đoạn '{target_stage['name']}'. Vui lòng hoàn thành các thông tin bắt buộc của giai đoạn '{current_stage['name']}': {', '.join(missing)}",
        }

    return {
        "can_transition": True,
        "missing_fields": [],
        "message": f"Đủ điều kiện chuyển từ '{current_stage['name']}' sang '{target_stage['name']}'.",
    }


def validate_and_execute_stage_transition(
    opportunity: dict,
    target_stage_identifier,
    current_user: dict,
    override: bool = False,
    override_reason: Optional[str] = None,
    extra_opportunity_data: Optional[dict] = None,
) -> dict:
    """
    AC S5-04:
    - Không cho chuyển giai đoạn nếu chưa đủ điều kiện.
    - Thông báo rõ điều kiện còn thiếu.
    - Trưởng nhóm trở lên (MANAGER, ADMIN) có thể ghi đè và phải nhập lý do.
    """
    current_stage_code = opportunity.get("stage", "PROSPECTING")
    current_stage = find_stage(current_stage_code)
    target_stage = find_stage(target_stage_identifier)

    if not target_stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Giai đoạn đích '{target_stage_identifier}' không tồn tại trong hệ thống",
        )

    # Nếu trùng giai đoạn hiện tại thì không cần kiểm tra điều kiện rời giai đoạn
    if current_stage and current_stage["code"] == target_stage["code"]:
        return {
            "success": True,
            "previous_stage": current_stage_code,
            "current_stage": target_stage["code"],
            "overridden": False,
            "override_reason": None,
            "override_by": None,
            "message": f"Cơ hội đang ở giai đoạn '{target_stage['name']}'.",
        }

    # Kết hợp dữ liệu hiện tại của cơ hội và dữ liệu cập nhật mới
    combined_data = dict(opportunity)
    if extra_opportunity_data:
        combined_data.update(extra_opportunity_data)

    from_stage_id = current_stage["id"] if current_stage else 1
    to_stage_id = target_stage["id"]
    check_result = check_transition_criteria(from_stage_id, to_stage_id, combined_data)

    if not check_result["can_transition"]:
        missing_fields = check_result["missing_fields"]
        current_stage_name = current_stage["name"] if current_stage else current_stage_code
        target_stage_name = target_stage["name"]

        # Nếu chưa đủ điều kiện, kiểm tra cơ chế ghi đè
        if override:
            # Kiểm tra quyền: Chỉ Trưởng nhóm (MANAGER) hoặc Quản trị viên (ADMIN)
            user_role = (current_user.get("role") or "").upper()
            if user_role not in ("ADMIN", "MANAGER"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ Trưởng nhóm (MANAGER) hoặc Quản trị viên (ADMIN) mới có quyền ghi đè điều kiện chuyển giai đoạn",
                )

            # Phải có lý do ghi đè
            clean_reason = (override_reason or "").strip()
            if not clean_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vui lòng nhập lý do ghi đè khi chuyển giai đoạn",
                )

            # Thực hiện ghi đè thành công
            opportunity["stage"] = target_stage["code"]
            opportunity["stage_overridden"] = True
            opportunity["override_reason"] = clean_reason
            opportunity["override_by"] = current_user.get("id")
            opportunity["override_by_name"] = current_user.get("full_name") or current_user.get("username")
            opportunity["overridden_at"] = datetime.utcnow().isoformat()

            return {
                "success": True,
                "previous_stage": current_stage_code,
                "current_stage": target_stage["code"],
                "overridden": True,
                "override_reason": clean_reason,
                "override_by": current_user.get("id"),
                "message": f"Đã ghi đè chuyển giai đoạn từ '{current_stage_name}' sang '{target_stage_name}' bởi {opportunity['override_by_name']}. Lý do: {clean_reason}",
            }

        # Không dùng ghi đè hoặc chưa bật override -> chặn và thông báo rõ điều kiện còn thiếu
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Không thể chuyển sang giai đoạn '{target_stage_name}'. Chưa thỏa mãn các điều kiện bắt buộc của giai đoạn '{current_stage_name}': {', '.join(missing_fields)}",
                "missing_requirements": missing_fields,
                "current_stage": current_stage_code,
                "target_stage": target_stage["code"],
            },
        )

    # Đủ điều kiện chuyển giai đoạn bình thường
    opportunity["stage"] = target_stage["code"]
    opportunity["stage_overridden"] = False
    opportunity["override_reason"] = None
    opportunity["override_by"] = None

    return {
        "success": True,
        "previous_stage": current_stage_code,
        "current_stage": target_stage["code"],
        "overridden": False,
        "override_reason": None,
        "override_by": None,
        "message": f"Chuyển thành công sang giai đoạn '{target_stage['name']}'.",
    }

