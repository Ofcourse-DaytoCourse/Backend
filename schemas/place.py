from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class PlaceBase(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    is_parking: bool = False
    is_open: bool = True
    open_hours: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price: Optional[List[Dict]] = None
    info_urls: Optional[List[str]] = None
    kakao_url: Optional[str] = None
    category_id: Optional[int] = None

class PlaceCreate(PlaceBase):
    place_id: str  # 카카오 place_id (String 타입)

class PlaceUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    phone: Optional[str] = None
    is_parking: Optional[bool] = None
    is_open: Optional[bool] = None
    open_hours: Optional[str] = None

class PlaceRead(PlaceBase):
    place_id: str  # String 타입으로 수정
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    average_rating: Optional[float] = 0.0  # 평균 평점
    review_count: Optional[int] = 0        # 리뷰 개수

    class Config:
        from_attributes = True

class PlaceListResponse(BaseModel):
    places: List[PlaceRead]
    total_count: int
    skip: int
    limit: int

class AISearchRequest(BaseModel):
    description: str = Field(..., min_length=20, max_length=200, description="장소 검색 설명 (20-200자)")
    district: str = Field(..., description="서울시 구 (예: 강남구)")
    category: Optional[str] = Field(None, description="카테고리 (전체/음식점/카페/문화시설 등)")

class AISearchResponse(BaseModel):
    places: List[PlaceRead]
    cost: int = Field(default=300, description="검색 비용 (원)")
    search_time: float = Field(..., description="검색 소요 시간 (초)")
    total_results: int = Field(..., description="검색된 총 결과 수")
