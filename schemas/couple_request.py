from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CoupleRequestCreate(BaseModel):
    requester_id: str  # UUID 타입
    partner_nickname: str

class CoupleRequestRead(BaseModel):
    request_id: int
    requester_id: str  # UUID 타입
    partner_nickname: str
    status: str
    requested_at: datetime

    class Config:
        from_attributes = True
