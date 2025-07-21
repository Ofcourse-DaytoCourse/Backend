from sqlalchemy import Column, String, JSON, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

    # 2.5.1 기존 User 모델과 관계 설정 - 결제 시스템 관계 추가
    # 입금 관련 관계
    deposit_requests = relationship("DepositRequest", back_populates="user")
    
    # 결제 관련 관계
    charge_histories = relationship("ChargeHistory", back_populates="user")
    usage_histories = relationship("UsageHistory", back_populates="user")
    user_balance = relationship("UserBalance", back_populates="user", uselist=False)
    refund_requests = relationship("RefundRequest", back_populates="user")
    
    # SMS 관련 관계
    unmatched_deposits = relationship("UnmatchedDeposit", back_populates="matched_user")
    balance_change_logs = relationship("BalanceChangeLog", back_populates="user")
    
    # 레이트 리미팅 관계
    rate_limit_logs = relationship("RateLimitLog", back_populates="user")
