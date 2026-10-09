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


def reset_fake_stages():
    global fake_stages_db
    fake_stages_db = copy.deepcopy(INITIAL_PIPELINE_STAGES)


def get_all_stages() -> List[dict]:
    return sorted(fake_stages_db, key=lambda x: x.get("order_index", 0))


def get_stage_by_id(stage_id: int) -> dict:
    for s in fake_stages_db:
        if s["id"] == stage_id:
            return s
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


def check_transition_criteria(from_stage_id: int, to_stage_id: int, opportunity_data: dict) -> dict:
    """
    AC S2-09: Ràng buộc chuyển giai đoạn - Kiểm tra điều kiện cần đạt (exit criteria)
    trước khi cho phép cơ hội chuyển sang giai đoạn kế tiếp.
    """
    current_stage = get_stage_by_id(from_stage_id)
    target_stage = get_stage_by_id(to_stage_id)

    # Nếu nhảy từ giai đoạn này sang giai đoạn khác (tiến tới), kiểm tra các required_exit_fields của current_stage
    missing = []
    for field_name in current_stage.get("required_exit_fields", []):
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
