from dotenv import load_dotenv
import os

load_dotenv()  # .env 파일 로드

# DigitalOcean 환경에서는 환경변수 우선 사용
DATABASE_URL = os.getenv("DATABASE_URL")

CONFIGS = {
    "development": {
        "api_url": "http://localhost:8000",
        "debug": True,
        "database_url": DATABASE_URL,
        "backend_host": "0.0.0.0",
        "backend_port": 8000,
        # .env 값 config에 통합!
        "kakao_rest_api_key": os.getenv("KAKAO_REST_API_KEY"),
        "kakao_redirect_uri": os.getenv("KAKAO_REDIRECT_URI"),
        "jwt_secret": os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production-2024"),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000"),
        
        # 9.1 결제 시스템 환경 변수 추가
        "signup_bonus_amount": int(os.getenv("SIGNUP_BONUS_AMOUNT", "10000")),
        "deposit_expiry_hours": int(os.getenv("DEPOSIT_EXPIRY_HOURS", "1")),
        "sms_parsing_enabled": os.getenv("SMS_PARSING_ENABLED", "true").lower() == "true",
        "default_bank_name": os.getenv("DEFAULT_BANK_NAME", "국민은행"),
        "default_account_number": os.getenv("DEFAULT_ACCOUNT_NUMBER", "12345678901234"),
        
        # 레이트 리미팅 설정
        "rate_limit_enabled": os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        "rate_limit_deposit_generate": os.getenv("RATE_LIMIT_DEPOSIT_GENERATE", "1/minute"),
        "rate_limit_refund_request": os.getenv("RATE_LIMIT_REFUND_REQUEST", "3/hour"),
        "rate_limit_balance_deduct": os.getenv("RATE_LIMIT_BALANCE_DEDUCT", "10/minute"),
        
        # 환불 시스템 설정
        "refund_partial_enabled": os.getenv("REFUND_PARTIAL_ENABLED", "true").lower() == "true",
        "refund_minimum_amount": int(os.getenv("REFUND_MINIMUM_AMOUNT", "1000")),
        "refund_maximum_days": int(os.getenv("REFUND_MAXIMUM_DAYS", "30")),
        
        # 로그 최적화 설정
        "log_cleanup_enabled": os.getenv("LOG_CLEANUP_ENABLED", "true").lower() == "true",
        "rate_limit_log_retention_hours": int(os.getenv("RATE_LIMIT_LOG_RETENTION_HOURS", "24")),
        "unmatched_deposit_retention_days": int(os.getenv("UNMATCHED_DEPOSIT_RETENTION_DAYS", "180")),
        "cleanup_schedule_hours": int(os.getenv("CLEANUP_SCHEDULE_HOURS", "1")),
        
        # 후기 검증 시스템 설정
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "review_validation_enabled": os.getenv("REVIEW_VALIDATION_ENABLED", "true").lower() == "true",
        "review_validation_model": os.getenv("REVIEW_VALIDATION_MODEL", "gpt-3.5-turbo"),
        "review_validation_max_tokens": int(os.getenv("REVIEW_VALIDATION_MAX_TOKENS", "150")),
        
        # RAG 서비스 설정
        "rag_service_url": os.getenv("RAG_SERVICE_URL", "http://localhost:8003"),
    },
    "production": {
        "api_url": "https://api.example.com",
        "frontend_url": "https://myapp.com",  # 프론트엔드 배포 주소
        "debug": False,
        "database_url": DATABASE_URL,
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
FRONTEND_URL = config["frontend_url"]
