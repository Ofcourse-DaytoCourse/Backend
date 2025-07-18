#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 초기화 스크립트
기존 reset_database.py를 PostgreSQL용으로 수정
"""
import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.base import Base
from config import DATABASE_URL

async def reset_postgresql_database():
    """PostgreSQL 데이터베이스 완전 초기화"""
    print("🔄 PostgreSQL 데이터베이스 초기화 시작...")
    
    try:
        # 1. 데이터베이스 연결 테스트
        print("📡 PostgreSQL 연결 테스트...")
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        # 2. 모든 테이블 삭제 및 재생성
        print("🗑️  기존 테이블 삭제...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            
        print("🏗️  새 테이블 생성...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        print("✅ PostgreSQL 데이터베이스 초기화 완료!")
        
        # 3. 테이블 확인
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = result.fetchall()
            print(f"📋 생성된 테이블: {[t[0] for t in tables]}")
            
        await engine.dispose()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 해결방법:")
        print("   1. PostgreSQL이 실행 중인지 확인: docker compose ps")
        print("   2. 연결 정보 확인: config.py의 DATABASE_URL")
        print("   3. 포트 충돌 확인: lsof -i :5432")
        raise

if __name__ == "__main__":
    # SQLAlchemy text import 추가
    from sqlalchemy import text
    
    print("🚀 PostgreSQL 데이터베이스 리셋 시작")
    asyncio.run(reset_postgresql_database())
    print("🎉 완료! 이제 load_places_data.py를 실행하세요.")