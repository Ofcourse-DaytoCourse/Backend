from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy import and_, delete, update as sqlalchemy_update
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from models.rate_limit import RateLimitLog
from models.user import User
from schemas.rate_limit_schema import RateLimitLogCreate, ActionType

# 레이트 리미팅 설정
RATE_LIMIT_CONFIGS = {
    ActionType.DEPOSIT_GENERATE: {
        "max_attempts": 1,
        "period_minutes": 1,
        "description": "입금자명 생성은 1분에 1회만 가능합니다"
    },
    ActionType.REFUND_REQUEST: {
        "max_attempts": 3,
        "period_minutes": 60,
        "description": "환불 요청은 1시간에 3회만 가능합니다"
    },
    ActionType.BALANCE_DEDUCT: {
        "max_attempts": 10,
        "period_minutes": 1,
        "description": "서비스 이용은 1분에 10회까지 가능합니다"
    }
}

# 4.4.1 create_rate_limit_log 함수
async def create_rate_limit_log(
    db: AsyncSession,
    log_data: RateLimitLogCreate
) -> RateLimitLog:
    """레이트 리미팅 로그 생성"""
    
    # 사용자 존재 확인
    user_result = await db.execute(select(User).where(User.user_id == log_data.user_id))
    if not user_result.scalar_one_or_none():
        raise ValueError("사용자를 찾을 수 없습니다")
    
    rate_limit_log = RateLimitLog(
        user_id=log_data.user_id,
        action_type=log_data.action_type.value
    )
    
    db.add(rate_limit_log)
    await db.commit()
    await db.refresh(rate_limit_log)
    
    return rate_limit_log

# 4.4.2 check_rate_limit 함수
async def check_rate_limit(
    db: AsyncSession,
    user_id: str,
    action_type: ActionType
) -> Dict[str, Any]:
    """레이트 리미팅 확인"""
    
    config = RATE_LIMIT_CONFIGS.get(action_type)
    if not config:
        raise ValueError(f"지원하지 않는 액션 타입입니다: {action_type}")
    
    # 제한 기간 내의 시도 횟수 조회
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=config["period_minutes"])
    
    result = await db.execute(
        select(func.count(RateLimitLog.rate_limit_log_id))
        .where(
            and_(
                RateLimitLog.user_id == user_id,
                RateLimitLog.action_type == action_type.value,
                RateLimitLog.created_at >= time_threshold
            )
        )
    )
    
    current_count = result.scalar()
    max_attempts = config["max_attempts"]
    
    # 허용 여부 확인
    allowed = current_count < max_attempts
    remaining_attempts = max(0, max_attempts - current_count)
    
    # 다음 리셋 시간 계산
    if not allowed:
        # 가장 오래된 로그의 만료 시간 계산
        oldest_log_result = await db.execute(
            select(RateLimitLog.created_at)
            .where(
                and_(
                    RateLimitLog.user_id == user_id,
                    RateLimitLog.action_type == action_type.value,
                    RateLimitLog.created_at >= time_threshold
                )
            )
            .order_by(RateLimitLog.created_at.asc())
            .limit(1)
        )
        
        oldest_created_at = oldest_log_result.scalar()
        if oldest_created_at:
            reset_time = oldest_created_at + timedelta(minutes=config["period_minutes"])
        else:
            reset_time = datetime.now(timezone.utc)
    else:
        reset_time = None
    
    return {
        "allowed": allowed,
        "remaining_attempts": remaining_attempts,
        "reset_time": reset_time,
        "message": config["description"] if not allowed else "허용됨",
        "current_count": current_count,
        "limit_per_period": max_attempts,
        "period_minutes": config["period_minutes"]
    }

async def is_rate_limited(
    db: AsyncSession,
    user_id: str,
    action_type: ActionType
) -> bool:
    """레이트 리미팅 여부 간단 확인"""
    result = await check_rate_limit(db, user_id, action_type)
    return not result["allowed"]

async def record_action_if_allowed(
    db: AsyncSession,
    user_id: str,
    action_type: ActionType
) -> Dict[str, Any]:
    """허용되는 경우에만 액션 기록"""
    
    # 레이트 리미팅 확인
    rate_check = await check_rate_limit(db, user_id, action_type)
    
    if not rate_check["allowed"]:
        return {
            "success": False,
            "message": rate_check["message"],
            "rate_limit_info": rate_check
        }
    
    # 허용되는 경우 로그 기록
    log_data = RateLimitLogCreate(user_id=user_id, action_type=action_type)
    rate_limit_log = await create_rate_limit_log(db, log_data)
    
    return {
        "success": True,
        "message": "액션이 허용되었습니다",
        "rate_limit_log_id": rate_limit_log.rate_limit_log_id,
        "rate_limit_info": rate_check
    }

# 4.4.3 cleanup_expired_logs 함수
async def cleanup_expired_logs(db: AsyncSession) -> int:
    """만료된 레이트 리미팅 로그 삭제 (24시간 후)"""
    current_time = datetime.now(timezone.utc)
    
    result = await db.execute(
        delete(RateLimitLog).where(RateLimitLog.expires_at <= current_time)
    )
    await db.commit()
    
    return result.rowcount

async def cleanup_old_logs_by_action(
    db: AsyncSession,
    action_type: ActionType,
    hours_old: int = 24
) -> int:
    """특정 액션 타입의 오래된 로그 삭제"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    
    result = await db.execute(
        delete(RateLimitLog).where(
            and_(
                RateLimitLog.action_type == action_type.value,
                RateLimitLog.created_at <= time_threshold
            )
        )
    )
    await db.commit()
    
    return result.rowcount

# 4.4.4 CRUD 기능 테스트 - 추가 유틸리티 함수들
async def get_user_rate_limit_logs(
    db: AsyncSession,
    user_id: str,
    action_type: Optional[ActionType] = None,
    skip: int = 0,
    limit: int = 10
) -> List[RateLimitLog]:
    """사용자의 레이트 리미팅 로그 조회"""
    query = select(RateLimitLog).where(RateLimitLog.user_id == user_id)
    
    if action_type:
        query = query.where(RateLimitLog.action_type == action_type.value)
    
    query = query.order_by(RateLimitLog.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def get_rate_limit_statistics(
    db: AsyncSession,
    action_type: Optional[ActionType] = None,
    hours: int = 24
) -> Dict[str, Any]:
    """레이트 리미팅 통계 조회"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    query = select(
        func.count(RateLimitLog.rate_limit_log_id).label("total_requests"),
        func.count(func.distinct(RateLimitLog.user_id)).label("unique_users")
    ).where(RateLimitLog.created_at >= time_threshold)
    
    if action_type:
        query = query.where(RateLimitLog.action_type == action_type.value)
    
    result = await db.execute(query)
    stats = result.first()
    
    # 시간대별 요청 분포
    hourly_query = select(
        func.date_trunc('hour', RateLimitLog.created_at).label("hour"),
        func.count(RateLimitLog.rate_limit_log_id).label("count")
    ).where(RateLimitLog.created_at >= time_threshold)
    
    if action_type:
        hourly_query = hourly_query.where(RateLimitLog.action_type == action_type.value)
    
    hourly_query = hourly_query.group_by(func.date_trunc('hour', RateLimitLog.created_at))
    hourly_result = await db.execute(hourly_query)
    
    hourly_stats = {}
    for row in hourly_result:
        hourly_stats[row.hour.isoformat()] = row.count
    
    return {
        "action_type": action_type.value if action_type else "all",
        "period_hours": hours,
        "total_requests": stats.total_requests or 0,
        "unique_users": stats.unique_users or 0,
        "hourly_distribution": hourly_stats
    }

async def get_user_current_status(
    db: AsyncSession,
    user_id: str
) -> Dict[str, Any]:
    """사용자의 현재 레이트 리미팅 상태 조회"""
    status = {}
    
    for action_type in ActionType:
        rate_check = await check_rate_limit(db, user_id, action_type)
        status[action_type.value] = {
            "allowed": rate_check["allowed"],
            "remaining_attempts": rate_check["remaining_attempts"],
            "reset_time": rate_check["reset_time"],
            "current_count": rate_check["current_count"],
            "limit_per_period": rate_check["limit_per_period"]
        }
    
    return {
        "user_id": user_id,
        "status": status,
        "has_active_limits": any(not status[action]["allowed"] for action in status),
        "checked_at": datetime.now(timezone.utc)
    }

async def reset_user_rate_limits(
    db: AsyncSession,
    user_id: str,
    action_type: Optional[ActionType] = None,
    admin_reason: str = "관리자 리셋"
) -> Dict[str, Any]:
    """사용자의 레이트 리미팅 리셋 (관리자용)"""
    
    query = delete(RateLimitLog).where(RateLimitLog.user_id == user_id)
    
    if action_type:
        query = query.where(RateLimitLog.action_type == action_type.value)
    
    result = await db.execute(query)
    await db.commit()
    
    return {
        "success": True,
        "message": "레이트 리미팅이 리셋되었습니다",
        "user_id": user_id,
        "action_type": action_type.value if action_type else "all",
        "deleted_logs": result.rowcount,
        "admin_reason": admin_reason,
        "reset_at": datetime.now(timezone.utc)
    }

async def get_rate_limit_violations(
    db: AsyncSession,
    hours: int = 24,
    min_attempts: int = 5
) -> List[Dict[str, Any]]:
    """레이트 리미팅 위반 사용자 조회"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # 시도 횟수가 많은 사용자 조회
    result = await db.execute(
        select(
            RateLimitLog.user_id,
            RateLimitLog.action_type,
            func.count(RateLimitLog.rate_limit_log_id).label("attempt_count"),
            func.max(RateLimitLog.created_at).label("last_attempt")
        )
        .where(RateLimitLog.created_at >= time_threshold)
        .group_by(RateLimitLog.user_id, RateLimitLog.action_type)
        .having(func.count(RateLimitLog.rate_limit_log_id) >= min_attempts)
        .order_by(func.count(RateLimitLog.rate_limit_log_id).desc())
    )
    
    violations = []
    for row in result:
        config = RATE_LIMIT_CONFIGS.get(ActionType(row.action_type), {})
        limit_exceeded = row.attempt_count > config.get("max_attempts", 0)
        
        violations.append({
            "user_id": row.user_id,
            "action_type": row.action_type,
            "attempt_count": row.attempt_count,
            "last_attempt": row.last_attempt,
            "limit_exceeded": limit_exceeded,
            "max_allowed": config.get("max_attempts", 0),
            "excess_attempts": max(0, row.attempt_count - config.get("max_attempts", 0))
        })
    
    return violations

async def extend_rate_limit_period(
    db: AsyncSession,
    user_id: str,
    action_type: ActionType,
    extend_hours: int,
    admin_reason: str
) -> Dict[str, Any]:
    """레이트 리미팅 기간 연장 (관리자용)"""
    
    extend_time = timedelta(hours=extend_hours)
    
    result = await db.execute(
        sqlalchemy_update(RateLimitLog)
        .where(
            and_(
                RateLimitLog.user_id == user_id,
                RateLimitLog.action_type == action_type.value
            )
        )
        .values(expires_at=RateLimitLog.expires_at + extend_time)
    )
    await db.commit()
    
    return {
        "success": True,
        "message": f"레이트 리미팅 기간이 {extend_hours}시간 연장되었습니다",
        "user_id": user_id,
        "action_type": action_type.value,
        "extended_hours": extend_hours,
        "affected_logs": result.rowcount,
        "admin_reason": admin_reason,
        "extended_at": datetime.now(timezone.utc)
    }

# 자동 정리 스케줄러용 함수
async def scheduled_cleanup(db: AsyncSession) -> Dict[str, int]:
    """정기적인 레이트 리미팅 로그 정리"""
    results = {}
    
    # 만료된 로그 삭제
    results["expired_logs"] = await cleanup_expired_logs(db)
    
    # 각 액션 타입별 오래된 로그 삭제 (48시간 이상)
    for action_type in ActionType:
        deleted_count = await cleanup_old_logs_by_action(db, action_type, 48)
        results[f"{action_type.value}_old_logs"] = deleted_count
    
    return results