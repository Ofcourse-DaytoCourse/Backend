from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy import and_, or_, update as sqlalchemy_update
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from models.payment import ChargeHistory, UsageHistory, UserBalance, RefundRequest
from models.user import User
from schemas.payment_schema import (
    ChargeHistoryCreate, UsageHistoryCreate, BalanceAddRequest, 
    BalanceDeductRequest, RefundRequestUpdate
)
from schemas.refund_schema import RefundRequestCreate

# 4.2.1 create_charge_history 함수
async def create_charge_history(
    db: AsyncSession,
    charge_data: ChargeHistoryCreate
) -> ChargeHistory:
    """충전 이력 생성"""
    charge_history = ChargeHistory(
        user_id=charge_data.user_id,
        deposit_request_id=charge_data.deposit_request_id,
        amount=charge_data.amount,
        is_refundable=charge_data.is_refundable,
        source_type=charge_data.source_type.value,
        description=charge_data.description
    )
    
    db.add(charge_history)
    await db.commit()
    await db.refresh(charge_history)
    
    return charge_history

# 4.2.2 create_usage_history 함수
async def create_usage_history(
    db: AsyncSession,
    usage_data: UsageHistoryCreate
) -> UsageHistory:
    """사용 이력 생성"""
    usage_history = UsageHistory(
        user_id=usage_data.user_id,
        amount=usage_data.amount,
        service_type=usage_data.service_type.value,
        service_id=usage_data.service_id,
        description=usage_data.description
    )
    
    db.add(usage_history)
    await db.commit()
    await db.refresh(usage_history)
    
    return usage_history

# 4.2.3 get_user_balance 함수
async def get_user_balance(db: AsyncSession, user_id: str) -> Optional[UserBalance]:
    """사용자 잔액 조회"""
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    return result.scalar_one_or_none()

async def get_or_create_user_balance(db: AsyncSession, user_id: str) -> UserBalance:
    """사용자 잔액 조회 또는 생성"""
    user_balance = await get_user_balance(db, user_id)
    
    if not user_balance:
        # 사용자 존재 확인
        user_result = await db.execute(select(User).where(User.user_id == user_id))
        if not user_result.scalar_one_or_none():
            raise ValueError("존재하지 않는 사용자입니다")
        
        # 새 잔액 레코드 생성
        user_balance = UserBalance(user_id=user_id)
        db.add(user_balance)
        await db.commit()
        await db.refresh(user_balance)
    
    return user_balance

# 4.2.4 update_user_balance 함수
async def update_user_balance(
    db: AsyncSession,
    user_id: str,
    amount: int,
    is_add: bool = True,
    is_refundable: bool = True
) -> UserBalance:
    """사용자 잔액 업데이트 (충전 또는 사용)"""
    user_balance = await get_or_create_user_balance(db, user_id)
    
    if is_add:
        # 잔액 추가
        user_balance.add_balance(amount, is_refundable)
    else:
        # 잔액 차감
        user_balance.deduct_balance(amount)
    
    user_balance.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user_balance)
    
    return user_balance

async def add_balance(
    db: AsyncSession,
    user_id: str,
    balance_data: BalanceAddRequest
) -> UserBalance:
    """잔액 추가"""
    return await update_user_balance(
        db, user_id, balance_data.amount, True, balance_data.is_refundable
    )

async def deduct_balance(
    db: AsyncSession,
    user_id: str,
    balance_data: BalanceDeductRequest
) -> Tuple[UserBalance, UsageHistory]:
    """잔액 차감 및 사용 이력 생성"""
    
    # 잔액 확인
    user_balance = await get_user_balance(db, user_id)
    if not user_balance or not user_balance.has_sufficient_balance(balance_data.amount):
        raise ValueError("잔액이 부족합니다")
    
    # 트랜잭션 처리 - 단일 커밋으로 처리
    try:
        # 잔액 차감 (커밋 없이)
        user_balance.deduct_balance(balance_data.amount)
        user_balance.updated_at = datetime.now(timezone.utc)
        
        # 사용 이력 생성 (커밋 없이)
        usage_history = UsageHistory(
            user_id=user_id,
            amount=balance_data.amount,
            service_type=balance_data.service_type.value,
            service_id=balance_data.service_id,
            description=balance_data.description
        )
        
        db.add(usage_history)
        
        # 한 번에 커밋
        await db.commit()
        await db.refresh(user_balance)
        await db.refresh(usage_history)
        
        return user_balance, usage_history
        
    except Exception as e:
        await db.rollback()
        raise e

# 4.2.5 create_refund_request 함수
async def create_refund_request(
    db: AsyncSession,
    user_id: str,
    refund_data: RefundRequestCreate
) -> RefundRequest:
    """환불 요청 생성"""
    
    print(f"🔍 CRUD: 환불 요청 생성 시작 - user_id: {user_id}, charge_history_id: {refund_data.charge_history_id}")
    
    # 충전 이력 존재 및 환불 가능 여부 확인
    charge_history = await get_charge_history(db, refund_data.charge_history_id)
    print(f"🔍 CRUD: 충전 이력 조회 결과: {charge_history}")
    if not charge_history:
        raise ValueError("충전 이력이 존재하지 않습니다")
    
    if charge_history.user_id != user_id:
        raise ValueError("본인의 충전 이력에 대해서만 환불 요청이 가능합니다")
    
    # 환불 가능 금액 확인
    refundable_amount = charge_history.get_refundable_amount()
    if refund_data.refund_amount > refundable_amount:
        raise ValueError(f"환불 가능 금액을 초과했습니다. (최대: {refundable_amount}원)")
    
    # 기존 대기 중 환불 요청 확인
    print(f"🔍 CRUD: 기존 환불 요청 확인 중...")
    existing_request = await get_pending_refund_request(db, refund_data.charge_history_id)
    print(f"🔍 CRUD: 기존 환불 요청: {existing_request}")
    if existing_request:
        raise ValueError("이미 대기 중인 환불 요청이 있습니다")
    
    print(f"🔍 CRUD: RefundRequest 객체 생성 중...")
    refund_request = RefundRequest(
        user_id=user_id,
        charge_history_id=refund_data.charge_history_id,
        bank_name=refund_data.bank_name,
        account_number=refund_data.account_number,
        account_holder=refund_data.account_holder,
        refund_amount=refund_data.refund_amount,
        contact=refund_data.contact,
        reason=refund_data.reason
    )
    print(f"🔍 CRUD: RefundRequest 객체 생성 완료")
    
    print(f"🔍 CRUD: 데이터베이스에 추가 중...")
    db.add(refund_request)
    print(f"🔍 CRUD: 커밋 중...")
    await db.commit()
    print(f"🔍 CRUD: 리프레시 중...")
    await db.refresh(refund_request)
    print(f"🔍 CRUD: 환불 요청 생성 완료")
    
    return refund_request

# 4.2.6 get_refundable_amount 함수
async def get_refundable_amount(
    db: AsyncSession,
    charge_history_id: int,
    user_id: Optional[str] = None
) -> dict:
    """환불 가능 금액 조회"""
    charge_history = await get_charge_history(db, charge_history_id)
    if not charge_history:
        raise ValueError("충전 이력이 존재하지 않습니다")
    
    if user_id and charge_history.user_id != user_id:
        raise ValueError("본인의 충전 이력만 조회할 수 있습니다")
    
    # 대기 중 환불 요청 확인
    pending_request = await get_pending_refund_request(db, charge_history_id)
    
    return {
        "charge_history_id": charge_history_id,
        "original_amount": charge_history.amount,
        "refunded_amount": charge_history.refunded_amount,
        "refundable_amount": charge_history.get_refundable_amount(),
        "is_refundable": charge_history.is_refundable,
        "refund_status": charge_history.refund_status,
        "has_pending_request": pending_request is not None,
        "pending_request_amount": pending_request.refund_amount if pending_request else 0
    }

# 4.2.7 process_refund 함수
async def process_refund(
    db: AsyncSession,
    refund_request_id: int,
    approved: bool,
    admin_memo: Optional[str] = None
) -> RefundRequest:
    """환불 요청 처리 (관리자 승인/거부)"""
    
    refund_request = await get_refund_request(db, refund_request_id)
    if not refund_request:
        raise ValueError("환불 요청이 존재하지 않습니다")
    
    if not refund_request.is_pending():
        raise ValueError("이미 처리된 환불 요청입니다")
    
    try:
        if approved:
            # 환불 승인 처리
            await approve_refund(db, refund_request, admin_memo)
        else:
            # 환불 거부 처리
            await reject_refund(db, refund_request, admin_memo)
            
        return refund_request
        
    except Exception as e:
        await db.rollback()
        raise e

async def approve_refund(
    db: AsyncSession,
    refund_request: RefundRequest,
    admin_memo: Optional[str] = None
):
    """환불 승인 처리"""
    
    # 충전 이력 업데이트
    charge_history = await get_charge_history(db, refund_request.charge_history_id)
    if not charge_history:
        raise ValueError("충전 이력이 존재하지 않습니다")
    
    # 환불 가능 금액 재확인
    if refund_request.refund_amount > charge_history.get_refundable_amount():
        raise ValueError("환불 가능 금액을 초과했습니다")
    
    # 충전 이력 환불 금액 업데이트
    charge_history.refunded_amount += refund_request.refund_amount
    
    # 환불 상태 업데이트
    if charge_history.is_fully_refunded():
        charge_history.refund_status = "fully_refunded"
    else:
        charge_history.refund_status = "partially_refunded"
    
    # 사용자 잔액 차감 (환불 가능 잔액에서)
    user_balance = await get_user_balance(db, refund_request.user_id)
    if user_balance:
        if user_balance.refundable_balance >= refund_request.refund_amount:
            user_balance.refundable_balance -= refund_request.refund_amount
            user_balance.total_balance -= refund_request.refund_amount
            
            # 사용 내역에 환불 기록 추가
            from models.payment import UsageHistory
            usage_history = UsageHistory(
                user_id=refund_request.user_id,
                amount=refund_request.refund_amount,
                service_type="refund",
                service_id=str(refund_request.refund_request_id),
                description=f"환불 승인 (요청 ID: {refund_request.refund_request_id})"
            )
            db.add(usage_history)
        else:
            raise ValueError("환불할 잔액이 부족합니다")
    
    # 환불 요청 상태 업데이트
    refund_request.status = "approved"
    refund_request.processed_at = datetime.now(timezone.utc)
    refund_request.admin_memo = admin_memo
    
    await db.commit()
    
    return refund_request

async def reject_refund(
    db: AsyncSession,
    refund_request: RefundRequest,
    admin_memo: Optional[str] = None
):
    """환불 거부 처리"""
    refund_request.status = "rejected"
    refund_request.processed_at = datetime.now(timezone.utc)
    refund_request.admin_memo = admin_memo
    
    await db.commit()
    
    return refund_request

# 4.2.8 기타 조회 함수들 - 충전, 사용, 환불 내역
async def get_charge_history(db: AsyncSession, charge_history_id: int) -> Optional[ChargeHistory]:
    """충전 이력 조회"""
    result = await db.execute(
        select(ChargeHistory).where(ChargeHistory.charge_history_id == charge_history_id)
    )
    return result.scalar_one_or_none()

async def get_user_charge_histories(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 10
) -> List[ChargeHistory]:
    """사용자 충전 이력 목록 조회 (N+1 쿼리 방지)"""
    result = await db.execute(
        select(ChargeHistory)
        .options(joinedload(ChargeHistory.user))
        .where(ChargeHistory.user_id == user_id)
        .order_by(ChargeHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_user_usage_histories(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 10
) -> List[UsageHistory]:
    """사용자 사용 이력 목록 조회 (N+1 쿼리 방지)"""
    result = await db.execute(
        select(UsageHistory)
        .options(joinedload(UsageHistory.user))
        .where(UsageHistory.user_id == user_id)
        .order_by(UsageHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_refund_request(db: AsyncSession, refund_request_id: int) -> Optional[RefundRequest]:
    """환불 요청 조회"""
    result = await db.execute(
        select(RefundRequest).where(RefundRequest.refund_request_id == refund_request_id)
    )
    return result.scalar_one_or_none()

async def get_user_refund_requests(
    db: AsyncSession,
    user_id: Optional[str],
    skip: int = 0,
    limit: int = 10
) -> List[RefundRequest]:
    """사용자 환불 요청 목록 조회 (user_id가 None이면 모든 사용자)"""
    query = select(RefundRequest)
    
    if user_id is not None:
        query = query.where(RefundRequest.user_id == user_id)
    
    result = await db.execute(
        query.order_by(RefundRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_pending_refund_request(
    db: AsyncSession,
    charge_history_id: int
) -> Optional[RefundRequest]:
    """특정 충전 이력의 대기 중 환불 요청 조회"""
    result = await db.execute(
        select(RefundRequest).where(
            and_(
                RefundRequest.charge_history_id == charge_history_id,
                or_(
                    RefundRequest.status == "pending",
                    RefundRequest.status == "approved"
                )
            )
        )
    )
    return result.scalar_one_or_none()

async def get_refundable_charge_histories(
    db: AsyncSession,
    user_id: str
) -> List[ChargeHistory]:
    """환불 가능한 충전 이력 조회 (대기중인 환불 요청이 없는 것만)"""
    # 대기중인 환불 요청이 있는 charge_history_id들 조회
    pending_subquery = select(RefundRequest.charge_history_id).where(
        and_(
            RefundRequest.user_id == user_id,
            RefundRequest.status.in_(["pending", "approved"])
        )
    )
    
    result = await db.execute(
        select(ChargeHistory).where(
            and_(
                ChargeHistory.user_id == user_id,
                ChargeHistory.is_refundable == True,
                ChargeHistory.refund_status.in_(["available", "partially_refunded"]),
                ~ChargeHistory.charge_history_id.in_(pending_subquery)  # 대기중인 환불 요청 제외
            )
        ).order_by(ChargeHistory.created_at.desc())
    )
    return result.scalars().all()

# 4.2.9 CRUD 통계 관련 함수들 (추가)
async def get_payment_statistics(
    db: AsyncSession,
    user_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """결제 통계 조회"""
    conditions = []
    
    if user_id:
        conditions.append(ChargeHistory.user_id == user_id)
    if start_date:
        conditions.append(ChargeHistory.created_at >= start_date)
    if end_date:
        conditions.append(ChargeHistory.created_at <= end_date)
    
    # 총 충전 금액
    charge_query = select(func.sum(ChargeHistory.amount))
    if conditions:
        charge_query = charge_query.where(and_(*conditions))
    
    charge_result = await db.execute(charge_query)
    total_charged = charge_result.scalar() or 0
    
    # 총 사용 금액
    usage_conditions = []
    if user_id:
        usage_conditions.append(UsageHistory.user_id == user_id)
    if start_date:
        usage_conditions.append(UsageHistory.created_at >= start_date)
    if end_date:
        usage_conditions.append(UsageHistory.created_at <= end_date)
    
    usage_query = select(func.sum(UsageHistory.amount))
    if usage_conditions:
        usage_query = usage_query.where(and_(*usage_conditions))
    
    usage_result = await db.execute(usage_query)
    total_used = usage_result.scalar() or 0
    
    # 총 환불 금액
    refund_query = select(func.sum(ChargeHistory.refunded_amount))
    if conditions:
        refund_query = refund_query.where(and_(*conditions))
    
    refund_result = await db.execute(refund_query)
    total_refunded = refund_result.scalar() or 0
    
    return {
        "total_charged": total_charged,
        "total_used": total_used,
        "total_refunded": total_refunded,
        "net_balance": total_charged - total_used - total_refunded
    }