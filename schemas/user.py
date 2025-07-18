from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    nickname: str
    email: Optional[str] = None

class UserRead(BaseModel):
    user_id: int
    kakao_id: Optional[int]
    nickname: str
    email: Optional[str]

    class Config:
        orm_mode = True

class StatusResponse(BaseModel):
    status: str
    message: Optional[str]

class NicknameCheckRequest(BaseModel):
    nickname: str

class UserProfileSetup(BaseModel):
    nickname: str
    provider_type: str
    provider_user_id: str

class UserProfileDetail(BaseModel):
    age_range: Optional[str] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    car_owner: Optional[bool] = None
    preferences: Optional[str] = None

class CoupleInfo(BaseModel):
    partner_nickname: Optional[str] = None
    couple_id: Optional[int] = None

class UserProfileResponse(BaseModel):
    user_id: int
    nickname: str
    email: Optional[str] = None
    profile_detail: Optional[UserProfileDetail] = None
    couple_info: Optional[CoupleInfo] = None

class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    profile_detail: Optional[UserProfileDetail] = None

class UserDeleteRequest(BaseModel):
    user_id: str
    nickname: str
