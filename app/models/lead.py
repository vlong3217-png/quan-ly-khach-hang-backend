import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
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
    Bảng quản lý khách hàng tiềm năng (Lead) - Hỗ trợ S4-01, S4-02, S4-03, S4-04, S4-05, S4-06.
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)  # Tương thích S4-02
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    company = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)  # Tương thích S4-02
    title = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    interest = Column(Text, nullable=True)  # Nhu cầu quan tâm
    source = Column(String(100), nullable=False, default="Hội thảo", index=True)  # Bắt buộc có nguồn (S4-02)
    status = Column(String(50), nullable=False, default="NEW", index=True)  # NEW, CONTACTED, QUALIFIED, CONVERTED, MERGED...
    campaign_id = Column(Integer, nullable=True, index=True)  # S4-03: Liên kết chiến dịch
    customer_id = Column(Integer, nullable=True, index=True)  # S4-04: Liên kết khách hàng
    notes = Column(Text, nullable=True)
    merged_into_id = Column(Integer, nullable=True)  # S4-04: ID lead chính khi gộp
    form_key = Column(String(64), nullable=True, index=True)  # S4-01: Mã biểu mẫu nếu tạo từ web-to-lead
    ip_address = Column(String(64), nullable=True)
    owner_id = Column(Integer, nullable=True)  # Phân bổ cho nhân viên nào (nếu có)
    team_id = Column(Integer, nullable=True)

    # Lead Scoring (S4-05)
    score = Column(Integer, default=0, nullable=False, index=True)
    grade = Column(String(20), default="COLD", nullable=False, index=True)  # HOT, WARM, COLD
    industry = Column(String(100), nullable=True, index=True)
    company_size = Column(String(100), nullable=True)
    budget = Column(Float, nullable=True)
    job_title = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    score_details = Column(Text, nullable=True)  # JSON lưu danh sách rule đã áp dụng
    last_scored_at = Column(DateTime, nullable=True)

    # Lead Allocation (S4-06)
    allocation_status = Column(String(50), default="UNASSIGNED", nullable=False, index=True)  # UNASSIGNED, QUEUED, ASSIGNED
    allocated_at = Column(DateTime, nullable=True)
    allocation_rule_id = Column(Integer, nullable=True)
    allocation_method = Column(String(50), nullable=True)  # ROUND_ROBIN, SPECIFIC_USER, REGION, INDUSTRY, MANUAL
    allocation_note = Column(String(500), nullable=True)

    # Lead Conversion (S4-08)
    converted_customer_id = Column(Integer, nullable=True)
    converted_opportunity_id = Column(Integer, nullable=True)
    converted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeadScoringRule(Base):
    """
    Quy tắc chấm điểm Lead theo tiêu chí khai báo được (S4-05).
    """
    __tablename__ = "lead_scoring_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    field_name = Column(String(50), nullable=False)  # industry, company_size, source, budget, job_title, phone, email, interest, city
    operator = Column(String(30), nullable=False, default="EQUALS")  # EQUALS, NOT_EQUALS, CONTAINS, NOT_EMPTY, IS_EMPTY, GREATER_THAN, LESS_THAN, IN
    target_value = Column(String(255), nullable=True)
    points = Column(Integer, nullable=False, default=10)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeadScoringSetting(Base):
    """
    Cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh (S4-05).
    """
    __tablename__ = "lead_scoring_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hot_threshold = Column(Integer, default=50, nullable=False)   # Điểm >= 50: Nóng (HOT)
    warm_threshold = Column(Integer, default=20, nullable=False)  # Điểm >= 20 và < 50: Ấm (WARM), < 20: Lạnh (COLD)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeadAllocationRule(Base):
    """
    Cấu hình quy tắc phân bổ lead tự động (S4-06).
    """
    __tablename__ = "lead_allocation_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=1, nullable=False, index=True)  # Thứ tự ưu tiên (1 = cao nhất)
    criterion_type = Column(String(50), nullable=False)  # REGION, INDUSTRY, SOURCE, ANY
    criterion_value = Column(String(255), nullable=True)  # Giá trị khớp (VD: Hà Nội, Đà Nẵng / Công nghệ thông tin)
    allocation_method = Column(String(50), nullable=False, default="ROUND_ROBIN")  # ROUND_ROBIN, SPECIFIC_USER, REGION, INDUSTRY
    assignee_user_ids = Column(Text, nullable=False)  # JSON list of user_ids: "[3, 4, 5]"
    last_assigned_index = Column(Integer, default=-1, nullable=False)  # Con trỏ xoay vòng
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeadAllocationLog(Base):
    """
    Nhật ký phân bổ lead tự động và thủ công (S4-06).
    """
    __tablename__ = "lead_allocation_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False, index=True)
    rule_id = Column(Integer, nullable=True)
    rule_name = Column(String(255), nullable=True)
    allocation_method = Column(String(50), nullable=False)  # ROUND_ROBIN, SPECIFIC_USER, REGION, INDUSTRY, MANUAL
    assigned_to = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False)  # SUCCESS, QUEUED, MANUAL
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class LeadMergeHistory(Base):
    """
    Lịch sử gộp Lead (S4-04).
    """
    __tablename__ = "lead_merge_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    primary_lead_id = Column(Integer, nullable=False, index=True)
    secondary_lead_id = Column(Integer, nullable=False, index=True)
    secondary_lead_name = Column(String(255), nullable=True)
    secondary_snapshot = Column(Text, nullable=True)  # JSON snapshot trước khi gộp
    merged_by = Column(String(100), nullable=True)
    merged_at = Column(DateTime, server_default=func.now())
