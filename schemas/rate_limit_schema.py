from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from enum import Enum

# 레이트 리미팅 관련 Enum 정의
class ActionType(str, Enum):
    """레이트 리미팅 액션 타입"""
    DEPOSIT_GENERATE = "deposit_generate"
    REFUND_REQUEST = "refund_request"
    BALANCE_DEDUCT = "balance_deduct"
    REVIEW_VALIDATION = "review_validation"

# RateLimitLog 스키마
class RateLimitLogCreate(BaseModel):
    """레이트 리미팅 로그 생성 스키마"""
    user_id: str
    action_type: ActionType
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자 ID를 입력해주세요')
        return v.strip()

class RateLimitLogResponse(BaseModel):
    """레이트 리미팅 로그 응답 스키마"""
    rate_limit_log_id: int
    user_id: str
    action_type: ActionType
    created_at: datetime
    expires_at: datetime
    
    # 추가 정보
    is_expired: bool = False
    remaining_hours: int = 0
    
    class Config:
        orm_mode = True
        use_enum_values = True

# 레이트 리미팅 검증 스키마
class RateLimitCheckRequest(BaseModel):
    """레이트 리미팅 확인 요청 스키마"""
    user_id: str
    action_type: ActionType
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('사용자 ID를 입력해주세요')
        return v.strip()

class RateLimitCheckResponse(BaseModel):
    """레이트 리미팅 확인 응답 스키마"""
    allowed: bool
    remaining_attempts: int
    reset_time: Optional[datetime] = None
    message: str
    
    # 현재 제한 상태 정보
    current_count: int = 0
    limit_per_period: int = 0
    period_minutes: int = 0

class RateLimitConfig(BaseModel):
    """레이트 리미팅 설정 스키마"""
    action_type: ActionType
    max_attempts: int
    period_minutes: int
    description: str
    
    @validator('max_attempts')
    def validate_max_attempts(cls, v):
        if v <= 0:
            raise ValueError('최대 시도 횟수는 0보다 커야 합니다')
        if v > 1000:
            raise ValueError('최대 시도 횟수는 1000을 초과할 수 없습니다')
        return v
    
    @validator('period_minutes')
    def validate_period_minutes(cls, v):
        if v <= 0:
            raise ValueError('제한 기간(분)은 0보다 커야 합니다')
        if v > 1440:  # 24시간
            raise ValueError('제한 기간은 24시간(1440분)을 초과할 수 없습니다')
        return v

# 레이트 리미팅 통계 스키마
class RateLimitStatistics(BaseModel):
    """레이트 리미팅 통계 스키마"""
    action_type: ActionType
    total_requests: int = 0
    blocked_requests: int = 0
    unique_users: int = 0
    block_rate: float = 0.0
    
    # 시간대별 통계
    hourly_stats: dict = {}
    daily_stats: dict = {}

class UserRateLimitStatus(BaseModel):
    """사용자별 레이트 리미팅 상태 스키마"""
    user_id: str
    rate_limits: list[RateLimitCheckResponse]
    
    # 전체 상태
    has_active_limits: bool = False
    total_blocked_actions: int = 0

class RateLimitViolation(BaseModel):
    """레이트 리미팅 위반 정보 스키마"""
    user_id: str
    action_type: ActionType
    violation_time: datetime
    attempt_count: int
    limit_exceeded_by: int
    
    class Config:
        orm_mode = True
        use_enum_values = True

# 관리자용 레이트 리미팅 관리 스키마
class RateLimitOverride(BaseModel):
    """레이트 리미팅 오버라이드 스키마 (관리자용)"""
    user_id: str
    action_type: ActionType
    reset_count: bool = False
    extend_period_hours: int = 0
    admin_reason: str
    
    @validator('extend_period_hours')
    def validate_extend_period_hours(cls, v):
        if v < 0:
            raise ValueError('연장 시간은 0 이상이어야 합니다')
        if v > 168:  # 7일
            raise ValueError('연장 시간은 최대 168시간(7일)입니다')
        return v
    
    @validator('admin_reason')
    def validate_admin_reason(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('관리자 사유를 입력해주세요')
        if len(v.strip()) > 500:
            raise ValueError('관리자 사유는 500자를 초과할 수 없습니다')
        return v.strip()

class RateLimitOverrideResponse(BaseModel):
    """레이트 리미팅 오버라이드 응답 스키마"""
    success: bool
    message: str
    user_id: str
    action_type: ActionType
    new_reset_time: Optional[datetime] = None
    logs_cleared: int = 0
    
    class Config:
        use_enum_values = True

# 레이트 리미팅 로그 목록 스키마
class RateLimitLogList(BaseModel):
    """레이트 리미팅 로그 목록 응답 스키마"""
    total: int
    items: list[RateLimitLogResponse]
    page: int
    size: int
    statistics: Optional[RateLimitStatistics] = None

# 레이트 리미팅 설정 목록 스키마
class RateLimitConfigList(BaseModel):
    """레이트 리미팅 설정 목록 스키마"""
    configs: list[RateLimitConfig]
    
    @validator('configs')
    def validate_configs(cls, v):
        if not v:
            raise ValueError('최소 하나의 설정이 필요합니다')
        
        # 액션 타입 중복 확인
        action_types = [config.action_type for config in v]
        if len(action_types) != len(set(action_types)):
            raise ValueError('동일한 액션 타입의 설정이 중복됩니다')
        
        return v

# 실시간 레이트 리미팅 모니터링 스키마
class RateLimitMonitoring(BaseModel):
    """실시간 레이트 리미팅 모니터링 스키마"""
    timestamp: datetime
    active_limits: list[UserRateLimitStatus]
    recent_violations: list[RateLimitViolation]
    system_load: float = 0.0
    
    # 전체 시스템 통계
    total_active_users: int = 0
    total_blocked_requests_last_hour: int = 0