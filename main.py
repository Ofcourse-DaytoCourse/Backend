from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
from routers.users import router as users_router

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routers import users, courses, couples, comments, auth, chat
import config  # config.py의 설정 불러오기

# ✅ 모든 모델 임포트 (SQLAlchemy 관계 설정을 위해 필수)
from models.base import Base
from models.user import User
from models.user_oauth import UserOAuth
from models.place_category import PlaceCategory
from models.place import Place
from models.place_category_relation import PlaceCategoryRelation
from models.course import Course
from models.course_place import CoursePlace
from models.chat_session import ChatSession
from models.comment import Comment
from models.couple_request import CoupleRequest
from models.couple import Couple

app = FastAPI(
    title="My Dating App API",
    description="연인 관리, 추천코스, 댓글, 사용자 인증 등 전체 API",
    version="1.0.0",
    debug=config.DEBUG,  # config의 debug 설정 사용
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # 두 포트 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(couples.router)
app.include_router(comments.router)
app.include_router(auth.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {
        "message": "Dating App API is running!",
        "api_url": config.API_URL,
        "kakao_rest_api_key": config.KAKAO_REST_API_KEY,       # Kakao REST API Key 반환 예시
        "kakao_redirect_uri": config.KAKAO_REDIRECT_URI,       # Kakao Redirect URI 반환 예시
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.BACKEND_HOST,   # config에서 host 가져오기
        port=config.BACKEND_PORT,   # config에서 port 가져오기
        reload=True,
    )
