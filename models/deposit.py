from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class DepositRequest(Base):
    """입금 요청 테이블 - 사용자가 충전하기 버튼 클릭 시 고유 입금자명 생성하여 저장"""
    __tablename__ = "deposit_requests"

    # 2.1.2 컬럼 정의 (11개 필드)
    deposit_request_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    deposit_name = Column(String(20), nullable=False, unique=True, index=True)
    amount = Column(Integer, nullable=True, index=True)
    bank_name = Column(String(50), nullable=False, default="국민은행")
    account_number = Column(String(20), nullable=False, default="12345678901234")
    status = Column(String(20), nullable=False, default="pending", index=True)
    
    # 타임스탬프 필드
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    matched_at = Column(TIMESTAMP(timezone=True))

    # 2.1.3 외래키 관계 설정
    user = relationship("User", back_populates="deposit_requests")
    charge_histories = relationship("ChargeHistory", back_populates="deposit_request")
    sms_logs = relationship("SmsLog", back_populates="matched_deposit")

    # 2.1.4 제약조건 설정 & 2.1.5 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint('amount IS NULL OR amount > 0', name='chk_deposit_amount_positive'),
        CheckConstraint("status IN ('pending', 'completed', 'expired', 'failed')", name='chk_deposit_status_valid'),
        
        # 인덱스 설정 (성능 최적화)
        Index('idx_deposit_requests_user_id', 'user_id'),
        Index('idx_deposit_requests_status', 'status'),
        Index('idx_deposit_requests_deposit_name', 'deposit_name'),
        Index('idx_deposit_requests_expires_at', 'expires_at'),
        Index('idx_deposit_requests_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<DepositRequest(id={self.deposit_request_id}, user_id={self.user_id}, deposit_name={self.deposit_name}, amount={self.amount}, status={self.status})>"
    
    def is_expired(self):
        """입금 요청 만료 여부 확인"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_active(self):
        """입금 요청 활성 상태 확인"""
        return self.status == 'pending' and not self.is_expired()

# 2.1.6 모델 검증 테스트 준비 완료