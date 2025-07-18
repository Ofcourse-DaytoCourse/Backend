from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# 사용자 프로필 스키마
class UserProfile(BaseModel):
    gender: Optional[str] = None
    age: Optional[int] = None
    mbti: Optional[str] = None
    address: Optional[str] = None
    car_owned: Optional[bool] = None
    description: Optional[str] = None
    relationship_stage: Optional[str] = None
    general_preferences: Optional[List[str]] = None
    profile_image_url: Optional[str] = None
    atmosphere: Optional[str] = None
    budget: Optional[str] = None
    time_slot: Optional[str] = None
    duration: Optional[str] = None  # 데이트 시간 (2시간, 3시간, 반나절 등)
    transportation: Optional[str] = None
    place_count: Optional[int] = None

# 새 채팅 세션 생성 요청
class ChatSessionCreate(BaseModel):
    user_id: str
    initial_message: str
    user_profile: Optional[UserProfile] = None

# 메시지 전송 요청
class ChatMessageCreate(BaseModel):
    session_id: str
    message: str
    user_id: str
    user_profile: Optional[UserProfile] = None

# 코스 추천 시작 요청
class ChatRecommendationStart(BaseModel):
    session_id: str

# 채팅 응답 스키마
class ChatResponse(BaseModel):
    message: Union[str, Dict[str, Any]]
    message_type: str
    quick_replies: Optional[List[str]] = None
    processing_time: Optional[float] = None
    course_data: Optional[Dict[str, Any]] = None

# 세션 정보 스키마
class SessionInfo(BaseModel):
    session_title: str
    session_status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    message_count: int
    has_course: bool = False

# 채팅 세션 응답
class ChatSessionResponse(BaseModel):
    success: bool
    session_id: str
    response: ChatResponse
    session_info: SessionInfo

# 메시지 응답
class ChatMessageResponse(BaseModel):
    success: bool
    session_id: str
    response: ChatResponse
    session_info: SessionInfo

# 코스 추천 응답
class ChatRecommendationResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    course_data: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None
    processing_info: Optional[Dict[str, Any]] = None

# 세션 목록 조회 응답
class ChatSessionListResponse(BaseModel):
    success: bool
    sessions: List[Dict[str, Any]]
    pagination: Optional[Dict[str, Any]] = None

# 세션 상세 조회 응답
class ChatSessionDetailResponse(BaseModel):
    success: bool
    session: Dict[str, Any]
    messages: List[Dict[str, Any]]

# 에러 응답
class ChatErrorResponse(BaseModel):
    success: bool = False
    error: Dict[str, Any]
    timestamp: datetime

# 건강 상태 체크 응답
class ChatHealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]
    metrics: Dict[str, Any]