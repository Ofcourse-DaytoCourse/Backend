from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

# SMS 처리 관련 Enum 클래스
class ProcessingStatus(str, Enum):
    """SMS 처리 상태"""
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"

class UnmatchedStatus(str, Enum):
    """미매칭 입금 상태"""
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    IGNORED = "ignored"

class BalanceChangeType(str, Enum):
    """잔액 변경 타입"""
    CHARGE = "charge"
    USAGE = "usage"
    REFUND = "refund"
    ADMIN_ADJUST = "admin_adjust"

# SmsLog 스키마
class SmsLogCreate(BaseModel):
    """SMS 로그 생성 스키마"""
    raw_message: str
    parsed_data: Optional[Dict[str, Any]] = None
    parsed_amount: Optional[int] = None
    parsed_name: Optional[str] = None
    parsed_time: Optional[datetime] = None
    processing_status: ProcessingStatus = ProcessingStatus.RECEIVED
    error_message: Optional[str] = None
    
    @validator('raw_message')
    def validate_raw_message(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('SMS 메시지 내용이 필요합니다')
        if len(v) > 1000:
            raise ValueError('SMS 메시지가 너무 깁니다')
        return v.strip()
    
    @validator('parsed_amount')
    def validate_parsed_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('파싱된 금액은 0보다 커야 합니다')
        return v
    
    @validator('parsed_name')
    def validate_parsed_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        if v is not None and len(v) > 50:
            raise ValueError('입금자명이 너무 깁니다')
        return v.strip() if v else None

class SmsLogResponse(BaseModel):
    """SMS 로그 응답 스키마"""
    sms_log_id: int
    raw_message: str
    parsed_data: Optional[Dict[str, Any]] = None
    parsed_amount: Optional[int] = None
    parsed_name: Optional[str] = None
    parsed_time: Optional[datetime] = None
    processing_status: ProcessingStatus
    matched_deposit_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # 계산된 필드
    is_processed: bool = False
    is_failed: bool = False
    is_matched: bool = False
    
    class Config:
        orm_mode = True
        use_enum_values = True

class SmsLogUpdate(BaseModel):
    """SMS 로그 업데이트 스키마"""
    processing_status: Optional[ProcessingStatus] = None
    matched_deposit_id: Optional[int] = None
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True

# SMS 파싱 관련 스키마
class SmsParseRequest(BaseModel):
    """SMS 파싱 요청 스키마 (외부 API용)"""
    raw_message: str
    sender: Optional[str] = None
    received_at: Optional[datetime] = None
    
    @validator('raw_message')
    def validate_raw_message(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('SMS 메시지가 필요합니다')
        return v.strip()

class SmsParseResponse(BaseModel):
    """SMS 파싱 응답 스키마"""
    success: bool
    message: str
    sms_log_id: Optional[int] = None
    matched_deposit_id: Optional[int] = None
    parsed_amount: Optional[int] = None
    parsed_name: Optional[str] = None
    charge_completed: bool = False
    
class SmsParsedData(BaseModel):
    """SMS 파싱 결과 스키마"""
    amount: Optional[int] = None
    deposit_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    transaction_time: Optional[datetime] = None
    balance: Optional[int] = None
    raw_text: str
    
    @validator('amount')
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('금액은 0보다 커야 합니다')
        return v

# UnmatchedDeposit 스키마
class UnmatchedDepositResponse(BaseModel):
    """미매칭 입금 응답 스키마"""
    unmatched_deposit_id: int
    raw_message: str
    parsed_amount: Optional[int] = None
    parsed_name: Optional[str] = None
    parsed_time: Optional[datetime] = None
    status: UnmatchedStatus
    created_at: datetime
    expires_at: datetime
    matched_user_id: Optional[str] = None
    matched_at: Optional[datetime] = None
    
    # 계산된 필드
    is_expired: bool = False
    is_matched: bool = False
    days_until_expiry: int = 0
    
    class Config:
        orm_mode = True
        use_enum_values = True

class UnmatchedDepositList(BaseModel):
    """미매칭 입금 목록 응답 스키마"""
    total: int
    items: list[UnmatchedDepositResponse]
    page: int
    size: int

class ManualMatchRequest(BaseModel):
    """수동 매칭 요청 스키마"""
    unmatched_deposit_id: int
    user_id: str
    confirmed_amount: int
    admin_note: Optional[str] = None
    
    @validator('confirmed_amount')
    def validate_confirmed_amount(cls, v):
        if v <= 0:
            raise ValueError('확인된 금액은 0보다 커야 합니다')
        return v

class ManualMatchResponse(BaseModel):
    """수동 매칭 응답 스키마"""
    success: bool
    message: str
    matched_deposit_id: Optional[int] = None
    charge_history_id: Optional[int] = None
    charged_amount: int = 0

# BalanceChangeLog 스키마
class BalanceChangeLogResponse(BaseModel):
    """잔액 변경 로그 응답 스키마"""
    balance_change_log_id: int
    user_id: str
    change_type: BalanceChangeType
    amount: int
    balance_before: int
    balance_after: int
    reference_table: Optional[str] = None
    reference_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime
    
    # 계산된 필드
    is_charge: bool = False
    is_usage: bool = False
    is_refund: bool = False
    is_admin_adjust: bool = False
    amount_display: str = ""  # 금액 표시형식 (+ 또는 -)
    
    class Config:
        orm_mode = True
        use_enum_values = True

class BalanceChangeLogCreate(BaseModel):
    """잔액 변경 로그 생성 스키마"""
    user_id: str
    change_type: BalanceChangeType
    amount: int
    balance_before: int
    balance_after: int
    reference_table: Optional[str] = None
    reference_id: Optional[int] = None
    description: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v == 0:
            raise ValueError('변경 금액은 0이 될 수 없습니다')
        return v

class BalanceChangeLogList(BaseModel):
    """잔액 변경 로그 목록 응답 스키마"""
    total: int
    items: list[BalanceChangeLogResponse]
    page: int
    size: int
    
    # 통계 정보
    total_charged: int = 0
    total_used: int = 0
    total_refunded: int = 0
    total_admin_adjusted: int = 0

# SMS 통계 스키마
class SmsStatistics(BaseModel):
    """SMS 처리 통계 스키마"""
    total_received: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_matched: int = 0
    total_unmatched: int = 0
    success_rate: float = 0.0
    match_rate: float = 0.0
    
class SmsLogList(BaseModel):
    """SMS 로그 목록 응답 스키마"""
    total: int
    items: list[SmsLogResponse]
    page: int
    size: int
    statistics: Optional[SmsStatistics] = None