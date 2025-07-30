from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# PostgreSQL 최적화 설정
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,             # 프로덕션 환경에서 로그 비활성화
    pool_size=3,            # 커넥션 풀 크기 (20 → 3)
    max_overflow=2,         # 오버플로우 허용 (30 → 2)
    pool_timeout=30,        # 커넥션 대기 시간
    pool_recycle=1800,      # 커넥션 재활용 (30분)
    pool_pre_ping=True,     # 커넥션 유효성 검사
    query_cache_size=0,     # 쿼리 캐시 완전 비활성화
)

SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session
