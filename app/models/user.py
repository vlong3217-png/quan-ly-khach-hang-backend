from sqlalchemy import Column, Integer, String, Boolean, Text, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(255), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="ADMIN")
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    team_id = Column(Integer, nullable=True)
    status = Column(String(20), default="ACTIVE")
    phone = Column(String(50), nullable=True)
    email_signature = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    monthly_quota = Column(Float, nullable=True, default=0.0)
