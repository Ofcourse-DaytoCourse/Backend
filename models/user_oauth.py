from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Text
from sqlalchemy.sql import func
from models.base import Base
import uuid

class UserOAuth(Base):
    __tablename__ = "user_oauth"
    
    oauth_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    provider_type = Column(String(20), nullable=False)      # "kakao", "google", "naver"
    provider_user_id = Column(String(255), nullable=False)  # 각 제공자별 사용자 ID
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True))
