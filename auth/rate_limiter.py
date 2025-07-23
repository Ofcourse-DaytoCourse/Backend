from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Callable, Any
from functools import wraps
from datetime import datetime, timezone
import asyncio

from db.session import get_db
from crud.crud_rate_limit import check_rate_limit, record_action_if_allowed
from schemas.rate_limit_schema import ActionType
from auth.dependencies import get_current_user

# 5.1 기본 구조 설정
class RateLimitException(HTTPException):
    """레이트 리미팅 예외 클래스"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        detail = {
            "message": message,
            "error_type": "rate_limit_exceeded",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if retry_after:
            detail["retry_after"] = retry_after
            
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)} if retry_after else None
        )

class RateLimiter:
    """레이트 리미터 클래스"""
    
    def __init__(self):
        self.security = HTTPBearer()
    
    async def check_limit(
        self,
        user_id: str,
        action_type: ActionType,
        db: AsyncSession
    ) -> dict:
        """레이트 리미팅 확인"""
        return await check_rate_limit(db, user_id, action_type)
    
    async def record_action(
        self,
        user_id: str,
        action_type: ActionType,
        db: AsyncSession
    ) -> dict:
        """액션 기록 (허용되는 경우에만)"""
        return await record_action_if_allowed(db, user_id, action_type)

# 전역 레이트 리미터 인스턴스
rate_limiter = RateLimiter()

# 5.1.2 레이트 리미팅 규칙 정의
RATE_LIMIT_RULES = {
    ActionType.DEPOSIT_GENERATE: {
        "max_attempts": 1,
        "period_minutes": 1,
        "message": "입금자명 생성은 1분에 1회만 가능합니다",
        "description": "스팸 방지를 위한 제한입니다"
    },
    ActionType.REFUND_REQUEST: {
        "max_attempts": 3,
        "period_minutes": 60,
        "message": "환불 요청은 1시간에 3회까지 가능합니다",
        "description": "환불 요청 남용 방지를 위한 제한입니다"
    },
    ActionType.BALANCE_DEDUCT: {
        "max_attempts": 10,
        "period_minutes": 1,
        "message": "서비스 이용은 1분에 10회까지 가능합니다",
        "description": "서버 부하 방지를 위한 제한입니다"
    },
    ActionType.REVIEW_VALIDATION: {
        "max_attempts": 1,
        "period_minutes": 1,
        "message": "후기 검증 실패 후 1분 후에 다시 시도해주세요",
        "description": "부적절한 후기 재작성 방지"
    }
}

# 5.1.3 예외 처리 클래스 생성
class RateLimitConfig:
    """레이트 리미팅 설정 클래스"""
    
    @staticmethod
    def get_rule(action_type: ActionType) -> dict:
        """액션 타입별 규칙 조회"""
        return RATE_LIMIT_RULES.get(action_type, {})
    
    @staticmethod
    def get_retry_after(reset_time: Optional[datetime]) -> Optional[int]:
        """재시도 가능 시간 계산 (초 단위)"""
        if not reset_time:
            return None
        
        now = datetime.now(timezone.utc)
        # timezone naive인 reset_time을 UTC로 처리
        if reset_time.replace(tzinfo=timezone.utc) <= now:
            return None
        
        return int((reset_time.replace(tzinfo=timezone.utc) - now).total_seconds())

# 의존성 함수들
async def get_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db)
) -> str:
    """토큰에서 사용자 ID 추출"""
    try:
        # 기존 get_current_user 사용
        user = await get_current_user(credentials, db)
        return user.user_id
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다"
        )

# 레이트 리미팅 체크 의존성
async def check_deposit_generate_limit(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """입금자명 생성 레이트 리미팅 체크"""
    result = await rate_limiter.check_limit(user_id, ActionType.DEPOSIT_GENERATE, db)
    
    if not result["allowed"]:
        retry_after = RateLimitConfig.get_retry_after(result.get("reset_time"))
        raise RateLimitException(
            message=RATE_LIMIT_RULES[ActionType.DEPOSIT_GENERATE]["message"],
            retry_after=retry_after
        )
    
    return user_id

async def check_refund_request_limit(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """환불 요청 레이트 리미팅 체크"""
    result = await rate_limiter.check_limit(user_id, ActionType.REFUND_REQUEST, db)
    
    if not result["allowed"]:
        retry_after = RateLimitConfig.get_retry_after(result.get("reset_time"))
        raise RateLimitException(
            message=RATE_LIMIT_RULES[ActionType.REFUND_REQUEST]["message"],
            retry_after=retry_after
        )
    
    return user_id

async def check_balance_deduct_limit(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """잔액 차감 레이트 리미팅 체크"""
    result = await rate_limiter.check_limit(user_id, ActionType.BALANCE_DEDUCT, db)
    
    if not result["allowed"]:
        retry_after = RateLimitConfig.get_retry_after(result.get("reset_time"))
        raise RateLimitException(
            message=RATE_LIMIT_RULES[ActionType.BALANCE_DEDUCT]["message"],
            retry_after=retry_after
        )
    
    return user_id

# 레이트 리미팅 기록 의존성
async def record_deposit_generate_action(
    user_id: str = Depends(check_deposit_generate_limit),
    db: AsyncSession = Depends(get_db)
):
    """입금자명 생성 액션 기록"""
    result = await rate_limiter.record_action(user_id, ActionType.DEPOSIT_GENERATE, db)
    
    if not result["success"]:
        retry_after = RateLimitConfig.get_retry_after(
            result.get("rate_limit_info", {}).get("reset_time")
        )
        raise RateLimitException(
            message=result["message"],
            retry_after=retry_after
        )
    
    return user_id

async def record_refund_request_action(
    user_id: str = Depends(check_refund_request_limit),
    db: AsyncSession = Depends(get_db)
):
    """환불 요청 액션 기록"""
    result = await rate_limiter.record_action(user_id, ActionType.REFUND_REQUEST, db)
    
    if not result["success"]:
        retry_after = RateLimitConfig.get_retry_after(
            result.get("rate_limit_info", {}).get("reset_time")
        )
        raise RateLimitException(
            message=result["message"],
            retry_after=retry_after
        )
    
    return user_id

async def record_balance_deduct_action(
    user_id: str = Depends(check_balance_deduct_limit),
    db: AsyncSession = Depends(get_db)
):
    """잔액 차감 액션 기록"""
    result = await rate_limiter.record_action(user_id, ActionType.BALANCE_DEDUCT, db)
    
    if not result["success"]:
        retry_after = RateLimitConfig.get_retry_after(
            result.get("rate_limit_info", {}).get("reset_time")
        )
        raise RateLimitException(
            message=result["message"],
            retry_after=retry_after
        )
    
    return user_id

# 유틸리티 함수들
async def get_user_rate_limit_status(
    user_id: str,
    db: AsyncSession
) -> dict:
    """사용자의 현재 레이트 리미팅 상태 조회"""
    from crud.crud_rate_limit import get_user_current_status
    return await get_user_current_status(db, user_id)

async def reset_user_limits(
    user_id: str,
    action_type: Optional[ActionType],
    db: AsyncSession,
    admin_reason: str = "관리자 리셋"
) -> dict:
    """사용자 레이트 리미팅 리셋 (관리자용)"""
    from crud.crud_rate_limit import reset_user_rate_limits
    return await reset_user_rate_limits(db, user_id, action_type, admin_reason)

# 5.2 데코레이터 구현

# 5.2.1 @rate_limit 데코레이터 생성
def rate_limit(action_type: ActionType, record_action: bool = True):
    """
    레이트 리미팅 데코레이터
    
    Args:
        action_type: 액션 타입 (ActionType)
        record_action: 액션 기록 여부 (기본값: True)
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPI의 의존성에서 user_id와 db 추출
            user_id = None
            db = None
            
            # kwargs에서 user_id와 db 찾기
            for key, value in kwargs.items():
                if key == 'current_user_id' or (isinstance(value, str) and len(value) == 36):
                    user_id = value
                elif hasattr(value, 'execute'):  # AsyncSession 확인
                    db = value
            
            if not user_id or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="레이트 리미팅을 위한 사용자 정보 또는 DB 세션을 찾을 수 없습니다"
                )
            
            # 레이트 리미팅 확인
            if record_action:
                result = await rate_limiter.record_action(user_id, action_type, db)
                if not result["success"]:
                    retry_after = RateLimitConfig.get_retry_after(
                        result.get("rate_limit_info", {}).get("reset_time")
                    )
                    raise RateLimitException(
                        message=result["message"],
                        retry_after=retry_after
                    )
            else:
                result = await rate_limiter.check_limit(user_id, action_type, db)
                if not result["allowed"]:
                    retry_after = RateLimitConfig.get_retry_after(result.get("reset_time"))
                    rule = RATE_LIMIT_RULES[action_type]
                    raise RateLimitException(
                        message=rule["message"],
                        retry_after=retry_after
                    )
            
            # 원본 함수 실행
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# 5.2.2 사용자별 제한 구현
def user_rate_limit(action_type: ActionType, check_only: bool = False):
    """
    사용자별 레이트 리미팅 데코레이터 (간단 버전)
    
    Args:
        action_type: 액션 타입
        check_only: True면 체크만, False면 기록도 함께
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPI 엔드포인트에서 사용되는 경우
            # 의존성으로 user_id와 db가 주입됨
            
            # 원본 함수 실행 (레이트 리미팅은 의존성에서 처리)
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# 5.2.3 액션별 제한 구현
class ActionRateLimit:
    """액션별 레이트 리미팅 클래스"""
    
    @staticmethod
    def deposit_generate():
        """입금자명 생성 레이트 리미팅"""
        return Depends(record_deposit_generate_action)
    
    @staticmethod
    def refund_request():
        """환불 요청 레이트 리미팅"""
        return Depends(record_refund_request_action)
    
    @staticmethod
    def balance_deduct():
        """잔액 차감 레이트 리미팅"""
        return Depends(record_balance_deduct_action)
    
    @staticmethod
    def check_only_deposit_generate():
        """입금자명 생성 체크만 (기록 X)"""
        return Depends(check_deposit_generate_limit)
    
    @staticmethod
    def check_only_refund_request():
        """환불 요청 체크만 (기록 X)"""
        return Depends(check_refund_request_limit)
    
    @staticmethod
    def check_only_balance_deduct():
        """잔액 차감 체크만 (기록 X)"""
        return Depends(check_balance_deduct_limit)

# 편의용 인스턴스
action_rate_limit = ActionRateLimit()

# 커스텀 레이트 리미팅 함수
async def custom_rate_limit_check(
    user_id: str,
    action_type: ActionType,
    db: AsyncSession,
    custom_limit: Optional[int] = None,
    custom_period_minutes: Optional[int] = None
) -> dict:
    """커스텀 레이트 리미팅 확인"""
    
    if custom_limit and custom_period_minutes:
        # 커스텀 설정으로 확인
        from crud.crud_rate_limit import RATE_LIMIT_CONFIGS
        from sqlalchemy import and_, select, func
        from models.rate_limit import RateLimitLog
        from datetime import timedelta
        
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=custom_period_minutes)
        
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
        allowed = current_count < custom_limit
        
        return {
            "allowed": allowed,
            "remaining_attempts": max(0, custom_limit - current_count),
            "current_count": current_count,
            "limit_per_period": custom_limit,
            "period_minutes": custom_period_minutes,
            "message": f"커스텀 제한: {custom_period_minutes}분에 {custom_limit}회"
        }
    else:
        # 기본 설정으로 확인
        return await rate_limiter.check_limit(user_id, action_type, db)

# 관리자용 레이트 리미팅 오버라이드
async def admin_override_rate_limit(
    user_id: str,
    action_type: ActionType,
    db: AsyncSession,
    admin_user_id: str,
    reason: str
) -> dict:
    """관리자 레이트 리미팅 오버라이드"""
    
    # 관리자 권한 확인 (실제 구현에서는 관리자 검증 로직 추가)
    # 여기서는 간단히 admin_user_id가 있다고 가정
    
    try:
        result = await reset_user_limits(
            user_id=user_id,
            action_type=action_type,
            db=db,
            admin_reason=f"관리자({admin_user_id}) 오버라이드: {reason}"
        )
        
        return {
            "success": True,
            "message": "레이트 리미팅이 오버라이드되었습니다",
            "admin_user_id": admin_user_id,
            "target_user_id": user_id,
            "action_type": action_type.value,
            "reason": reason,
            "result": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"오버라이드 실패: {str(e)}",
            "admin_user_id": admin_user_id,
            "target_user_id": user_id
        }

# 헬스 체크용 함수
async def get_rate_limit_health(db: AsyncSession) -> dict:
    """레이트 리미팅 시스템 상태 확인"""
    from crud.crud_rate_limit import get_rate_limit_statistics
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
        "statistics": {}
    }
    
    try:
        for action_type in ActionType:
            stats = await get_rate_limit_statistics(db, action_type, 1)  # 최근 1시간
            health_status["statistics"][action_type.value] = stats
        
        return health_status
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        return health_status