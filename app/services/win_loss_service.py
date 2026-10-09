import copy
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status

from app.schemas.win_loss import (
    CloseOpportunityValidationRequest,
    CompetitorCreate,
    CompetitorUpdate,
    ReasonCreate,
    ReasonType,
    ReasonUpdate,
)

INITIAL_REASONS = [
    # WIN REASONS
    {
        "id": 1,
        "reason_type": "WIN",
        "code": "WIN_PRODUCT_FIT",
        "name": "Tính năng sản phẩm đáp ứng hoàn hảo nhu cầu",
        "requires_competitor": False,
        "is_active": True,
        "sort_order": 1,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "reason_type": "WIN",
        "code": "WIN_PRICE",
        "name": "Giá cả cạnh tranh và chính sách ưu đãi tốt",
        "requires_competitor": False,
        "is_active": True,
        "sort_order": 2,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 3,
        "reason_type": "WIN",
        "code": "WIN_REPUTATION",
        "name": "Uy tín thương hiệu & Dịch vụ hỗ trợ tốt",
        "requires_competitor": False,
        "is_active": True,
        "sort_order": 3,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    # LOSS REASONS
    {
        "id": 4,
        "reason_type": "LOSS",
        "code": "LOSS_COMPETITOR_PRICE",
        "name": "Đối thủ cạnh tranh có giá thấp hơn",
        "requires_competitor": True,  # Bắt buộc khai báo đối thủ
        "is_active": True,
        "sort_order": 1,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 5,
        "reason_type": "LOSS",
        "code": "LOSS_COMPETITOR_FEATURE",
        "name": "Đối thủ có tính năng vượt trội",
        "requires_competitor": True,  # Bắt buộc khai báo đối thủ
        "is_active": True,
        "sort_order": 2,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 6,
        "reason_type": "LOSS",
        "code": "LOSS_BUDGET_CANCELLED",
        "name": "Khách hàng hoãn hoặc cắt giảm ngân sách đầu tư",
        "requires_competitor": False,
        "is_active": True,
        "sort_order": 3,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
]

INITIAL_COMPETITORS = [
    {
        "id": 1,
        "code": "COMP_GLOBAL_A",
        "name": "Tập đoàn Phần mềm Quốc tế A",
        "strengths": "Thương hiệu toàn cầu, tính năng phong phú",
        "weaknesses": "Giá rất đắt, hỗ trợ bản địa chậm",
        "pricing_strategy": "Cao cấp",
        "is_active": True,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
    {
        "id": 2,
        "code": "COMP_LOCAL_B",
        "name": "Công ty Giải pháp Nội địa B",
        "strengths": "Giá rẻ, quy trình triển khai nhanh",
        "weaknesses": "Hệ thống ít ổn định, thiếu bảo mật cao",
        "pricing_strategy": "Giá rẻ",
        "is_active": True,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
    },
]

fake_reasons_db = copy.deepcopy(INITIAL_REASONS)
fake_competitors_db = copy.deepcopy(INITIAL_COMPETITORS)


def reset_fake_win_loss():
    global fake_reasons_db, fake_competitors_db
    fake_reasons_db = copy.deepcopy(INITIAL_REASONS)
    fake_competitors_db = copy.deepcopy(INITIAL_COMPETITORS)


# ================= REASONS SERVICE =================

def get_reasons(reason_type: Optional[str] = None, active_only: bool = False) -> List[dict]:
    results = fake_reasons_db
    if reason_type:
        rt = reason_type.upper()
        results = [r for r in results if r["reason_type"] == rt]
    if active_only:
        results = [r for r in results if r.get("is_active", True)]
    return sorted(results, key=lambda x: (x.get("sort_order", 0), x["id"]))


def get_reason_by_id(reason_id: int) -> dict:
    for r in fake_reasons_db:
        if r["id"] == reason_id:
            return r
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy lý do với ID {reason_id}",
    )


def create_reason(reason_in: ReasonCreate) -> dict:
    clean_code = reason_in.code.strip().upper()
    rt = reason_in.reason_type.value

    if any(r["reason_type"] == rt and r["code"].upper() == clean_code for r in fake_reasons_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã lý do '{clean_code}' đã tồn tại trong nhóm {rt}",
        )

    next_id = max([r["id"] for r in fake_reasons_db], default=0) + 1
    new_reason = {
        "id": next_id,
        "reason_type": rt,
        "code": clean_code,
        "name": reason_in.name.strip(),
        "requires_competitor": reason_in.requires_competitor,
        "is_active": reason_in.is_active,
        "sort_order": reason_in.sort_order,
        "created_at": datetime.utcnow(),
    }
    fake_reasons_db.append(new_reason)
    return new_reason


def update_reason(reason_id: int, reason_in: ReasonUpdate) -> dict:
    reason = next((r for r in fake_reasons_db if r["id"] == reason_id), None)
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lý do với ID {reason_id}",
        )

    if reason_in.name is not None:
        reason["name"] = reason_in.name.strip()
    if reason_in.requires_competitor is not None:
        reason["requires_competitor"] = reason_in.requires_competitor
    if reason_in.is_active is not None:
        reason["is_active"] = reason_in.is_active
    if reason_in.sort_order is not None:
        reason["sort_order"] = reason_in.sort_order

    return reason


def delete_reason(reason_id: int) -> dict:
    reason = next((r for r in fake_reasons_db if r["id"] == reason_id), None)
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lý do với ID {reason_id}",
        )
    fake_reasons_db.remove(reason)
    return {
        "success": True,
        "message": f"Đã xoá lý do '{reason['name']}' thành công.",
    }


# ================= COMPETITORS SERVICE =================

def get_competitors(active_only: bool = False) -> List[dict]:
    results = fake_competitors_db
    if active_only:
        results = [c for c in results if c.get("is_active", True)]
    return sorted(results, key=lambda x: x["id"])


def get_competitor_by_id(comp_id: int) -> dict:
    for c in fake_competitors_db:
        if c["id"] == comp_id:
            return c
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy đối thủ cạnh tranh với ID {comp_id}",
    )


def create_competitor(comp_in: CompetitorCreate) -> dict:
    clean_code = comp_in.code.strip().upper()
    if any(c["code"].upper() == clean_code for c in fake_competitors_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã đối thủ '{clean_code}' đã tồn tại",
        )

    next_id = max([c["id"] for c in fake_competitors_db], default=0) + 1
    new_comp = {
        "id": next_id,
        "code": clean_code,
        "name": comp_in.name.strip(),
        "strengths": comp_in.strengths.strip() if comp_in.strengths else None,
        "weaknesses": comp_in.weaknesses.strip() if comp_in.weaknesses else None,
        "pricing_strategy": comp_in.pricing_strategy.strip() if comp_in.pricing_strategy else None,
        "is_active": comp_in.is_active,
        "created_at": datetime.utcnow(),
    }
    fake_competitors_db.append(new_comp)
    return new_comp


def update_competitor(comp_id: int, comp_in: CompetitorUpdate) -> dict:
    comp = next((c for c in fake_competitors_db if c["id"] == comp_id), None)
    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đối thủ với ID {comp_id}",
        )

    if comp_in.name is not None:
        comp["name"] = comp_in.name.strip()
    if comp_in.strengths is not None:
        comp["strengths"] = comp_in.strengths.strip()
    if comp_in.weaknesses is not None:
        comp["weaknesses"] = comp_in.weaknesses.strip()
    if comp_in.pricing_strategy is not None:
        comp["pricing_strategy"] = comp_in.pricing_strategy.strip()
    if comp_in.is_active is not None:
        comp["is_active"] = comp_in.is_active

    return comp


def delete_competitor(comp_id: int) -> dict:
    comp = next((c for c in fake_competitors_db if c["id"] == comp_id), None)
    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đối thủ với ID {comp_id}",
        )
    fake_competitors_db.remove(comp)
    return {
        "success": True,
        "message": f"Đã xoá đối thủ '{comp['name']}' thành công.",
    }


# ================= VALIDATION FOR CLOSING OPPORTUNITY =================

def validate_close_opportunity(req: CloseOpportunityValidationRequest) -> dict:
    """
    AC S2-10: Khi đóng cơ hội (Won/Lost):
    - Bắt buộc phải chọn Lý do tương ứng (Win reason nếu Won, Loss reason nếu Lost).
    - Nếu lý do đó cấu hình requires_competitor = True, bắt buộc phải chọn Competitor.
    """
    status_upper = req.status.strip().upper()
    if status_upper not in {"WON", "LOST"}:
        return {
            "is_valid": False,
            "message": "Trạng thái đóng chỉ có thể là WON hoặc LOST",
        }

    reason = next((r for r in fake_reasons_db if r["id"] == req.reason_id), None)
    if not reason:
        return {
            "is_valid": False,
            "message": f"Không tìm thấy lý do với ID {req.reason_id}",
        }

    # Kiểm tra loại lý do có khớp trạng thái không
    expected_type = "WIN" if status_upper == "WON" else "LOSS"
    if reason["reason_type"] != expected_type:
        return {
            "is_valid": False,
            "message": f"Lý do '{reason['name']}' thuộc loại {reason['reason_type']}, không phù hợp với trạng thái đóng {status_upper}",
        }

    # Kiểm tra ràng buộc đối thủ cạnh tranh
    if reason.get("requires_competitor", False):
        if not req.competitor_id:
            return {
                "is_valid": False,
                "message": f"Lý do '{reason['name']}' bắt buộc phải khai báo đối thủ cạnh tranh cụ thể.",
            }
        comp = next((c for c in fake_competitors_db if c["id"] == req.competitor_id), None)
        if not comp:
            return {
                "is_valid": False,
                "message": f"Không tìm thấy đối thủ cạnh tranh với ID {req.competitor_id}",
            }

    return {
        "is_valid": True,
        "message": "Dữ liệu đóng cơ hội hợp lệ.",
    }
