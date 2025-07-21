from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from enum import Enum

# 환불 관련 Enum 클래스 (payment_schema.py에서 사용하는 것과 중복 방지)
class RefundRequestStatus(str, Enum):
    """환불 요청 상태"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

class RefundStatus(str, Enum):
    """환불 상태"""
    AVAILABLE = "available"
    PARTIALLY_REFUNDED = "partially_refunded"
    FULLY_REFUNDED = "fully_refunded"
    UNAVAILABLE = "unavailable"

# 환불 요청 스키마
class RefundRequestCreate(BaseModel):
    """환불 요청 생성 스키마 (새로운 시스템)"""
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
        if v < 1000:
            raise ValueError('최소 환불 금액은 1,000원입니다')
        if v > 1000000:
            raise ValueError('최대 단일 환불 가능 금액은 1,000,000원입니다')
        return v
    
    @validator('bank_name')
    def validate_bank_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('은행명이 필요합니다')
        if len(v.strip()) > 50:
            raise ValueError('은행명은 50자를 초과할 수 없습니다')
        return v.strip()
    
    @validator('account_number')
    def validate_account_number(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('계좌번호가 필요합니다')
        # 계좌번호 형식 검증 (숫자와 하이픈 허용)
        import re
        if not re.match(r'^[\d\-]+$', v.strip()):
            raise ValueError('계좌번호는 숫자와 하이픈(-)만 포함할 수 있습니다')
        if len(v.strip()) > 50:
            raise ValueError('계좌번호는 50자를 초과할 수 없습니다')
        return v.strip()
    
    @validator('account_holder')
    def validate_account_holder(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('예금주 이름이 필요합니다')
        if len(v.strip()) > 50:
            raise ValueError('예금주 이름은 50자를 초과할 수 없습니다')
        return v.strip()
    
    @validator('contact')
    def validate_contact(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('연락처가 필요합니다')
        # 전화번호 형식 검증 (숫자와 하이픈 허용)
        import re
        if not re.match(r'^[\d\-]+$', v.strip()):
            raise ValueError('연락처는 숫자와 하이픈(-)만 포함할 수 있습니다')
        if len(v.strip()) > 20:
            raise ValueError('연락처는 20자를 초과할 수 없습니다')
        return v.strip()
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('환불 사유가 필요합니다')
        if len(v.strip()) < 10:
            raise ValueError('환불 사유는 최소 10자 이상 필요합니다')
        if len(v.strip()) > 500:
            raise ValueError('환불 사유는 500자를 초과할 수 없습니다')
        return v.strip()

class RefundRequestResponse(BaseModel):
    """환불 요청 응답 스키마 (새로운 시스템)"""
    refund_request_id: int
    user_id: str
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
    
    # 계산된 필드
    is_pending: bool = False
    is_approved: bool = False
    is_completed: bool = False
    days_since_request: int = 0
    
    class Config:
        from_attributes = True
        use_enum_values = True

class RefundRequestUpdate(BaseModel):
    """환불 요청 업데이트 스키마 (관리자용)"""
    status: Optional[RefundRequestStatus] = None
    admin_memo: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    @validator('admin_memo')
    def validate_admin_memo(cls, v):
        if v is not None and len(v.strip()) > 1000:
            raise ValueError('관리자 메모는 1000자를 초과할 수 없습니다')
        return v.strip() if v else None
    
    class Config:
        use_enum_values = True

class RefundRequestList(BaseModel):
    """환불 요청 목록 응답 스키마"""
    total: int
    items: list[RefundRequestResponse]
    page: int
    size: int
    
    # 통계 정보
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    completed_count: int = 0

# 환불 가능 금액 조회 스키마
class RefundableAmountResponse(BaseModel):
    """환불 가능 금액 응답 스키마"""
    charge_history_id: int
    original_amount: int
    refunded_amount: int
    refundable_amount: int
    is_refundable: bool
    refund_status: RefundStatus
    has_pending_request: bool = False
    pending_request_amount: int = 0
    
    # 충전 이력 정보
    charge_date: datetime
    source_type: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True

class RefundableHistoryResponse(BaseModel):
    """환불 가능한 충전 이력 목록 응답"""
    user_id: str
    total_refundable_amount: int
    refundable_histories: list[RefundableAmountResponse]

# 관리자용 환불 승인/거부 스키마
class RefundApprovalRequest(BaseModel):
    """환불 승인 요청 스키마"""
    action: str  # "approve" 또는 "reject"
    admin_memo: Optional[str] = None
    
    @validator('action')
    def validate_action(cls, v):
        if v not in ['approve', 'reject']:
            raise ValueError('action은 approve 또는 reject만 가능합니다')
        return v
    
    @validator('admin_memo')
    def validate_admin_memo(cls, v):
        if v is not None and len(v.strip()) > 1000:
            raise ValueError('관리자 메모는 1000자를 초과할 수 없습니다')
        return v.strip() if v else None

class RefundApprovalResponse(BaseModel):
    """환불 승인 응답 스키마"""
    success: bool
    message: str
    refund_request_id: int
    new_status: RefundRequestStatus
    processed_at: datetime
    refunded_amount: int = 0
    remaining_balance: int = 0
    
    class Config:
        use_enum_values = True

# 환불 통계 스키마
class RefundStatistics(BaseModel):
    """환불 통계 스키마"""
    total_requests: int = 0
    pending_requests: int = 0
    approved_requests: int = 0
    rejected_requests: int = 0
    completed_requests: int = 0
    
    total_requested_amount: int = 0
    total_approved_amount: int = 0
    total_completed_amount: int = 0
    
    approval_rate: float = 0.0
    completion_rate: float = 0.0
    average_processing_days: float = 0.0

# 환불 내역 조회 스키마
class RefundHistoryResponse(BaseModel):
    """환불 내역 응답 스키마"""
    refund_requests: list[RefundRequestResponse]
    statistics: RefundStatistics
    page: int
    size: int
    total: int

# 부분 환불 관련 스키마
class PartialRefundInfo(BaseModel):
    """부분 환불 정보 스키마"""
    charge_history_id: int
    original_amount: int
    total_refunded: int
    available_for_refund: int
    refund_history: list[RefundRequestResponse]
    
    can_request_more: bool = True
    max_additional_refund: int = 0

class BulkRefundRequest(BaseModel):
    """대량 환불 요청 스키마 (관리자용)"""
    refund_request_ids: list[int]
    action: str  # "approve" 또는 "reject"
    admin_memo: Optional[str] = None
    
    @validator('refund_request_ids')
    def validate_refund_request_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError('환불 요청 ID가 필요합니다')
        if len(v) > 100:
            raise ValueError('최대 대량 처리 가능 건수는 100건입니다')
        return v
    
    @validator('action')
    def validate_action(cls, v):
        if v not in ['approve', 'reject']:
            raise ValueError('action은 approve 또는 reject만 가능합니다')
        return v

class BulkRefundResponse(BaseModel):
    """대량 환불 처리 응답 스키마"""
    total_processed: int
    successful_count: int
    failed_count: int
    successful_ids: list[int]
    failed_results: list[dict]
    total_refunded_amount: int = 0