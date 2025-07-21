# -*- coding: utf-8 -*-
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from enum import Enum

# 결제 관련 Enum 정의
class SourceType(str, Enum):
    """충전 소스 타입"""
    DEPOSIT = "deposit"
    BONUS = "bonus"
    REFUND = "refund"
    ADMIN = "admin"

class RefundStatus(str, Enum):
    """환불 상태"""
    AVAILABLE = "available"
    PARTIALLY_REFUNDED = "partially_refunded"
    FULLY_REFUNDED = "fully_refunded"
    UNAVAILABLE = "unavailable"

class ServiceType(str, Enum):
    """서비스 타입"""
    COURSE_GENERATION = "course_generation"
    PREMIUM_FEATURE = "premium_feature"
    CHAT_SERVICE = "chat_service"
    OTHER = "other"

class RefundRequestStatus(str, Enum):
    """환불 요청 상태"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

# ChargeHistory 스키마
class ChargeHistoryCreate(BaseModel):
    """충전 내역 생성 스키마"""
    user_id: str
    deposit_request_id: Optional[int] = None
    amount: int
    is_refundable: bool = True
    source_type: SourceType = SourceType.DEPOSIT
    description: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('충전 금액은 0보다 커야 합니다')
        return v

class ChargeHistoryResponse(BaseModel):
    """충전 내역 응답 스키마"""
    charge_history_id: int
    user_id: str
    deposit_request_id: Optional[int] = None
    amount: int
    refunded_amount: int
    is_refundable: bool
    source_type: SourceType
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    refund_status: RefundStatus
    
    # 계산된 필드
    refundable_amount: int = 0
    is_fully_refunded: bool = False
    
    class Config:
        orm_mode = True
        use_enum_values = True

# UsageHistory 스키마
class UsageHistoryCreate(BaseModel):
    """사용 내역 생성 스키마"""
    user_id: str
    amount: int
    service_type: ServiceType
    service_id: Optional[str] = None
    description: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('사용 금액은 0보다 커야 합니다')
        return v

class UsageHistoryResponse(BaseModel):
    """사용 내역 응답 스키마"""
    usage_history_id: int
    user_id: str
    amount: int
    service_type: ServiceType
    service_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        use_enum_values = True

# UserBalance 스키마
class UserBalanceResponse(BaseModel):
    """사용자 잔액 응답 스키마"""
    balance_id: int
    user_id: str
    total_balance: int
    refundable_balance: int
    non_refundable_balance: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # 추가 정보
    has_balance: bool = False
    
    class Config:
        orm_mode = True

class BalanceDeductRequest(BaseModel):
    """잔액 차감 요청 스키마"""
    amount: int
    service_type: ServiceType
    service_id: Optional[str] = None
    description: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('차감 금액은 0보다 커야 합니다')
        return v

class BalanceAddRequest(BaseModel):
    """잔액 추가 요청 스키마"""
    amount: int
    is_refundable: bool = True
    source_type: SourceType = SourceType.ADMIN
    description: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('추가 금액은 0보다 커야 합니다')
        return v

# RefundRequest 스키마
class RefundRequestCreate(BaseModel):
    """환불 요청 생성 스키마"""
    charge_history_id: int
    bank_name: str
    account_number: str
    account_holder: str
    refund_amount: int
    contact: str
    reason: str
    
    @validator('refund_amount')
    def validate_refund_amount(cls, v):
        if v <= 0:
            raise ValueError('환불 금액은 0보다 커야 합니다')
        return v
    
    @validator('bank_name')
    def validate_bank_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('은행명을 입력해주세요')
        return v.strip()
    
    @validator('account_number')
    def validate_account_number(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('계좌번호를 입력해주세요')
        # 계좌번호 형식 검증 (숫자와 하이픈만 허용)
        import re
        if not re.match(r'^[\d\-]+$', v.strip()):
            raise ValueError('계좌번호는 숫자와 하이픈(-)만 입력 가능합니다')
        return v.strip()
    
    @validator('account_holder')
    def validate_account_holder(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('계좌 소유자명을 입력해주세요')
        return v.strip()
    
    @validator('contact')
    def validate_contact(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('연락처를 입력해주세요')
        # 전화번호 형식 검증 (숫자와 하이픈만 허용)
        import re
        if not re.match(r'^[\d\-]+$', v.strip()):
            raise ValueError('연락처는 숫자와 하이픈(-)만 입력 가능합니다')
        return v.strip()
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('환불 사유를 입력해주세요')
        if len(v.strip()) < 10:
            raise ValueError('환불 사유는 최소 10자 이상 입력해주세요')
        return v.strip()

class RefundRequestResponse(BaseModel):
    """환불 요청 응답 스키마"""
    refund_request_id: int
    user_id: str
    charge_history_id: int
    bank_name: str
    account_number: str
    account_holder: str
    refund_amount: int
    contact: str
    reason: str
    status: RefundRequestStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    admin_memo: Optional[str] = None
    
    # 관련 충전 내역 정보
    charge_history: Optional[ChargeHistoryResponse] = None
    
    class Config:
        orm_mode = True
        use_enum_values = True

class RefundRequestUpdate(BaseModel):
    """환불 요청 수정 스키마 (관리자용)"""
    status: Optional[RefundRequestStatus] = None
    admin_memo: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True

# 결제 히스토리 조회용 스키마
class PaymentHistoryResponse(BaseModel):
    """결제 히스토리 통합 응답 스키마"""
    user_balance: UserBalanceResponse
    charge_histories: list[ChargeHistoryResponse]
    usage_histories: list[UsageHistoryResponse]
    refund_requests: list[RefundRequestResponse]
    
    # 통계 정보
    total_charged: int = 0
    total_used: int = 0
    total_refunded: int = 0

class RefundableAmountResponse(BaseModel):
    """환불 가능 금액 응답 스키마"""
    charge_history_id: int
    original_amount: int
    refunded_amount: int
    refundable_amount: int
    is_refundable: bool
    refund_status: RefundStatus
    has_pending_request: bool = False
    
    class Config:
        use_enum_values = True

# 페이지네이션 스키마
class PaymentHistoryListResponse(BaseModel):
    """결제 히스토리 목록 응답 스키마"""
    total_charge: int
    total_usage: int
    total_refund: int
    charge_histories: list[ChargeHistoryResponse]
    usage_histories: list[UsageHistoryResponse]
    page: int
    size: int