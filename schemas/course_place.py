from pydantic import BaseModel

class CoursePlaceBase(BaseModel):
    course_id: int
    place_id: int
    sequence_order: int
    estimated_duration: int

class CoursePlaceCreate(CoursePlaceBase):
    pass

class CoursePlaceRead(CoursePlaceBase):
    course_place_id: int

    class Config:
        from_attributes = True
