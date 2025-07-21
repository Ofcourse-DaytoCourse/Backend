# -*- coding: utf-8 -*-
"""
새로운 환불 시스템 CRUD 함수들
charge_history_id 의존성 제거, 단순한 환불 가능 금액 기반 시스템
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime, timezone
from models.payment import RefundRequest, UserBalance, UsageHistory
from models.user import User
from schemas.refund_schema import RefundRequestCreate

# ================================================================
# 1. 환불 가능 금액 조회
# ================================================================

async def get_user_refundable_amount(db: AsyncSession, user_id: str) -> dict:
    """사용자의 환불 가능 금액 조회"""
    user_balance = await get_user_balance(db, user_id)
    
    if not user_balance:
        return {
            "user_id": user_id,
            "refundable_amount": 0,
            "total_balance": 0,
            "can_request_refund": False,
            "message": "잔액 정보가 없습니다"
        }
    
    # 현재 대기중인 환불 요청이 있는지 확인
    has_pending_request = await has_pending_refund_request(db, user_id)
    
    return {
        "user_id": user_id,
        "refundable_amount": user_balance.refundable_balance,
        "total_balance": user_balance.total_balance,
        "can_request_refund": not has_pending_request,
        "message": "처리중인 환불 요청이 있습니다" if has_pending_request else "환불 신청 가능"
    }

async def get_user_balance(db: AsyncSession, user_id: str) -> Optional[UserBalance]:
    """사용자 잔액 조회"""
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    return result.scalar_one_or_none()

# ================================================================
# 2. 환불 요청 관리
# ================================================================

async def has_pending_refund_request(db: AsyncSession, user_id: str) -> bool:
    """사용자에게 대기중인 환불 요청이 있는지 확인"""
    result = await db.execute(
        select(RefundRequest).where(
            and_(
                RefundRequest.user_id == user_id,
                RefundRequest.status == "pending"
            )
        )
    )
    return result.scalar_one_or_none() is not None

async def get_pending_refund_request(db: AsyncSession, user_id: str) -> Optional[RefundRequest]:
    """사용자의 대기중인 환불 요청 조회"""
    result = await db.execute(
        select(RefundRequest).where(
            and_(
                RefundRequest.user_id == user_id,
                RefundRequest.status == "pending"
            )
        )
    )
    return result.scalar_one_or_none()

async def create_refund_request(
    db: AsyncSession,
    user_id: str,
    refund_data: RefundRequestCreate
) -> RefundRequest:
    """환불 요청 생성 (새로운 시스템)"""
    
    # 1. 환불 가능성 검증
    refundable_info = await get_user_refundable_amount(db, user_id)
    
    if not refundable_info["can_request_refund"]:
        raise ValueError("이미 처리중인 환불 요청이 있습니다")
    
    if refund_data.refund_amount > refundable_info["refundable_amount"]:
        raise ValueError(f"환불 가능 금액({refundable_info['refundable_amount']:,}원)을 초과했습니다")
    
    if refund_data.refund_amount < 1000:
        raise ValueError("최소 환불 금액은 1,000원입니다")
    
    # 2. 환불 요청 생성
    refund_request = RefundRequest(
        user_id=user_id,
        bank_name=refund_data.bank_name,
        account_number=refund_data.account_number,
        account_holder=refund_data.account_holder,
        refund_amount=refund_data.refund_amount,
        contact=refund_data.contact,
        reason=refund_data.reason,
        status="pending"
    )
    
    db.add(refund_request)
    await db.commit()
    await db.refresh(refund_request)
    
    return refund_request

# ================================================================
# 3. 환불 승인/거부 처리
# ================================================================

async def approve_refund_new(
    db: AsyncSession,
    refund_request: RefundRequest,
    admin_memo: Optional[str] = None
) -> RefundRequest:
    """환불 승인 처리 (새로운 시스템)"""
    
    # 0. 중복 처리 방지 - 이미 처리된 요청인지 확인
    if refund_request.status != "pending":
        raise ValueError(f"이미 처리된 요청입니다. 현재 상태: {refund_request.status}")
    
    # 1. 사용자 잔액 차감
    user_balance = await get_user_balance(db, refund_request.user_id)
    if not user_balance:
        raise ValueError("사용자 잔액 정보가 없습니다")
    
    if user_balance.refundable_balance < refund_request.refund_amount:
        raise ValueError("환불 가능 잔액이 부족합니다")
    
    # 2. 잔액 차감
    user_balance.refundable_balance -= refund_request.refund_amount
    user_balance.total_balance -= refund_request.refund_amount
    user_balance.updated_at = datetime.now(timezone.utc)
    
    # 3. 사용 내역 기록
    usage_history = UsageHistory(
        user_id=refund_request.user_id,
        amount=refund_request.refund_amount,
        service_type="refund",
        service_id=str(refund_request.refund_request_id),
        description=f"환불 승인 (요청 ID: {refund_request.refund_request_id})"
    )
    db.add(usage_history)
    
    # 4. 환불 요청 상태 업데이트
    refund_request.status = "approved"
    refund_request.processed_at = datetime.now(timezone.utc)
    refund_request.admin_memo = admin_memo
    
    await db.commit()
    return refund_request

async def reject_refund_new(
    db: AsyncSession,
    refund_request: RefundRequest,
    admin_memo: Optional[str] = None
) -> RefundRequest:
    """환불 거부 처리 (새로운 시스템)"""
    
    # 중복 처리 방지 - 이미 처리된 요청인지 확인
    if refund_request.status != "pending":
        raise ValueError(f"이미 처리된 요청입니다. 현재 상태: {refund_request.status}")
    
    refund_request.status = "rejected"
    refund_request.processed_at = datetime.now(timezone.utc)
    refund_request.admin_memo = admin_memo
    
    await db.commit()
    return refund_request

# ================================================================
# 4. 환불 내역 조회
# ================================================================

async def get_user_refund_history(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 10,
    status_filter: Optional[str] = None
) -> List[RefundRequest]:
    """사용자 환불 내역 조회"""
    query = select(RefundRequest).where(RefundRequest.user_id == user_id)
    
    if status_filter:
        query = query.where(RefundRequest.status == status_filter)
    
    result = await db.execute(
        query.order_by(RefundRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_all_refund_requests(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None
) -> List[RefundRequest]:
    """모든 환불 요청 조회 (관리자용)"""
    query = select(RefundRequest)
    
    if status_filter:
        query = query.where(RefundRequest.status == status_filter)
    
    result = await db.execute(
        query.order_by(RefundRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_refund_request(db: AsyncSession, refund_request_id: int) -> Optional[RefundRequest]:
    """환불 요청 단건 조회"""
    result = await db.execute(
        select(RefundRequest).where(RefundRequest.refund_request_id == refund_request_id)
    )
    return result.scalar_one_or_none()