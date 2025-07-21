# -*- coding: utf-8 -*-
from pydantic import BaseModel, validator
from typing import Optional, List
from enum import Enum

class ManualChargeTargetType(str, Enum):
    """수동 충전 대상 타입"""
    ALL_USERS = "all_users"      # 전체 사용자
    SINGLE_USER = "single_user"  # 개별 사용자

class ManualChargeRequest(BaseModel):
    """관리자 수동 충전 요청 스키마"""
    target_type: ManualChargeTargetType
    nickname: Optional[str] = None  # single_user일 때 필수
    amount: int
    is_refundable: bool = True
    description: Optional[str] = None
    
    @validator('nickname')
    def validate_nickname(cls, v, values):
        target_type = values.get('target_type')
        if target_type == ManualChargeTargetType.SINGLE_USER:
            if not v or len(v.strip()) == 0:
                raise ValueError('개별 사용자 선택 시 닉네임은 필수입니다')
        return v.strip() if v else None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('충전 금액은 0보다 커야 합니다')
        if v > 1000000:  # 100만원 제한
            raise ValueError('충전 금액은 100만원을 초과할 수 없습니다')
        return v

class ManualChargeResult(BaseModel):
    """수동 충전 결과"""
    user_id: str
    nickname: str
    amount: int
    is_refundable: bool
    charge_history_id: int
    success: bool
    error_message: Optional[str] = None

class ManualChargeResponse(BaseModel):
    """관리자 수동 충전 응답 스키마"""
    total_users: int
    success_count: int
    failed_count: int
    total_amount: int
    results: List[ManualChargeResult]
    
    class Config:
        orm_mode = True