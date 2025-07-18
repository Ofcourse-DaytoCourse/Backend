from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일 로드

CONFIGS = {
    "development": {
        "api_url": "http://localhost:8000",
        "frontend_url": "http://localhost:3000",  # 프론트엔드 개발 주소
        "debug": True,
        "database_url": os.getenv("DATABASE_URL", "postgresql+asyncpg://daytocourse_user:daytocourse_pass@localhost:5433/daytocourse"),
        "backend_host": "0.0.0.0",
        "backend_port": 8000,
        # .env 값 config에 통합!
        "kakao_rest_api_key": os.getenv("KAKAO_REST_API_KEY"),
        "kakao_redirect_uri": os.getenv("KAKAO_REDIRECT_URI"),
        "jwt_secret": os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production-2024"),
    },
    "production": {
        "api_url": "https://api.example.com",
        "frontend_url": "https://myapp.com",  # 프론트엔드 배포 주소
        "debug": False,
        "database_url": "postgresql+asyncpg://user:password@localhost:5432/dating_app_db",
        "backend_host": "0.0.0.0",
        "backend_port": 80,
        "kakao_rest_api_key": os.getenv("KAKAO_REST_API_KEY"),
        "kakao_redirect_uri": os.getenv("KAKAO_REDIRECT_URI"),
        "jwt_secret": os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production-2024"),
    },
}

CURRENT_ENV = "development"  # production으로 바꾸면 배포환경 설정 사용

config = CONFIGS[CURRENT_ENV]

# 선택: 전역 속성으로 꺼내서 쓸 수도 있어
API_URL = config["api_url"]
FRONTEND_URL = config["frontend_url"]
DEBUG = config["debug"]
DATABASE_URL = config["database_url"]
BACKEND_HOST = config["backend_host"]
BACKEND_PORT = config["backend_port"]
KAKAO_REST_API_KEY = config["kakao_rest_api_key"]
KAKAO_REDIRECT_URI = config["kakao_redirect_uri"]
JWT_SECRET = config["jwt_secret"]
