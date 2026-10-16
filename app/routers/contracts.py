"""
Contract API Router with role-based access control and quote conversion (S7-04).
"""

import math
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.services.pdf_template_service import get_template_by_id, get_default_template
from app.services.pdf_generator_service import generate_contract_pdf

from app.core.database import get_db
from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.contract import (
    ContractConvertRequest,
    ContractGenerateNumberResponse,
    ContractListResponse,
    ContractResponse,
)
from app.services.contract_service import (
    convert_quote_to_contract,
    generate_unique_contract_number,
    get_contract_by_id,
    get_contract_by_quote_id,
    get_contracts_by_scope,
)

router = APIRouter(
    prefix="/contracts",
    tags=["Contracts"],
)


@router.get("/generate-number", response_model=ContractGenerateNumberResponse)
def get_suggested_contract_number(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Tự động sinh số hợp đồng gợi ý duy nhất theo ngày (S7-04 AC 4).
    Định dạng: HD-YYYYMMDD-XXX
    """
    suggested = generate_unique_contract_number(db=db)
    return {"suggested_contract_number": suggested}


@router.post("/from-quote/{quote_id}", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def convert_quote_to_contract_endpoint(
    quote_id: int,
    payload: ContractConvertRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "ACCOUNTANT", "DIRECTOR", "MANAGER"], detail="Chỉ Kế toán, Giám đốc hoặc Quản trị viên mới có quyền chuyển báo giá thành hợp đồng (S7-04)")),
    db: Session = Depends(get_db),
):
    """
    Chuyển một báo giá được chấp nhận thành hợp đồng (S7-04):
    - AC 1: Kế thừa 100% dòng sản phẩm và các giá trị tài chính đã chốt.
    - AC 2: Khai báo số hợp đồng, ngày ký, ngày hiệu lực, ngày hết hạn, điều khoản thanh toán.
    - AC 3: Tự động chuyển cơ hội tương ứng sang Đóng thắng (CLOSED_WON) với giá trị bằng đúng giá trị hợp đồng.
    - AC 4: Kiểm tra tính duy nhất của số hợp đồng.
    """
    return convert_quote_to_contract(
        quote_id=quote_id,
        data=payload.model_dump(),
        current_user=current_user,
        db=db,
    )


@router.get("/by-quote/{quote_id}", response_model=ContractResponse)
def get_contract_by_quote(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tra cứu hợp đồng đã được sinh từ một báo giá."""
    contract = get_contract_by_quote_id(quote_id, db=db)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chưa có hợp đồng nào được tạo từ báo giá ID {quote_id}",
        )
    return contract


@router.get("", response_model=ContractListResponse)
def list_contracts(
    scope: Optional[str] = Query(None, description="Data scope filter: MY, MY_TEAM, TEAM, hoặc ALL"),
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái hợp đồng (ACTIVE, EXPIRED, TERMINATED)"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm (số HĐ, tiêu đề, khách hàng)"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng hợp đồng mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy danh sách hợp đồng theo quyền hạn (DataScope) và phân trang."""
    effective_scope = resolve_scope(current_user, scope)
    all_contracts = get_contracts_by_scope(
        current_user=current_user,
        scope=effective_scope,
        search=search,
        customer_id=customer_id,
        status_filter=status,
        db=db,
    )
    total = len(all_contracts)

    effective_limit = limit if limit is not None else 20
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_contracts[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "contracts": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xem chi tiết một hợp đồng kèm các dòng sản phẩm và điều khoản."""
    contract = get_contract_by_id(contract_id, db=db)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng",
        )

    if not check_scope_access(current_user, contract["owner_id"], contract.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu hợp đồng này",
        )

    return contract


@router.get("/{contract_id}/export-pdf")
def export_contract_pdf(
    contract_id: int,
    template_id: Optional[int] = Query(None, description="ID của mẫu PDF cần áp dụng (nếu bỏ trống sẽ lấy mẫu mặc định)"),
    preview: bool = Query(False, description="True để xem trực tiếp (inline), False để tải về (attachment)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Xuất hợp đồng ra file PDF theo mẫu công ty (S7-05 AC 1 & AC 2):
    - Đầy đủ thông tin pháp lý, các bên A và B, dòng sản phẩm, tổng tiền bằng số và bằng chữ.
    - Tùy biến mẫu theo template_id hoặc mẫu mặc định.
    """
    contract = get_contract_by_id(contract_id, db=db)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng để xuất PDF",
        )

    if not check_scope_access(current_user, contract["owner_id"], contract.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu hợp đồng này",
        )

    # Lấy mẫu PDF cấu hình
    if template_id is not None:
        template = get_template_by_id(template_id, db=db)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy mẫu PDF với ID {template_id}",
            )
    else:
        template = get_default_template("CONTRACT", db=db)

    pdf_bytes = generate_contract_pdf(contract, template)
    c_num = contract.get("contract_number") or f"HD_{contract_id}"
    filename = f"Hop_Dong_{c_num}.pdf"
    disposition = "inline" if preview else f'attachment; filename="{filename}"'

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "X-Report-Template-Id": str(template.get("id", 1)),
        },
    )
