#!/usr/bin/env python3
"""
PostgreSQL용 장소 데이터 로딩 스크립트 (기존 place_id 유지)
JSON 파일의 place_id를 그대로 사용해서 AI 시스템과 호환성 유지
"""
import asyncio
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from models.place import Place
from models.place_category import PlaceCategory
from models.place_category_relation import PlaceCategoryRelation
from config import DATABASE_URL

async def load_places_to_postgresql():
    """PostgreSQL에 장소 데이터 로딩"""
    print("🏗️ PostgreSQL에 장소 데이터 로딩 시작...")
    
    try:
        # 1. 데이터베이스 연결
        engine = create_async_engine(DATABASE_URL, echo=False)  # echo=False로 로그 줄임
        SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        
        # 2. 카테고리는 자체 필드 사용 (기존 카테고리 테이블 사용 안함)
        print("📂 새 카테고리 시스템 사용 (major/middle/minor_category)")
        
        # 3. 장소 데이터 로딩
        data_dir = "./data"
        total_places = 0
        
        if not os.path.exists(data_dir):
            print(f"❌ 데이터 디렉토리가 없습니다: {data_dir}")
            return
        
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                print(f"📥 {filename} 데이터 로딩 중...")
                
                with open(os.path.join(data_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 새 데이터 구조 처리
                places_array = data.get('places', [])
                file_major_category = data.get('major_category', filename.replace('.json', ''))
                
                print(f"   📊 총 {len(places_array)}개 장소 발견")
                
                async with SessionLocal() as session:
                    count = 0
                    for place_data in places_array:
                        try:
                            # place_id 확인 (필수 필드)
                            place_id = place_data.get('place_id')
                            if not place_id:
                                print(f"   ⚠️ place_id 누락: {place_data.get('name', 'Unknown')}")
                                continue
                            
                            # 중복 확인
                            result = await session.execute(
                                select(Place).where(Place.place_id == place_id)
                            )
                            existing_place = result.scalar_one_or_none()
                            
                            if existing_place:
                                print(f"   ⚠️ 중복 place_id 건너뛰기: {place_id}")
                                continue
                            
                            # 좌표 처리
                            latitude = None
                            longitude = None
                            try:
                                if place_data.get('latitude'):
                                    latitude = float(place_data['latitude'])
                                if place_data.get('longitude'):
                                    longitude = float(place_data['longitude'])
                            except (ValueError, TypeError):
                                print(f"   ⚠️ 좌표 변환 실패: {place_id}")
                            
                            # Place 객체 생성 (새 필드 매핑)
                            place = Place(
                                place_id=place_id,  # JSON의 place_id 사용
                                name=place_data.get('name', ''),
                                address=place_data.get('address', ''),
                                description=place_data.get('detailed_description', ''),  # 필드명 변경
                                latitude=latitude,
                                longitude=longitude,
                                phone=place_data.get('phone', ''),
                                kakao_url=place_data.get('kakao_url', ''),
                                is_parking=place_data.get('parking_available', False),  # 필드명 변경
                                is_open=place_data.get('is_open', True),
                                open_hours=place_data.get('open_hours'),
                                price=place_data.get('menu_info', []),  # 필드명 변경
                                summary=place_data.get('gpt_summary', ''),  # 필드명 변경
                                info_urls=place_data.get('info_urls', []),
                                category_id=None,  # 기존 카테고리 시스템 사용 안함
                                
                                # 새 필드들
                                business_hours=place_data.get('business_hours', {}),
                                menu_info=place_data.get('menu_info', []),
                                homepage_url=place_data.get('homepage_url'),
                                kakao_category=place_data.get('kakao_category'),
                                major_category=place_data.get('major_category', file_major_category),
                                middle_category=place_data.get('middle_category'),
                                minor_category=place_data.get('minor_category')
                            )
                            session.add(place)
                            
                            # 기존 카테고리 관계 테이블 사용 안함 (새 필드들로 대체)
                            
                            count += 1
                            
                            # 100개마다 중간 커밋
                            if count % 100 == 0:
                                await session.commit()
                                print(f"   💾 {count}개 저장 중...")
                                
                        except Exception as e:
                            print(f"   ⚠️ 장소 저장 실패: {place_data.get('place_id', 'Unknown')}: {e}")
                            continue
                    
                    await session.commit()
                    total_places += count
                    print(f"✅ {filename}: {count}개 장소 저장 완료")
        
        await engine.dispose()
        print(f"🎉 총 {total_places}개 장소 데이터 로딩 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 해결방법:")
        print("   1. PostgreSQL이 실행 중인지 확인")
        print("   2. reset_database_postgres.py 먼저 실행")
        print("   3. data/ 디렉토리에 JSON 파일들이 있는지 확인")
        raise

if __name__ == "__main__":
    print("🚀 PostgreSQL 장소 데이터 로딩 시작")
    asyncio.run(load_places_to_postgresql())
    print("✨ 모든 작업 완료! 서버를 시작할 수 있습니다.")