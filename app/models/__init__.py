"""Models package."""
from app.models.user import Base, User
from app.models.customer import Customer, CustomerMergeHistory
from app.models.opportunity import (
    Opportunity,
    OpportunityProduct,
    OpportunityModel,
    OpportunityProductModel,
)
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
from app.models.campaign import Campaign
from app.models.contract import Contract, ContractModel, ContractItemModel
from app.models.pdf_template import PDFTemplate, PDFTemplateModel
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
    "Campaign",
    "Contract",
    "ContractModel",
    "ContractItemModel",
    "PDFTemplate",
    "PDFTemplateModel",
]
