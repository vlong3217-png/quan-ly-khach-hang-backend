import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.models.user import Base


class LeadSourceConfig(Base):
    """
    Cấu hình biểu mẫu nhúng Web-to-Lead (S4-01).
    Mỗi biểu mẫu có một form_key/mã nhúng duy nhất, tên nguồn (utm_source/source_name)
    và danh sách các trường hiển thị, cấu hình chống spam.
    """
    __tablename__ = "lead_forms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    form_key = Column(String(64), unique=True, index=True, nullable=False, default=lambda: uuid.uuid4().hex[:16])
    name = Column(String(255), nullable=False)
    source_name = Column(String(100), nullable=False, default="Website Form")  # Nguồn gắn vào lead
    description = Column(Text, nullable=True)
    target_url = Column(String(500), nullable=True)  # URL website nhúng form
    is_active = Column(Boolean, default=True, nullable=False)
    rate_limit_per_minute = Column(Integer, default=5, nullable=False)  # Giới hạn số submit / IP / phút
    created_by = Column(Integer, nullable=True)  # User ID người tạo biểu mẫu
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Lead(Base):
    """
    Bảng quản lý khách hàng tiềm năng (Lead) - S4-01.
    Thu thập từ biểu mẫu nhúng trên website hoặc các nguồn khác.
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True, index=True)
    company = Column(String(255), nullable=True)
    interest = Column(Text, nullable=True)  # Nhu cầu quan tâm
    source = Column(String(100), nullable=False, default="Website Form", index=True)
    status = Column(String(50), nullable=False, default="NEW", index=True)  # Mới (NEW), Đang xử lý (IN_PROGRESS), Đạt (QUALIFIED), Hủy (DISQUALIFIED)
    form_key = Column(String(64), nullable=True, index=True)  # Mã biểu mẫu nếu tạo từ web-to-lead
    ip_address = Column(String(64), nullable=True)
    owner_id = Column(Integer, nullable=True)  # Phân bổ cho nhân viên nào (nếu có)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
