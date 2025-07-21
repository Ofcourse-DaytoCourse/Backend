from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index, CheckConstraint, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class SmsLog(Base):
    """SMS 로그 테이블 - 은행 SMS 메시지 파싱 및 매칭 결과 저장"""
    __tablename__ = "sms_logs"

    # 2.3.1 SmsLog 컬럼 정의
    sms_log_id = Column(Integer, primary_key=True, index=True)
    raw_message = Column(Text, nullable=False)
    parsed_data = Column(JSONB)
    parsed_amount = Column(Integer, index=True)
    parsed_name = Column(String(50), index=True)
    parsed_time = Column(TIMESTAMP(timezone=True), index=True)
    processing_status = Column(String(20), default="received", nullable=False, index=True)
    matched_deposit_id = Column(Integer, ForeignKey("deposit_requests.deposit_request_id", ondelete="SET NULL"), index=True)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    # 관계 설정
    matched_deposit = relationship("DepositRequest", back_populates="sms_logs")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint("processing_status IN ('received', 'processed', 'failed', 'ignored')", name='chk_sms_processing_status_valid'),
        
        # 중복 SMS 방지 UNIQUE 제약조건
        Index('unique_sms_entry', 'parsed_amount', 'parsed_name', 'parsed_time', unique=True),
        
        # 인덱스 설정
        Index('idx_sms_logs_processing_status', 'processing_status'),
        Index('idx_sms_logs_parsed_name', 'parsed_name'),
        Index('idx_sms_logs_parsed_amount', 'parsed_amount'),
        Index('idx_sms_logs_parsed_time', 'parsed_time'),
        Index('idx_sms_logs_matched_deposit_id', 'matched_deposit_id'),
        Index('idx_sms_logs_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<SmsLog(id={self.sms_log_id}, parsed_amount={self.parsed_amount}, parsed_name={self.parsed_name}, processing_status={self.processing_status})>"

    def is_processed(self):
        """성공적으로 처리된 SMS인지 확인"""
        return self.processing_status == 'processed'

    def is_failed(self):
        """처리에 실패한 SMS인지 확인"""
        return self.processing_status == 'failed'

    def is_matched(self):
        """매칭에 성공한 SMS인지 확인"""
        return self.matched_deposit_id is not None


class UnmatchedDeposit(Base):
    """미매칭 입금 테이블 - SMS 파싱 후 매칭에 실패한 입금 내역 저장"""
    __tablename__ = "unmatched_deposits"

    # 2.3.2 UnmatchedDeposit 컬럼 정의
    unmatched_deposit_id = Column(Integer, primary_key=True, index=True)
    raw_message = Column(Text, nullable=False)
    parsed_amount = Column(Integer, index=True)
    parsed_name = Column(String(50), index=True)
    parsed_time = Column(TIMESTAMP(timezone=True), index=True)
    status = Column(String(20), default="unmatched", nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), server_default=func.text("CURRENT_TIMESTAMP + INTERVAL '180 days'"), index=True)
    matched_user_id = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    matched_at = Column(TIMESTAMP(timezone=True))

    # 관계 설정
    matched_user = relationship("User", back_populates="unmatched_deposits")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint("status IN ('unmatched', 'matched', 'ignored')", name='chk_unmatched_status_valid'),
        
        # 인덱스 설정
        Index('idx_unmatched_deposits_status', 'status'),
        Index('idx_unmatched_deposits_parsed_name', 'parsed_name'),
        Index('idx_unmatched_deposits_parsed_amount', 'parsed_amount'),
        Index('idx_unmatched_deposits_parsed_time', 'parsed_time'),
        Index('idx_unmatched_deposits_expires_at', 'expires_at'),
        Index('idx_unmatched_deposits_created_at', 'created_at'),
        Index('idx_unmatched_deposits_matched_user_id', 'matched_user_id'),
    )

    def __repr__(self):
        return f"<UnmatchedDeposit(id={self.unmatched_deposit_id}, parsed_amount={self.parsed_amount}, parsed_name={self.parsed_name}, status={self.status})>"

    def is_expired(self):
        """만료된 미매칭 입금인지 확인 (6개월 후 자동 삭제)"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

    def is_matched(self):
        """매칭된 입금인지 확인"""
        return self.status == 'matched'


class BalanceChangeLog(Base):
    """잔액 변경 로그 테이블 - 모든 잔액 변경 사항 로그 (감사 추적용)"""
    __tablename__ = "balance_change_logs"

    # 2.3.3 BalanceChangeLog 컬럼 정의
    balance_change_log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    change_type = Column(String(20), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reference_table = Column(String(50), index=True)
    reference_id = Column(Integer, index=True)
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)

    # 관계 설정
    user = relationship("User", back_populates="balance_change_logs")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint("change_type IN ('charge', 'usage', 'refund', 'admin_adjust')", name='chk_balance_change_type_valid'),
        
        # 인덱스 설정
        Index('idx_balance_change_logs_user_id', 'user_id'),
        Index('idx_balance_change_logs_change_type', 'change_type'),
        Index('idx_balance_change_logs_reference_table', 'reference_table'),
        Index('idx_balance_change_logs_reference_id', 'reference_id'),
        Index('idx_balance_change_logs_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<BalanceChangeLog(id={self.balance_change_log_id}, user_id={self.user_id}, change_type={self.change_type}, amount={self.amount}, balance_before={self.balance_before}, balance_after={self.balance_after})>"

    def is_charge(self):
        """충전 로그인지 확인"""
        return self.change_type == 'charge'

    def is_usage(self):
        """사용 로그인지 확인"""
        return self.change_type == 'usage'

    def is_refund(self):
        """환불 로그인지 확인"""
        return self.change_type == 'refund'

    def is_admin_adjust(self):
        """관리자 조정 로그인지 확인"""
        return self.change_type == 'admin_adjust'

# 2.3.4-2.3.6 모든 컬럼 및 관계 설정, 제약조건 및 인덱스 설정, 비즈니스 로직 메서드 완료