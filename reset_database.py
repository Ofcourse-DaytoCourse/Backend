#!/usr/bin/env python3
"""
데이터베이스 스키마 재설정 스크립트
Place 모델 변경사항 적용을 위해 DB를 초기화합니다.

⚠️ 주의: 모든 데이터가 삭제됩니다!

사용법:
python reset_database.py
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.user import User
from models.place_category import PlaceCategory
from models.place import Place
from models.place_category_relation import PlaceCategoryRelation
from models.course import Course
from models.course_place import CoursePlace
from models.chat_session import ChatSession
from models.comment import Comment
from models.couple_request import CoupleRequest
from models.couple import Couple
from models.user_oauth import UserOAuth

# 기본 카테고리 데이터
DEFAULT_CATEGORIES = [
    (1, "기타"),
    (2, "문화시설"),
    (3, "쇼핑"),
    (4, "술집"),
    (5, "야외활동"),
    (6, "엔터테인먼트"),
    (7, "음식점"),
    (8, "카페"),
    (9, "휴식시설")
]


async def reset_database():
    """데이터베이스 스키마 재설정"""
    
    # SQLite 파일 경로
    db_file = Path("dev.db")
    
    print("🔄 데이터베이스 재설정 시작...")
    
    # 확인
    if db_file.exists():
        confirm = input(f"⚠️  {db_file} 파일을 삭제하고 새로 생성하시겠습니까? (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("❌ 작업 취소됨")
            return
        
        # 기존 DB 파일 삭제
        try:
            os.remove(db_file)
            print(f"  ✅ 기존 DB 파일 삭제: {db_file}")
        except Exception as e:
            print(f"  ❌ DB 파일 삭제 실패: {e}")
            return
    
    # 비동기 엔진 생성
    DATABASE_URL = f"sqlite+aiosqlite:///./{db_file}"
    engine = create_async_engine(DATABASE_URL)
    
    try:
        # 테이블 생성
        print("📋 테이블 생성 중...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("  ✅ 모든 테이블 생성 완료")
        
        # 기본 카테고리 데이터 삽입
        print("📁 기본 카테고리 생성 중...")
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            for category_id, category_name in DEFAULT_CATEGORIES:
                category = PlaceCategory(
                    category_id=category_id,
                    category_name=category_name
                )
                session.add(category)
                print(f"  ✅ 카테고리 추가: {category_name} (ID: {category_id})")
            
            await session.commit()
        
        print("🎉 데이터베이스 재설정 완료!")
        print("💡 이제 load_places_data.py를 실행하여 장소 데이터를 로딩하세요.")
        
    except Exception as e:
        print(f"❌ 데이터베이스 재설정 실패: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("=" * 50)
    print("🔄 데이터베이스 재설정 도구")
    print("=" * 50)
    
    # 비동기 실행
    asyncio.run(reset_database())
    
    print("\n✨ 작업 완료!")