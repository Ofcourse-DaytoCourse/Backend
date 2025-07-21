# -*- coding: utf-8 -*-
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from enum import Enum

class DepositStatus(str, Enum):
    """입금 요청 상태"""
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"

class DepositRequestCreate(BaseModel):
    """입금 요청 생성 스키마"""
    bank_name: Optional[str] = "국민은행"
    account_number: Optional[str] = "12345678901234"

class DepositRequestResponse(BaseModel):
    """입금 요청 응답 스키마"""
    deposit_request_id: int
    user_id: str
    deposit_name: str
    amount: Optional[int] = None
    bank_name: str
    account_number: str
    status: DepositStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: datetime
    matched_at: Optional[datetime] = None
    
    # 추가 메서드 필드
    is_expired: bool = False
    is_active: bool = False
    
    class Config:
        orm_mode = True
        use_enum_values = True

class DepositRequestUpdate(BaseModel):
    """입금 요청 수정 스키마"""
    status: Optional[DepositStatus] = None
    matched_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True

class DepositRequestList(BaseModel):
    """입금 요청 목록 응답 스키마"""
    total: int
    items: list[DepositRequestResponse]
    page: int
    size: int
    
class DepositGenerateResponse(BaseModel):
    """입금자명 생성 성공 응답"""
    deposit_request_id: int
    deposit_name: str
    amount: Optional[int] = None
    bank_name: str
    account_number: str
    expires_at: datetime
    expires_in_minutes: int
    
    class Config:
        orm_mode = True

class DepositErrorReport(BaseModel):
    """입금자명 오류 신고 스키마"""
    deposit_request_id: int
    actual_deposit_name: str
    contact: Optional[str] = None
    description: Optional[str] = None
    
    @validator('actual_deposit_name')
    def validate_actual_deposit_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('실제 입금자명을 입력해주세요')
        if len(v) > 20:
            raise ValueError('입금자명은 20자를 초과할 수 없습니다')
        return v.strip()