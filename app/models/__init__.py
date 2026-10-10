"""Models package."""
from app.models.user import Base, User
from app.models.customer import Customer, CustomerMergeHistory
from app.models.opportunity import Opportunity, OpportunityProduct
from app.models.activity import Activity
from app.models.quote import Quote
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.contact import Contact, ContactCompanyHistory
from app.models.lead import (
    Lead,
    LeadSourceConfig,
    LeadScoringRule,
    LeadScoringSetting,
    LeadAllocationRule,
    LeadAllocationLog,
    LeadMergeHistory,
    LeadSavedFilter,
)
__all__ = [
    "Base",
    "User",
    "Customer",
    "CustomerMergeHistory",
    "Opportunity",
    "OpportunityProduct",
    "Activity",
    "Quote",
    "AuditLog",
    "Product",
    "Contact",
    "ContactCompanyHistory",
    "Lead",
    "LeadSourceConfig",
    "LeadScoringRule",
    "LeadScoringSetting",
    "LeadAllocationRule",
    "LeadAllocationLog",
    "LeadMergeHistory",
    "LeadSavedFilter",
]
