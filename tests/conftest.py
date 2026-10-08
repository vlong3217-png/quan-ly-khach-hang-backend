import os
import pytest

# Thiết lập database SQLite phục vụ cho bộ test chạy nhanh và độc lập
os.environ["DATABASE_URL"] = "sqlite:///./test_crm.db"

from app.core.database import engine
from app.models import Base

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup sau khi chạy xong
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
