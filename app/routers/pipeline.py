from typing import List
from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.pipeline import (
    PipelineStageCreate,
    PipelineStageResponse,
    PipelineStageUpdate,
    StageTransitionCheckRequest,
    StageTransitionCheckResponse,
)
from app.services import pipeline_service

router = APIRouter(prefix="/pipeline-stages", tags=["Pipeline Stages Configuration"])


@router.get("", response_model=List[PipelineStageResponse])
def get_pipeline_stages(
    current_user: dict = Depends(get_current_user),
):
    """Xem danh sách các giai đoạn trong quy trình bán hàng pipeline."""
    return pipeline_service.get_all_stages()


@router.get("/{stage_id}", response_model=PipelineStageResponse)
def get_pipeline_stage_detail(
    stage_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết một giai đoạn."""
    return pipeline_service.get_stage_by_id(stage_id)


@router.post("", response_model=PipelineStageResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline_stage(
    stage_in: PipelineStageCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cấu hình pipeline stages")),
):
    """Tạo mới giai đoạn pipeline (tên, xác suất thành công %, exit criteria)."""
    return pipeline_service.create_stage(stage_in)


@router.put("/{stage_id}", response_model=PipelineStageResponse)
def update_pipeline_stage(
    stage_id: int,
    stage_in: PipelineStageUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cập nhật pipeline stages")),
):
    """Cập nhật giai đoạn pipeline."""
    return pipeline_service.update_stage(stage_id, stage_in)


@router.post("/check-transition", response_model=StageTransitionCheckResponse)
def check_stage_transition(
    req: StageTransitionCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Kiểm tra điều kiện chuyển giai đoạn (Exit criteria) dựa trên dữ liệu hiện tại của Opportunity.
    """
    return pipeline_service.check_transition_criteria(
        from_stage_id=req.from_stage_id,
        to_stage_id=req.to_stage_id,
        opportunity_data=req.opportunity_data,
    )
