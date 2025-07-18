from pydantic import BaseModel
from datetime import datetime

class CoupleCreate(BaseModel):
    user1_id: str
    user2_id: str
    user1_nickname: str
    user2_nickname: str

class CoupleRead(BaseModel):
    couple_id: int
    user1_id: str
    user2_id: str
    user1_nickname: str
    user2_nickname: str
    created_at: datetime

    class Config:
        from_attributes = True