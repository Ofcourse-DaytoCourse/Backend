from sqlalchemy import Column, String, JSON, TIMESTAMP
from sqlalchemy.sql import func
from models.base import Base
import uuid


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)  
    nickname = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=True)
    user_status = Column(String(20))
    profile_detail = Column(JSON)
    couple_info = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
