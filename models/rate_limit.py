from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class RateLimitLog(Base):
    """레이트 리미팅 테이블 - API 호출 빈도 제한 및 스팸 방지"""
    __tablename__ = "rate_limit_logs"

    # 2.4.1 RateLimitLog 컬럼 정의
    rate_limit_log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # 'deposit_generate', 'refund_request', 'balance_deduct'
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), server_default=func.text("CURRENT_TIMESTAMP + INTERVAL '24 hours'"), index=True)

    # 2.4.2 외래키 관계 설정
    user = relationship("User", back_populates="rate_limit_logs")

    # 2.4.3 인덱스 설정
    __table_args__ = (
        # 빠른 조회를 위한 복합 인덱스 (레이트 리미팅 확인용)
        Index('idx_rate_limit_user_action', 'user_id', 'action_type', 'created_at'),
        Index('idx_rate_limit_expires', 'expires_at'),
        Index('idx_rate_limit_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<RateLimitLog(id={self.rate_limit_log_id}, user_id={self.user_id}, action_type={self.action_type}, created_at={self.created_at})>"

    def is_expired(self):
        """레이트 리미팅 로그 만료 여부 확인 (24시간 후 자동 삭제)"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

    def is_deposit_generate(self):
        """입금자명 생성 레이트 리미팅 로그인지 확인"""
        return self.action_type == 'deposit_generate'

    def is_refund_request(self):
        """환불 요청 레이트 리미팅 로그인지 확인"""
        return self.action_type == 'refund_request'

    def is_balance_deduct(self):
        """잔액 차감 레이트 리미팅 로그인지 확인"""
        return self.action_type == 'balance_deduct'

# 2.4.4 모델 검증 테스트 완료