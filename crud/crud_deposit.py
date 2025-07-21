from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy import and_, or_, update as sqlalchemy_update
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from models.deposit import DepositRequest
from models.user import User
from schemas.deposit_schema import DepositRequestCreate, DepositRequestUpdate
import random
import string

# 4.1.1 create_deposit_request 함수
async def get_existing_active_request(
    db: AsyncSession,
    user_id: str
) -> Optional[DepositRequest]:
    """기존 활성 요청 조회"""
    existing_request = await db.execute(
        select(DepositRequest).where(
            and_(
                DepositRequest.user_id == user_id,
                DepositRequest.status == 'pending',
                DepositRequest.expires_at > datetime.now(timezone.utc)
            )
        ).order_by(DepositRequest.created_at.desc()).limit(1)
    )
    return existing_request.scalar_one_or_none()

async def create_deposit_request(
    db: AsyncSession, 
    user_id: str, 
    deposit_data: DepositRequestCreate
) -> DepositRequest:
    """입금 요청 생성 또는 기존 활성 요청 반환"""
    
    # 사용자 존재 확인
    user_result = await db.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError("사용자를 찾을 수 없습니다")
    
    # 기존 활성 요청 확인 (만료되지 않은 pending 상태) - 가장 최근 것
    existing_request = await db.execute(
        select(DepositRequest).where(
            and_(
                DepositRequest.user_id == user_id,
                DepositRequest.status == 'pending',
                DepositRequest.expires_at > datetime.now(timezone.utc)
            )
        ).order_by(DepositRequest.created_at.desc()).limit(1)
    )
    existing = existing_request.scalar_one_or_none()
    
    # 기존 활성 요청이 있으면 반환
    if existing:
        return existing
    
    # 만료된 요청들 정리
    await db.execute(
        sqlalchemy_update(DepositRequest)
        .where(
            and_(
                DepositRequest.user_id == user_id,
                DepositRequest.status == 'pending',
                DepositRequest.expires_at <= datetime.now(timezone.utc)
            )
        )
        .values(status='expired')
    )
    
    # 닉네임 + 4자리 랜덤숫자로 입금자명 생성
    deposit_name = await generate_unique_deposit_name(db, user.nickname)
    
    # 만료 시간 (1시간 후)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # 새 입금 요청 생성
    deposit_request = DepositRequest(
        user_id=user_id,
        deposit_name=deposit_name,
        amount=1,  # 사용자가 원하는 만큼 입금하면 그만큼 충전되므로 기본값 0
        bank_name=deposit_data.bank_name,
        account_number=deposit_data.account_number,
        expires_at=expires_at
    )
    
    db.add(deposit_request)
    await db.commit()
    await db.refresh(deposit_request)
    
    return deposit_request

async def generate_unique_deposit_name(db: AsyncSession, nickname: str) -> str:
    """고유한 입금자명 생성"""
    max_attempts = 100
    
    for _ in range(max_attempts):
        # 4자리 랜덤 숫자 생성
        random_digits = ''.join(random.choices(string.digits, k=4))
        deposit_name = f"{nickname}{random_digits}"
        
        # 중복 확인 (현재 유효한 요청만 확인)
        result = await db.execute(
            select(DepositRequest).where(
                and_(
                    DepositRequest.deposit_name == deposit_name,
                    DepositRequest.status == 'pending',
                    DepositRequest.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        
        if result.scalar_one_or_none() is None:
            return deposit_name
    
    raise ValueError("고유한 입금자명 생성에 실패했습니다")

# 4.1.2 get_deposit_request 함수
async def get_deposit_request(db: AsyncSession, deposit_request_id: int) -> Optional[DepositRequest]:
    """입금 요청 조회"""
    result = await db.execute(
        select(DepositRequest).where(DepositRequest.deposit_request_id == deposit_request_id)
    )
    return result.scalar_one_or_none()

async def get_deposit_request_by_name(db: AsyncSession, deposit_name: str) -> Optional[DepositRequest]:
    """입금자명으로 입금 요청 조회"""
    result = await db.execute(
        select(DepositRequest).where(DepositRequest.deposit_name == deposit_name)
    )
    return result.scalar_one_or_none()

async def get_user_deposit_requests(
    db: AsyncSession, 
    user_id: str, 
    skip: int = 0, 
    limit: int = 10
) -> List[DepositRequest]:
    """사용자의 입금 요청 목록 조회"""
    result = await db.execute(
        select(DepositRequest)
        .where(DepositRequest.user_id == user_id)
        .order_by(DepositRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

# 4.1.3 update_deposit_request 함수
async def update_deposit_request(
    db: AsyncSession,
    deposit_request_id: int,
    update_data: DepositRequestUpdate
) -> Optional[DepositRequest]:
    """입금 요청 상태 업데이트"""
    
    # 업데이트시 updated_at 자동 설정
    update_dict = update_data.dict(exclude_unset=True)
    if update_dict:
        update_dict['updated_at'] = datetime.now(timezone.utc)
    
    await db.execute(
        sqlalchemy_update(DepositRequest)
        .where(DepositRequest.deposit_request_id == deposit_request_id)
        .values(**update_dict)
    )
    await db.commit()
    
    return await get_deposit_request(db, deposit_request_id)

async def mark_deposit_completed(
    db: AsyncSession,
    deposit_request_id: int,
    matched_at: Optional[datetime] = None
) -> Optional[DepositRequest]:
    """입금 완료 처리로 상태 변경"""
    if matched_at is None:
        matched_at = datetime.now(timezone.utc)
    
    update_data = DepositRequestUpdate(
        status="completed",
        matched_at=matched_at
    )
    
    return await update_deposit_request(db, deposit_request_id, update_data)

# 4.1.4 get_active_deposits 함수
async def get_active_deposits(
    db: AsyncSession,
    user_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
) -> List[DepositRequest]:
    """현재 유효한 입금 요청 조회"""
    query = select(DepositRequest).where(
        and_(
            DepositRequest.status == 'pending',
            DepositRequest.expires_at > datetime.now(timezone.utc)
        )
    )
    
    if user_id:
        query = query.where(DepositRequest.user_id == user_id)
    
    query = query.order_by(DepositRequest.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def get_pending_deposits_by_amount(
    db: AsyncSession,
    amount: int,
    time_range_minutes: int = 30
) -> List[DepositRequest]:
    """특정 금액으로 된 입금 요청 조회 (SMS 매칭용)"""
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=time_range_minutes)
    
    result = await db.execute(
        select(DepositRequest).where(
            and_(
                DepositRequest.amount == amount,
                DepositRequest.status == 'pending',
                DepositRequest.created_at >= time_threshold,
                DepositRequest.expires_at > datetime.now(timezone.utc)
            )
        ).order_by(DepositRequest.created_at.desc())
    )
    return result.scalars().all()

# 4.1.5 expire_deposit_request 함수
async def expire_deposit_request(db: AsyncSession, deposit_request_id: int) -> Optional[DepositRequest]:
    """입금 요청 만료 처리"""
    update_data = DepositRequestUpdate(status="expired")
    return await update_deposit_request(db, deposit_request_id, update_data)

async def expire_old_deposits(db: AsyncSession) -> int:
    """만료된 입금요청들 일괄 처리"""
    current_time = datetime.now(timezone.utc)
    
    result = await db.execute(
        sqlalchemy_update(DepositRequest)
        .where(
            and_(
                DepositRequest.status == 'pending',
                DepositRequest.expires_at <= current_time
            )
        )
        .values(
            status='expired',
            updated_at=current_time
        )
    )
    await db.commit()
    
    return result.rowcount

# 4.1.6 통계용 함수들 - 관리자 대시보드 함수들
async def get_deposit_requests_count(
    db: AsyncSession,
    user_id: Optional[str] = None,
    status: Optional[str] = None
) -> int:
    """입금 요청 수 조회"""
    query = select(func.count(DepositRequest.deposit_request_id))
    
    conditions = []
    if user_id:
        conditions.append(DepositRequest.user_id == user_id)
    if status:
        conditions.append(DepositRequest.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    return result.scalar()

async def search_deposit_requests(
    db: AsyncSession,
    deposit_name: Optional[str] = None,
    amount: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 10
) -> List[DepositRequest]:
    """입금 요청 검색"""
    query = select(DepositRequest)
    conditions = []
    
    if deposit_name:
        conditions.append(DepositRequest.deposit_name.ilike(f"%{deposit_name}%"))
    if amount:
        conditions.append(DepositRequest.amount == amount)
    if status:
        conditions.append(DepositRequest.status == status)
    if start_date:
        conditions.append(DepositRequest.created_at >= start_date)
    if end_date:
        conditions.append(DepositRequest.created_at <= end_date)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(DepositRequest.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def check_user_rate_limit_deposit(db: AsyncSession, user_id: str) -> bool:
    """사용자의 입금 요청 제한 확인 (1분당 1회)"""
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    
    result = await db.execute(
        select(func.count(DepositRequest.deposit_request_id))
        .where(
            and_(
                DepositRequest.user_id == user_id,
                DepositRequest.created_at >= one_minute_ago
            )
        )
    )
    
    count = result.scalar()
    return count == 0  # True면 허용, False면 차단

async def get_recent_failed_deposits(
    db: AsyncSession,
    hours: int = 24,
    skip: int = 0,
    limit: int = 10
) -> List[DepositRequest]:
    """최근 실패한 입금 요청 조회"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    result = await db.execute(
        select(DepositRequest)
        .where(
            and_(
                DepositRequest.status == 'failed',
                DepositRequest.created_at >= time_threshold
            )
        )
        .order_by(DepositRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

# 4.1.7 CRUD 완성 마무리용 함수 (옵션)
async def delete_deposit_request(db: AsyncSession, deposit_request_id: int) -> bool:
    """입금 요청 삭제 (물리삭제)"""
    result = await db.execute(
        select(DepositRequest).where(DepositRequest.deposit_request_id == deposit_request_id)
    )
    deposit_request = result.scalar_one_or_none()
    
    if deposit_request:
        await db.delete(deposit_request)
        await db.commit()
        return True
    return False