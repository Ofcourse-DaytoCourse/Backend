from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime

class ReviewCreateRequest(BaseModel):
    place_id: str
    course_id: int
    rating: int
    review_text: Optional[str] = None
    tags: List[str] = []
    photo_urls: List[str] = []

    @validator('rating')
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

class ReviewResponse(BaseModel):
    id: int
    user_id: str
    place_id: str
    course_id: int
    rating: int
    review_text: Optional[str]
    tags: List[str]
    photo_urls: List[str]
    created_at: datetime
    place_name: Optional[str] = None

    class Config:
        from_attributes = True