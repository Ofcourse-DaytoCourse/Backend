from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index, CheckConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class ChargeHistory(Base):
    """충전 내역 테이블 - 충전 완료 후 잔액, 환불 가능 여부 저장"""
    __tablename__ = "charge_histories"

    # 2.2.1 ChargeHistory 컬럼 정의
    charge_history_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    deposit_request_id = Column(Integer, ForeignKey("deposit_requests.deposit_request_id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Integer, nullable=False, index=True)
    refunded_amount = Column(Integer, default=0, nullable=False)
    is_refundable = Column(Boolean, nullable=False, default=True, index=True)
    source_type = Column(String(20), nullable=False, default="deposit", index=True)
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    refund_status = Column(String(20), default="available", nullable=False, index=True)

    # 관계 설정
    user = relationship("User", back_populates="charge_histories")
    deposit_request = relationship("DepositRequest", back_populates="charge_histories")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint('amount > 0', name='chk_charge_amount_positive'),
        CheckConstraint('refunded_amount >= 0', name='chk_refunded_amount_positive'),
        CheckConstraint('refunded_amount <= amount', name='chk_refunded_amount_valid'),
        CheckConstraint("source_type IN ('deposit', 'bonus', 'refund', 'admin', 'review_reward')", name='chk_charge_source_type_valid'),
        CheckConstraint("refund_status IN ('available', 'partially_refunded', 'fully_refunded', 'unavailable')", name='chk_refund_status_valid'),
        
        # 인덱스 설정
        Index('idx_charge_histories_user_id', 'user_id'),
        Index('idx_charge_histories_deposit_request_id', 'deposit_request_id'),
        Index('idx_charge_histories_source_type', 'source_type'),
        Index('idx_charge_histories_refund_status', 'refund_status'),
        Index('idx_charge_histories_created_at', 'created_at'),
        Index('idx_charge_histories_is_refundable', 'is_refundable'),
    )

    def __repr__(self):
        return f"<ChargeHistory(id={self.charge_history_id}, user_id={self.user_id}, amount={self.amount}, refunded_amount={self.refunded_amount}, refund_status={self.refund_status})>"

    def get_refundable_amount(self):
        """환불 가능한 금액 반환"""
        if not self.is_refundable or self.refund_status == 'unavailable':
            return 0
        return self.amount - self.refunded_amount

    def is_fully_refunded(self):
        """완전 환불 여부 확인"""
        return self.refunded_amount >= self.amount


class UsageHistory(Base):
    """사용 내역 테이블 - 서비스 사용 시 차감 내역 저장 (과금 기록)"""
    __tablename__ = "usage_histories"

    # 2.2.2 UsageHistory 컬럼 정의
    usage_history_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False, index=True)
    service_type = Column(String(50), nullable=False, index=True)
    service_id = Column(String(50), index=True)
    description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계 설정
    user = relationship("User", back_populates="usage_histories")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint('amount > 0', name='chk_usage_amount_positive'),
        CheckConstraint("service_type IN ('course_generation', 'premium_feature', 'chat_service', 'ai_search', 'other', 'refund')", name='chk_usage_service_type_valid'),
        
        # 인덱스 설정
        Index('idx_usage_histories_user_id', 'user_id'),
        Index('idx_usage_histories_service_type', 'service_type'),
        Index('idx_usage_histories_service_id', 'service_id'),
        Index('idx_usage_histories_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<UsageHistory(id={self.usage_history_id}, user_id={self.user_id}, amount={self.amount}, service_type={self.service_type})>"


class UserBalance(Base):
    """사용자 잔액 테이블 - 사용자 현재 잔액 관리 (환불 가능/불가능 구분)"""
    __tablename__ = "user_balances"

    # 2.2.3 UserBalance 컬럼 정의
    balance_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    total_balance = Column(Integer, nullable=False, default=0, index=True)
    refundable_balance = Column(Integer, nullable=False, default=0)
    non_refundable_balance = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now(), index=True)

    # 관계 설정
    user = relationship("User", back_populates="user_balance")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint('total_balance >= 0', name='chk_total_balance_positive'),
        CheckConstraint('refundable_balance >= 0', name='chk_refundable_balance_positive'),
        CheckConstraint('non_refundable_balance >= 0', name='chk_non_refundable_balance_positive'),
        CheckConstraint('total_balance = refundable_balance + non_refundable_balance', name='chk_balance_consistency'),
        
        # 인덱스 설정
        Index('idx_user_balances_user_id', 'user_id'),
        Index('idx_user_balances_total_balance', 'total_balance'),
        Index('idx_user_balances_updated_at', 'updated_at'),
    )

    def __repr__(self):
        return f"<UserBalance(user_id={self.user_id}, total_balance={self.total_balance}, refundable_balance={self.refundable_balance}, non_refundable_balance={self.non_refundable_balance})>"

    def has_sufficient_balance(self, amount):
        """잔액 충분 여부 확인"""
        return self.total_balance >= amount

    def add_balance(self, amount, is_refundable=True):
        """잔액 추가"""
        if is_refundable:
            self.refundable_balance += amount
        else:
            self.non_refundable_balance += amount
        self.total_balance += amount

    def deduct_balance(self, amount):
        """잔액 차감 (환불 불가능 잔액 먼저 차감)"""
        if not self.has_sufficient_balance(amount):
            raise ValueError("잔액이 부족합니다.")
        
        remaining_amount = amount
        
        # 환불 불가능 잔액 먼저 차감
        if self.non_refundable_balance > 0:
            deduct_from_non_refundable = min(remaining_amount, self.non_refundable_balance)
            self.non_refundable_balance -= deduct_from_non_refundable
            remaining_amount -= deduct_from_non_refundable
        
        # 환불 가능 잔액 차감
        if remaining_amount > 0:
            self.refundable_balance -= remaining_amount
        
        self.total_balance -= amount


class RefundRequest(Base):
    """환불 요청 테이블 - 사용자 환불 요청 관리, 부분 환불 지원"""
    __tablename__ = "refund_requests"

    # 2.2.4 RefundRequest 컬럼 정의
    refund_request_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    bank_name = Column(String(50), nullable=False)
    account_number = Column(String(50), nullable=False)
    account_holder = Column(String(50), nullable=False)
    refund_amount = Column(Integer, nullable=False)
    contact = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    processed_at = Column(TIMESTAMP(timezone=True), index=True)
    admin_memo = Column(Text)

    # 관계 설정
    user = relationship("User", back_populates="refund_requests")

    # 제약조건 및 인덱스 설정
    __table_args__ = (
        # CHECK 제약조건
        CheckConstraint('refund_amount > 0', name='chk_refund_amount_positive'),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'completed')", name='chk_refund_status_valid'),
        
        # 인덱스 설정
        Index('idx_refund_requests_user_id', 'user_id'),
        Index('idx_refund_requests_status', 'status'),
        Index('idx_refund_requests_created_at', 'created_at'),
        Index('idx_refund_requests_processed_at', 'processed_at'),
    )

    def __repr__(self):
        return f"<RefundRequest(id={self.refund_request_id}, user_id={self.user_id}, refund_amount={self.refund_amount}, status={self.status})>"

    def is_pending(self):
        """대기 중인 환불 요청인지 확인"""
        return self.status == 'pending'

    def is_approved(self):
        """승인된 환불 요청인지 확인"""
        return self.status == 'approved'

    def is_completed(self):
        """완료된 환불 요청인지 확인"""
        return self.status == 'completed'

# 2.2.5-2.2.7 모든 컬럼 및 관계 설정, 제약조건 및 인덱스 설정, 비즈니스 로직 메서드 완료