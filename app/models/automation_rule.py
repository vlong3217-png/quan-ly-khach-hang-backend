"""SQLAlchemy models for Automation Workflow Rules (S7-09 EP-09)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.models.user import Base


class AutomationRuleModel(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    trigger_event = Column(String(64), nullable=False, index=True)  # OPPORTUNITY_STAGE_CHANGED, LEAD_STATUS_CHANGED, QUOTE_STATUS_CHANGED
    conditions = Column(JSON, nullable=True)  # e.g. {"to_stage": "PROPOSAL", "min_value": 50000000}
    actions = Column(JSON, nullable=False)  # list of actions: CREATE_TASK, SEND_NOTIFICATION, CHANGE_OWNER
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AutomationExecutionLogModel(Base):
    __tablename__ = "automation_execution_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_id = Column(Integer, index=True, nullable=False)
    rule_name = Column(String(255), nullable=False)
    trigger_event = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)  # OPPORTUNITY, LEAD, QUOTE, TASK
    entity_id = Column(Integer, nullable=False)
    entity_name = Column(String(255), nullable=True)
    status = Column(String(20), default="SUCCESS")  # SUCCESS, FAILED, SKIPPED
    actions_executed = Column(JSON, nullable=True)
    message = Column(Text, nullable=True)
    executed_at = Column(DateTime, server_default=func.now(), index=True)
