from sqlalchemy import Column, BigInteger, String, Text, Boolean, Integer, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from models.base import Base

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    total_duration = Column(Integer, nullable=True)
    estimated_cost = Column(Integer, nullable=True)
    is_shared_with_couple = Column(Boolean, nullable=False, server_default="false")
    comments = Column(JSON, nullable=True, server_default="[]")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
