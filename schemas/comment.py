from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CommentBase(BaseModel):
    course_id: int
    user_id: str
    nickname: str
    comment: str

class CommentCreate(CommentBase):
    timestamp: Optional[datetime] = None

class CommentRead(CommentBase):
    comment_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ✅ 프론트 명세에 맞춘 댓글 삭제용 스키마
class CommentDelete(CommentBase):
    timestamp: str  # DELETE 명세엔 ISO 문자열로 보내는 형태라 str로 선언
