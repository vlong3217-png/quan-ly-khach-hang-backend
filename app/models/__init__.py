"""Models package."""
from app.models.user import Base, User
from app.models.customer import Customer, CustomerMergeHistory
from app.models.opportunity import (
    Opportunity,
    OpportunityProduct,
    OpportunityModel,
    OpportunityProductModel,
    OpportunityHistoryModel,
    OpportunitySavedFilterModel,
    OpportunityShareModel,
    OpportunityAttachmentModel,
)
from app.models.activity import Activity, ActivityModel, TaskModel, NotificationModel
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
__all__ = [
    "Base",
    "User",
    "Customer",
    "CustomerMergeHistory",
    "Opportunity",
    "OpportunityProduct",
    "OpportunityModel",
    "OpportunityProductModel",
    "OpportunityHistoryModel",
    "OpportunitySavedFilterModel",
    "OpportunityShareModel",
    "OpportunityAttachmentModel",
    "Activity",
    "ActivityModel",
    "TaskModel",
    "NotificationModel",
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
]

from app.models.email_marketing import EmailTemplate, EmailLog

from app.models.notification_preference import NotificationPreference


from app.models.sales_quota import SalesQuota, SalesQuotaAuditLog

