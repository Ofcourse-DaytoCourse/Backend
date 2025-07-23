from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


# SharedCourse 스키마들
class SharedCourseCreate(BaseModel):
    course_id: int
    title: str = Field(..., max_length=200)
    description: str
    preview_image_url: Optional[str] = None
    price: int = 300
    reward_per_save: int = 100

class SharedCourseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    preview_image_url: Optional[str] = None
    price: Optional[int] = None
    is_active: Optional[bool] = None

class SharedCourseResponse(BaseModel):
    id: int
    course_id: int
    shared_by_user_id: str
    title: str
    description: str
    preview_image_url: Optional[str]
    price: int
    reward_per_save: int
    view_count: int
    purchase_count: int
    save_count: int
    is_active: bool
    shared_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# SharedCourseReview 스키마들
class SharedCourseReviewForCreate(BaseModel):
    """공유 코스 생성 시 사용하는 후기 스키마 (shared_course_id 없음)"""
    rating: int = Field(..., ge=1, le=5)
    review_text: str = Field(..., min_length=15)
    tags: List[str] = []
    photo_urls: List[str] = []

class SharedCourseReviewCreate(BaseModel):
    """일반적인 후기 생성 시 사용하는 스키마 (shared_course_id 포함)"""
    shared_course_id: int
    rating: int = Field(..., ge=1, le=5)
    review_text: str = Field(..., min_length=15)
    tags: List[str] = []
    photo_urls: List[str] = []

    @validator('photo_urls')
    def validate_photos(cls, v):
        if len(v) > 3:
            raise ValueError('최대 3개의 사진만 업로드 가능합니다.')
        return v

class SharedCourseReviewResponse(BaseModel):
    id: int
    user_id: str
    shared_course_id: int
    rating: int
    review_text: str
    tags: List[str]
    photo_urls: List[str]
    is_deleted: bool
    credit_given: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# CoursePurchase 스키마들
class CoursePurchaseCreate(BaseModel):
    shared_course_id: int

class CoursePurchaseResponse(BaseModel):
    id: int
    buyer_user_id: str
    shared_course_id: int
    copied_course_id: int
    purchase_amount: int
    is_saved: bool
    creator_reward_given: bool
    purchased_at: datetime
    saved_at: Optional[datetime]

    class Config:
        from_attributes = True


# CourseBuyerReview 스키마들
class CourseBuyerReviewCreate(BaseModel):
    shared_course_id: int
    purchase_id: int
    rating: int = Field(..., ge=1, le=5)
    review_text: str = Field(..., min_length=15)
    tags: List[str] = []
    photo_urls: List[str] = []

    @validator('photo_urls')
    def validate_photos(cls, v):
        if len(v) > 3:
            raise ValueError('최대 3개의 사진만 업로드 가능합니다.')
        return v

class CourseBuyerReviewResponse(BaseModel):
    id: int
    buyer_user_id: str
    shared_course_id: int
    purchase_id: int
    rating: int
    review_text: str
    tags: List[str]
    photo_urls: List[str]
    is_deleted: bool
    credit_given: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 창작자 후기 객체 스키마
class CreatorReviewResponse(BaseModel):
    rating: int
    review_text: str
    tags: List[str] = []
    created_at: datetime

class SharedCourseStatsResponse(BaseModel):
    id: int  # 프론트엔드 호환성을 위해 추가
    shared_course_id: int
    title: str
    shared_by_user_id: str
    view_count: int
    purchase_count: int
    save_count: int
    price: int
    shared_at: datetime
    creator_rating: Optional[int]
    creator_review_text: Optional[str]
    buyer_review_count: int
    avg_buyer_rating: Optional[float]
    overall_rating: Optional[float]

    class Config:
        from_attributes = True

# 통계 및 목록 조회용 스키마들
class SharedCourseListResponse(BaseModel):
    courses: List[SharedCourseStatsResponse]
    total_count: int
    page: int
    limit: int

# 구매 상태 정보
class PurchaseStatusResponse(BaseModel):
    is_purchased: bool
    can_purchase: bool  
    is_saved: bool

# 코스 장소 정보
class CoursePlace(BaseModel):
    sequence: int
    name: str
    address: str
    category: str
    phone: Optional[str] = None
    estimated_duration: Optional[int] = None
    estimated_cost: Optional[int] = None
    coordinates: Optional[dict] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    kakao_url: Optional[str] = None

# 코스 정보
class CourseInfo(BaseModel):
    course_id: int
    title: str
    description: str
    places: List[CoursePlace]

# 상세 조회용 확장 스키마 (창작자 후기 포함)
class SharedCourseDetailResponse(BaseModel):
    id: int
    course_id: int
    shared_by_user_id: str
    title: str
    description: str
    preview_image_url: Optional[str]
    price: int
    reward_per_save: int
    view_count: int
    purchase_count: int
    save_count: int
    is_active: bool
    shared_at: datetime
    updated_at: datetime
    
    # 평점 정보
    overall_rating: Optional[float]
    creator_rating: Optional[int]
    avg_buyer_rating: Optional[float]
    buyer_review_count: int
    
    # 창작자 후기 정보
    creator_review: Optional[CreatorReviewResponse] = None
    
    # 구매자 후기들
    buyer_reviews: List[CourseBuyerReviewResponse] = []
    
    # 구매 상태 정보
    purchase_status: PurchaseStatusResponse
    
    # 코스 정보 (구매한 경우만)
    course: Optional[CourseInfo] = None

    class Config:
        from_attributes = True