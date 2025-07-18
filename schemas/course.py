from pydantic import BaseModel
from typing import Optional, Any, List

class CourseCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    places: Optional[List[Any]] = []
    total_duration: Optional[int] = 0
    estimated_cost: Optional[int] = 0
    user_request: Optional[str] = None
    preferences: Optional[dict] = {}

class CourseRead(BaseModel):
    course_id: int
    title: str
    description: Optional[str]
    is_shared_with_couple: bool
    user_id: str

    class Config:
        from_attributes = True
