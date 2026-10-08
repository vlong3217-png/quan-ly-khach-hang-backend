import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Thông tin cấu hình MySQL
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "vu123456")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "crm_db")

encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

raw_db_url = os.getenv("DATABASE_URL")
connect_args = {}

if raw_db_url:
    if raw_db_url.startswith("sqlite"):
        DATABASE_URL = raw_db_url
        connect_args = {"check_same_thread": False}
        engine = create_engine(
            DATABASE_URL,
            connect_args=connect_args,
        )
    else:
        # Chuẩn hóa scheme mysql:// -> mysql+pymysql://
        if raw_db_url.startswith("mysql://"):
            raw_db_url = raw_db_url.replace("mysql://", "mysql+pymysql://", 1)

        # Xử lý các query param từ Aiven / Cloud provider (đặc biệt là ?ssl-mode=REQUIRED)
        parsed = urllib.parse.urlsplit(raw_db_url)
        qs = urllib.parse.parse_qsl(parsed.query)
        filtered_params = []
        use_ssl = False

        for k, v in qs:
            # Aiven gửi ?ssl-mode=REQUIRED nhưng PyMySQL chỉ nhận connect_args={'ssl': ...}
            if k.lower() in ("ssl-mode", "ssl_mode"):
                use_ssl = True
            else:
                filtered_params.append((k, v))

        if use_ssl:
            # PyMySQL bật SSL mode an toàn
            connect_args["ssl"] = {"check_hostname": False}

        DATABASE_URL = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(filtered_params), parsed.fragment)
        )
        engine = create_engine(
            DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
        )
else:
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
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
