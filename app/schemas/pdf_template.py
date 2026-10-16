"""Pydantic Schemas for PDF Templates (S7-05: PDF Quote & Contract Export)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PDFTemplateBase(BaseModel):
    name: str = Field(..., description="Tên mẫu PDF (ví dụ: Mẫu Báo giá Tiêu chuẩn 2026)")
    template_type: str = Field("QUOTE", description="Loại mẫu: QUOTE (Báo giá) hoặc CONTRACT (Hợp đồng)")
    is_default: bool = Field(False, description="Đặt làm mẫu mặc định cho loại tài liệu này")
    is_active: bool = Field(True, description="Trạng thái kích hoạt mẫu")

    # Company Branding & Identity (AC 1 & AC 2)
    company_name: Optional[str] = Field("CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM", description="Tên công ty phát hành")
    company_tax_code: Optional[str] = Field("0109888999", description="Mã số thuế doanh nghiệp")
    company_address: Optional[str] = Field("Tòa nhà Technosoft, Phố Duy Tân, Cầu Giấy, Hà Nội", description="Địa chỉ trụ sở")
    company_phone: Optional[str] = Field("1900 6868 - 024.3795.8888", description="Số điện thoại / Hotline")
    company_email: Optional[str] = Field("sales@crmvietnam.vn", description="Email liên hệ kinh doanh")
    company_website: Optional[str] = Field("https://crmvietnam.vn", description="Website chính thức")
    company_bank_info: Optional[str] = Field(
        "Số tài khoản: 19036888999018 tại Ngân hàng TMCP Kỹ Thương Việt Nam (Techcombank) - Chi nhánh Thăng Long",
        description="Thông tin tài khoản ngân hàng thụ hưởng"
    )
    logo_url: Optional[str] = Field(None, description="Đường dẫn hoặc base64 logo công ty")

    # Visual Style
    primary_color: str = Field("#1E40AF", description="Mã màu chủ đạo (Hex code)")
    secondary_color: str = Field("#F3F4F6", description="Mã màu phụ / màu nền header bảng")

    # Document contents
    header_title: Optional[str] = Field(None, description="Tiêu đề văn bản (để trống sẽ tự động lấy theo loại)")
    terms_and_conditions: Optional[str] = Field(None, description="Điều khoản và quy định thanh toán mặc định")
    footer_text: Optional[str] = Field("Cảm ơn Quý khách hàng đã tin tưởng và đồng hành cùng chúng tôi!", description="Lời kết ở chân trang")
    signature_customer_label: Optional[str] = Field("ĐẠI DIỆN KHÁCH HÀNG", description="Tiêu đề ô ký của khách hàng")
    signature_company_label: Optional[str] = Field("ĐẠI DIỆN CÔNG TY", description="Tiêu đề ô ký của công ty")


class PDFTemplateCreate(PDFTemplateBase):
    pass


class PDFTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    company_name: Optional[str] = None
    company_tax_code: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    company_website: Optional[str] = None
    company_bank_info: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    header_title: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    footer_text: Optional[str] = None
    signature_customer_label: Optional[str] = None
    signature_company_label: Optional[str] = None


class PDFTemplateResponse(PDFTemplateBase):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PDFTemplateListResponse(BaseModel):
    total: int
    templates: List[PDFTemplateResponse]
