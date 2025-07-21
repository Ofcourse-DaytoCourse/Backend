# -*- coding: utf-8 -*-
"""
새로운 환불 시스템 스키마
charge_history_id 의존성 제거, 단순한 환불 가능 금액 기반 시스템
"""

from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

# ================================================================
# 1. 환불 가능 금액 스키마
# ================================================================

class RefundAvailableResponse(BaseModel):
    """환불 가능 금액 응답 스키마"""
    user_id: str
    refundable_amount: int
    total_balance: int
    can_request_refund: bool
    message: str

# ================================================================
# 2. 환불 요청 스키마 (새로운 시스템)
# ================================================================

class RefundRequestCreateNew(BaseModel):
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

class RefundRequestResponseNew(BaseModel):
    """환불 요청 응답 스키마 (새로운 시스템)"""
    refund_request_id: int
    user_id: str
    bank_name: str
    account_number: str
    account_holder: str
    refund_amount: int
    contact: str
    reason: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    admin_memo: Optional[str] = None
    
    class Config:
        orm_mode = True

# ================================================================
# 3. 환불 내역 스키마
# ================================================================

class RefundHistoryResponseNew(BaseModel):
    """환불 내역 응답 스키마 (새로운 시스템)"""
    refund_history: list[RefundRequestResponseNew]
    pagination: dict

# ================================================================
# 4. 관리자용 스키마
# ================================================================

class RefundAdminUpdateNew(BaseModel):
    """환불 승인/거부 스키마 (관리자용)"""
    admin_memo: str
    
    @validator('admin_memo')
    def validate_admin_memo(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('관리자 메모가 필요합니다')
        if len(v.strip()) > 1000:
            raise ValueError('관리자 메모는 1000자를 초과할 수 없습니다')
        return v.strip()