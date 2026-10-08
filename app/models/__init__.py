"""Models package."""
from app.models.user import Base, User
from app.models.customer import Customer
from app.models.opportunity import Opportunity
from app.models.activity import Activity
from app.models.quote import Quote
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.contact import Contact, ContactCompanyHistory

__all__ = [
    "Base",
    "User",
    "Customer",
    "Opportunity",
    "Activity",
    "Quote",
    "AuditLog",
    "Product",
    "Contact",
    "ContactCompanyHistory",
]



