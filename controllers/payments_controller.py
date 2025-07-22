# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import asyncio

from crud.crud_deposit import (
    create_deposit_request, get_user_deposit_requests, check_user_rate_limit_deposit
)
from crud.crud_payment import (
    get_user_balance, get_or_create_user_balance, 
    deduct_balance as crud_deduct_balance,
    get_user_charge_histories, get_user_usage_histories, get_payment_statistics
)
from crud.crud_sms import create_balance_change_log
from schemas.deposit_schema import DepositRequestCreate
from schemas.payment_schema import BalanceDeductRequest

# 6.1.1 generate_deposit_name 함수
async def generate_deposit_name(
    db: AsyncSession,
    user_id: str,
    bank_name: str = "국민은행",
    account_number: str = "12345678901234"
) -> Dict[str, Any]:
    """입금자명 생성 비즈니스 로직"""
    
    try:
        # 먼저 기존 활성 요청이 있는지 확인
        from crud.crud_deposit import get_existing_active_request
        existing_request = await get_existing_active_request(db, user_id)
        
        if existing_request:
            # 기존 요청이 있으면 레이트 리미팅 없이 반환
            deposit_request = existing_request
        else:
            # 새 요청 생성 시에만 레이트 리미팅 체크
            if not await check_user_rate_limit_deposit(db, user_id):
                return {
                    "success": False,
                    "message": "입금자명 생성은 1분에 1회만 가능합니다",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            
            # 입금 요청 생성
            deposit_data = DepositRequestCreate(
                bank_name=bank_name,
                account_number=account_number
            )
            
            deposit_request = await create_deposit_request(db, user_id, deposit_data)
        
        # 만료 시간 계산 (분 단위)
        now = datetime.now(timezone.utc)
        if deposit_request.expires_at.tzinfo is None:
            # timezone-naive인 경우 UTC로 설정
            expires_at_utc = deposit_request.expires_at.replace(tzinfo=timezone.utc)
        else:
            # timezone-aware인 경우 UTC로 변환
            expires_at_utc = deposit_request.expires_at.astimezone(timezone.utc)
        expires_in_minutes = int((expires_at_utc - now).total_seconds() / 60)
        
        # 디버깅을 위한 로그
        print(f"DEBUG: now = {now}")
        print(f"DEBUG: expires_at = {deposit_request.expires_at}")
        print(f"DEBUG: expires_at_utc = {expires_at_utc}")
        print(f"DEBUG: expires_in_minutes = {expires_in_minutes}")
        
        return {
            "success": True,
            "message": "입금자명이 생성되었습니다",
            "data": {
                "deposit_request_id": deposit_request.deposit_request_id,
                "deposit_name": deposit_request.deposit_name,
                "amount": deposit_request.amount,
                "bank_name": deposit_request.bank_name,
                "account_number": deposit_request.account_number,
                "expires_at": expires_at_utc.isoformat(),
                "expires_in_minutes": expires_in_minutes
            }
        }
        
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        print(f"DEBUG ERROR TYPE: {type(e)}")
        import traceback
        print(f"DEBUG TRACEBACK: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"입금자명 생성 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.1.2 process_payment 함수
async def process_payment(
    db: AsyncSession,
    user_id: str,
    deposit_request_id: int,
    confirmed_amount: int
) -> Dict[str, Any]:
    """결제 처리 비즈니스 로직"""
    
    try:
        from crud.crud_deposit import get_deposit_request, mark_deposit_completed
        from crud.crud_payment import create_charge_history, update_user_balance
        from schemas.payment_schema import ChargeHistoryCreate, SourceType
        
        # 입금 요청 체크
        deposit_request = await get_deposit_request(db, deposit_request_id)
        if not deposit_request:
            return {
                "success": False,
                "message": "입금 요청을 찾을 수 없습니다",
                "error_code": "DEPOSIT_REQUEST_NOT_FOUND"
            }
        
        if deposit_request.user_id != user_id:
            return {
                "success": False,
                "message": "권한이 없는 입금 요청입니다",
                "error_code": "UNAUTHORIZED"
            }
        
        if deposit_request.status != "pending":
            return {
                "success": False,
                "message": "이미 처리된 입금 요청입니다",
                "error_code": "ALREADY_PROCESSED"
            }
        
        # 만료 체크 제거 - 테이블에서 찾았다면 이미 유효함
        
        # 금액 체크 제거 - 사용자가 원하는 만큼 충전 가능
        # 실제 입금된 금액으로 충전 처리
        
        # 트랜잭션 처리
        # 1. 입금 요청 상태 완료
        await mark_deposit_completed(db, deposit_request_id)
        
        # 2. 충전 내역 생성
        charge_data = ChargeHistoryCreate(
            user_id=user_id,
            deposit_request_id=deposit_request_id,
            amount=confirmed_amount,
            source_type=SourceType.DEPOSIT,
            description=f"입금 처리: {deposit_request.deposit_name}"
        )
        
        charge_history = await create_charge_history(db, charge_data)
        
        # 3. 사용자 잔액 업데이트
        user_balance = await get_or_create_user_balance(db, user_id)
        balance_before = user_balance.total_balance
        
        updated_balance = await update_user_balance(db, user_id, confirmed_amount, True, True)
        
        # 4. 잔액 변경 로그 생성
        await create_balance_change_log(
            db=db,
            user_id=user_id,
            change_type="charge",
            amount=confirmed_amount,
            balance_before=balance_before,
            balance_after=updated_balance.total_balance,
            reference_table="charge_histories",
            reference_id=charge_history.charge_history_id,
            description="입금 처리로 인한 충전"
        )
        
        return {
            "success": True,
            "message": "결제가 성공적으로 처리되었습니다",
            "data": {
                "charge_history_id": charge_history.charge_history_id,
                "charged_amount": confirmed_amount,
                "balance_before": balance_before,
                "balance_after": updated_balance.total_balance,
                "refundable_balance": updated_balance.refundable_balance,
                "non_refundable_balance": updated_balance.non_refundable_balance
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"결제 처리 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.1.3 deduct_balance 함수
async def deduct_balance(
    db: AsyncSession,
    user_id: str,
    deduct_request: BalanceDeductRequest
) -> Dict[str, Any]:
    """잔액 차감 비즈니스 로직"""
    
    try:
        # 사용자 잔액 체크
        user_balance = await get_user_balance(db, user_id)
        if not user_balance:
            return {
                "success": False,
                "message": "사용자 잔액 정보를 찾을 수 없습니다",
                "error_code": "BALANCE_NOT_FOUND"
            }
        
        # 잔액 부족 체크
        if not user_balance.has_sufficient_balance(deduct_request.amount):
            return {
                "success": False,
                "message": f"잔액이 부족합니다. (현재 잔액: {user_balance.total_balance}원)",
                "error_code": "INSUFFICIENT_BALANCE",
                "data": {
                    "current_balance": user_balance.total_balance,
                    "required_amount": deduct_request.amount,
                    "shortage": deduct_request.amount - user_balance.total_balance
                }
            }
        
        # 잔액 차감 및 사용 내역 생성
        updated_balance, usage_history = await crud_deduct_balance(db, user_id, deduct_request)
        
        # 잔액 변경 로그 생성
        await create_balance_change_log(
            db=db,
            user_id=user_id,
            change_type="usage",
            amount=-deduct_request.amount,  # 마이너스 값
            balance_before=user_balance.total_balance,
            balance_after=updated_balance.total_balance,
            reference_table="usage_histories",
            reference_id=usage_history.usage_history_id,
            description=f"서비스 이용: {deduct_request.service_type.value}"
        )
        
        return {
            "success": True,
            "message": "잔액이 차감되었습니다",
            "data": {
                "usage_history_id": usage_history.usage_history_id,
                "deducted_amount": deduct_request.amount,
                "service_type": deduct_request.service_type.value,
                "service_id": deduct_request.service_id,
                "balance_before": user_balance.total_balance,
                "balance_after": updated_balance.total_balance,
                "remaining_balance": updated_balance.total_balance
            }
        }
        
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"잔액 차감 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.1.4 get_payment_history 함수
async def get_payment_history(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    size: int = 10,
    history_type: Optional[str] = None
) -> Dict[str, Any]:
    """결제 히스토리 조회 비즈니스 로직"""
    
    try:
        skip = (page - 1) * size
        
        # 현재 잔액 조회
        user_balance = await get_user_balance(db, user_id)
        if not user_balance:
            user_balance = await get_or_create_user_balance(db, user_id)
        
        # 비동기 작업들 조회
        tasks = []
        
        if not history_type or history_type == "charge":
            tasks.append(get_user_charge_histories(db, user_id, skip, size))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=[])))
        
        if not history_type or history_type == "usage":
            tasks.append(get_user_usage_histories(db, user_id, skip, size))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=[])))
        
        # 통계 정보 조회
        tasks.append(get_payment_statistics(db, user_id))
        
        results = await asyncio.gather(*tasks)
        charge_histories, usage_histories, statistics = results
        
        return {
            "success": True,
            "data": {
                "user_balance": {
                    "total_balance": user_balance.total_balance,
                    "refundable_balance": user_balance.refundable_balance,
                    "non_refundable_balance": user_balance.non_refundable_balance,
                    "updated_at": user_balance.updated_at
                },
                "charge_histories": [
                    {
                        "charge_history_id": ch.charge_history_id,
                        "amount": ch.amount,
                        "refunded_amount": ch.refunded_amount,
                        "is_refundable": ch.is_refundable,
                        "source_type": ch.source_type,
                        "refund_status": ch.refund_status,
                        "refundable_amount": max(0, ch.amount - ch.refunded_amount) if ch.is_refundable else 0,
                        "description": ch.description,
                        "created_at": ch.created_at
                    } for ch in charge_histories
                ],
                "usage_histories": [
                    {
                        "usage_history_id": uh.usage_history_id,
                        "amount": uh.amount,
                        "service_type": uh.service_type,
                        "service_id": uh.service_id,
                        "description": uh.description,
                        "created_at": uh.created_at
                    } for uh in usage_histories
                ],
                "statistics": statistics,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total_charge": len(charge_histories),
                    "total_usage": len(usage_histories)
                }
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"결제 히스토리 조회 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.1.5 트랜잭션 처리 로직
async def process_payment_transaction(
    db: AsyncSession,
    user_id: str,
    transaction_type: str,
    amount: int,
    **kwargs
) -> Dict[str, Any]:
    """결제 트랜잭션 통합 처리"""
    
    try:
        if transaction_type == "deposit":
            # 입금 처리
            return await process_payment(
                db, user_id, kwargs.get("deposit_request_id"), amount
            )
        
        elif transaction_type == "deduct":
            # 차감 처리
            deduct_request = BalanceDeductRequest(
                amount=amount,
                service_type=kwargs.get("service_type"),
                service_id=kwargs.get("service_id"),
                description=kwargs.get("description")
            )
            return await deduct_balance(db, user_id, deduct_request)
        
        else:
            return {
                "success": False,
                "message": "올바르지 않은 트랜잭션 타입입니다",
                "error_code": "INVALID_TRANSACTION_TYPE"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"트랜잭션 처리 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "TRANSACTION_ERROR"
        }

# 6.1.6 비즈니스 로직 헬퍼 - 사용자 함수들
async def get_user_deposit_summary(
    db: AsyncSession,
    user_id: str
) -> Dict[str, Any]:
    """사용자 입금 요약 정보"""
    
    try:
        # 활성 입금 요청 조회
        active_deposits = await get_user_deposit_requests(db, user_id, 0, 5)
        active_deposits = [d for d in active_deposits if d.is_active()]
        
        # 현재 잔액 조회
        user_balance = await get_user_balance(db, user_id)
        
        return {
            "success": True,
            "data": {
                "active_deposit_requests": len(active_deposits),
                "active_deposits": [
                    {
                        "deposit_request_id": d.deposit_request_id,
                        "deposit_name": d.deposit_name,
                        "amount": d.amount,
                        "expires_at": d.expires_at,
                        "is_expired": d.is_expired()
                    } for d in active_deposits
                ],
                "current_balance": user_balance.total_balance if user_balance else 0,
                "refundable_balance": user_balance.refundable_balance if user_balance else 0
            }
        }
        
    except Exception as e:
        print(f"DEBUG get_user_deposit_summary ERROR: {str(e)}")
        print(f"DEBUG ERROR TYPE: {type(e)}")
        import traceback
        print(f"DEBUG TRACEBACK: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"입금 요약 조회 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

def calculate_review_reward(review_data: dict) -> int:
    """후기 타입에 따른 크레딧 계산 (환불 불가능)"""
    has_text = review_data.get('review_text') and len(review_data['review_text'].strip()) > 0
    has_photos = review_data.get('photo_urls') and len(review_data['photo_urls']) > 0
    
    if has_text and has_photos:
        return 500  # 평점 + 텍스트 + 사진
    elif has_text:
        return 300  # 평점 + 텍스트
    else:
        return 100  # 평점만

async def process_review_credit(user_id: str, review_data: dict, db: AsyncSession) -> Dict[str, Any]:
    """후기 작성 크레딧 지급 (환불 불가능 잔액으로)"""
    try:
        amount = calculate_review_reward(review_data)
        
        # 기존 UserBalance 모델 활용
        user_balance = await get_or_create_user_balance(db, user_id)
        
        # 환불 불가능 잔액으로 추가
        user_balance.add_balance(amount, is_refundable=False)
        
        # 충전 히스토리 기록
        from models.payment import ChargeHistory
        charge_history = ChargeHistory(
            user_id=user_id,
            amount=amount,
            source_type="review_reward",
            description=f"후기 작성 보상 ({amount}원)",
            is_refundable=False
            # updated_at은 자동으로 설정됨 (명시적으로 None 전달하지 않음)
        )
        db.add(charge_history)
        
        await db.commit()
        
        return {
            "success": True,
            "amount": amount,
            "message": f"후기 작성 보상 {amount}원이 지급되었습니다"
        }
        
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "amount": 0,
            "message": f"크레딧 지급 실패: {str(e)}"
        }

async def validate_payment_amount(amount: int) -> Dict[str, Any]:
    """결제 금액 검증"""
    
    if amount <= 0:
        return {
            "valid": False,
            "message": "결제 금액은 0보다 커야 합니다"
        }
    
    return {
        "valid": True,
        "message": "올바른 결제 금액입니다"
    }