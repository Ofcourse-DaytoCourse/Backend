from sqlalchemy import Column, BigInteger, String, Boolean, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from models.base import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    session_title = Column(String(200), nullable=True)
    session_status = Column(String(20), nullable=False, server_default="ACTIVE")
    is_active = Column(Boolean, nullable=False, server_default="true")
    messages = Column(JSON, nullable=True, server_default='[]')
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_activity_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
