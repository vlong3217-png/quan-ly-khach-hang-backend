import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus

# Thông tin cấu hình MySQL
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "vu123456")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "crm_db")

# Escape password nếu có ký tự đặc biệt
encoded_password = quote_plus(DB_PASSWORD)

# URL kết nối SQLAlchemy tới MySQL sử dụng pymysql driver
raw_db_url = os.getenv("DATABASE_URL")
if raw_db_url:
    # Nếu Render cung cấp mysql:// thì chuẩn hóa thành mysql+pymysql://
    if raw_db_url.startswith("mysql://"):
        DATABASE_URL = raw_db_url.replace("mysql://", "mysql+pymysql://", 1)
    else:
        DATABASE_URL = raw_db_url
else:
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Tự động ping kiểm tra kết nối còn sống không
    pool_recycle=3600,       # Tái tạo kết nối sau 1 tiếng để tránh timeout
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency cung cấp database session cho FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
