#!/usr/bin/env python3
"""
장소 데이터 로딩 스크립트
data/ 폴더의 카테고리별 JSON 파일을 읽어서 places 테이블에 저장

사용법:
python load_places_data.py

data/ 폴더 구조:
data/
├── 기타.json
├── 문화시설.json  
├── 쇼핑.json
├── 술집.json
├── 야외활동.json
├── 엔터테인먼트.json
├── 음식점.json
├── 카페.json
└── 휴식시설.json
"""

import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from db.session import get_db
from models.place import Place
from models.place_category import PlaceCategory
from models.place_category_relation import PlaceCategoryRelation


# 카테고리 매핑
CATEGORY_MAPPING = {
    "기타": 1,
    "문화시설": 2,
    "쇼핑": 3, 
    "술집": 4,
    "야외활동": 5,
    "엔터테인먼트": 6,
    "음식점": 7,
    "카페": 8,
    "휴식시설": 9
}


def get_category_ids_from_place_id(place_id: str) -> List[int]:
    """place_id에서 카테고리 추론 (최대 2개)"""
    categories = []
    
    if "문화,예술" in place_id or "문화시설" in place_id:
        categories.append(2)  # 문화시설
    if "음식점" in place_id:
        categories.append(7)  # 음식점
    if "카페" in place_id:
        categories.append(8)  # 카페
    if "술집" in place_id:
        categories.append(4)  # 술집
    if "쇼핑" in place_id:
        categories.append(3)  # 쇼핑
    if "여행" in place_id or "야외" in place_id:
        categories.append(5)  # 야외활동
    if "엔터" in place_id:
        categories.append(6)  # 엔터테인먼트
    if "휴식" in place_id:
        categories.append(9)  # 휴식시설
    
    # 카테고리가 없으면 기타 추가
    if not categories:
        categories.append(1)  # 기타
    
    # 최대 2개까지만 반환
    return categories[:2]


async def ensure_categories_exist(db: AsyncSession):
    """카테고리가 존재하지 않으면 생성"""
    print("🔍 카테고리 확인 및 생성...")
    
    for category_name, category_id in CATEGORY_MAPPING.items():
        # 카테고리 존재 확인
        result = await db.execute(
            select(PlaceCategory).where(PlaceCategory.category_id == category_id)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            # 카테고리 생성
            new_category = PlaceCategory(
                category_id=category_id,
                category_name=category_name
            )
            db.add(new_category)
            print(f"  ✅ 카테고리 생성: {category_name} (ID: {category_id})")
        else:
            print(f"  ✓ 카테고리 존재: {category_name} (ID: {category_id})")
    
    await db.commit()


async def clear_existing_places(db: AsyncSession):
    """기존 places 데이터 삭제 (clean start)"""
    print("🗑️  기존 places 데이터 삭제...")
    
    # place_category_relations 먼저 삭제 (외래키 제약조건)
    await db.execute(delete(PlaceCategoryRelation))
    # course_places 먼저 삭제 (외래키 제약조건)
    await db.execute(delete(Place))
    await db.commit()
    print("  ✅ 기존 데이터 삭제 완료")


def validate_place_data(place_data: Dict[str, Any]) -> bool:
    """장소 데이터 유효성 검사"""
    required_fields = ["place_id", "name"]
    
    for field in required_fields:
        if not place_data.get(field):
            print(f"  ❌ 필수 필드 누락: {field} in {place_data}")
            return False
    
    return True


def process_place_data(place_data: Dict[str, Any], file_category: str) -> tuple[Dict[str, Any], List[int]]:
    """JSON 데이터를 DB 형식으로 변환 (장소 데이터 + 카테고리 ID 목록)"""
    
    # 카테고리 ID 결정 (파일명 우선, place_id로 추론 보조)
    category_ids = []
    
    # 1차 카테고리: 파일명 기반
    primary_category_id = CATEGORY_MAPPING.get(file_category)
    if primary_category_id:
        category_ids.append(primary_category_id)
    
    # 2차 카테고리: place_id 기반으로 추론
    inferred_categories = get_category_ids_from_place_id(place_data.get("place_id", ""))
    for cat_id in inferred_categories:
        if cat_id not in category_ids:
            category_ids.append(cat_id)
            break  # 2차 카테고리 하나만 추가
    
    # 카테고리가 없으면 기타 추가
    if not category_ids:
        category_ids.append(1)  # 기타
    
    # 최대 2개까지만
    category_ids = category_ids[:2]
    
    # 좌표 문자열 → Float 변환
    latitude = None
    longitude = None
    try:
        if place_data.get("latitude"):
            latitude = float(place_data["latitude"])
        if place_data.get("longitude"):
            longitude = float(place_data["longitude"])
    except (ValueError, TypeError):
        print(f"  ⚠️  좌표 변환 실패: {place_data.get('place_id')}")
    
    place_data_processed = {
        "place_id": place_data["place_id"],
        "name": place_data["name"],
        "address": place_data.get("address"),
        "kakao_url": place_data.get("kakao_url"),
        "latitude": latitude,
        "longitude": longitude,
        "price": place_data.get("price", []),
        "description": place_data.get("description", ""),
        "summary": place_data.get("summary", ""),
        "category_id": category_ids[0],  # 기존 호환성을 위해 1차 카테고리 유지
        "phone": "",
        "is_parking": False,
        "is_open": True,
        "open_hours": None,
        "info_urls": []
    }
    
    return place_data_processed, category_ids


async def load_category_file(db: AsyncSession, file_path: Path) -> int:
    """카테고리별 JSON 파일 로딩"""
    category_name = file_path.stem  # 파일명에서 확장자 제거
    
    print(f"📂 {category_name}.json 로딩 중...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            places_data = json.load(f)
        
        if not isinstance(places_data, list):
            print(f"  ❌ {file_path} 형식 오류: 배열이 아님")
            return 0
        
        loaded_count = 0
        for place_data in places_data:
            # 데이터 유효성 검사
            if not validate_place_data(place_data):
                continue
            
            # 데이터 변환
            processed_data, category_ids = process_place_data(place_data, category_name)
            
            # 중복 확인
            result = await db.execute(
                select(Place).where(Place.place_id == processed_data["place_id"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"  ⚠️  중복 place_id 건너뛰기: {processed_data['place_id']}")
                continue
            
            # DB에 저장
            place = Place(**processed_data)
            db.add(place)
            
            # 카테고리 관계 저장
            for priority, category_id in enumerate(category_ids, 1):
                relation = PlaceCategoryRelation(
                    place_id=processed_data["place_id"],
                    category_id=category_id,
                    priority=priority
                )
                db.add(relation)
            
            loaded_count += 1
        
        await db.commit()
        print(f"  ✅ {category_name}: {loaded_count}개 장소 로딩 완료")
        return loaded_count
        
    except FileNotFoundError:
        print(f"  ❌ 파일 없음: {file_path}")
        return 0
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 파싱 오류: {file_path} - {e}")
        return 0
    except Exception as e:
        print(f"  ❌ 로딩 실패: {file_path} - {e}")
        await db.rollback()
        return 0


async def load_all_places_data():
    """전체 장소 데이터 로딩 메인 함수"""
    print("🚀 장소 데이터 로딩 시작...")
    
    # data 폴더 확인
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"❌ data 폴더가 없습니다: {data_dir.absolute()}")
        print("📁 data/ 폴더를 생성하고 카테고리별 JSON 파일을 넣어주세요.")
        return
    
    # DB 세션 생성
    async for db in get_db():
        try:
            # 1. 카테고리 확인/생성
            await ensure_categories_exist(db)
            
            # 2. 기존 데이터 삭제 (선택사항)
            clear_data = input("기존 places 데이터를 삭제하고 새로 로딩하시겠습니까? (y/N): ")
            if clear_data.lower() in ['y', 'yes']:
                await clear_existing_places(db)
            
            # 3. 카테고리별 파일 로딩
            total_loaded = 0
            for category_name in CATEGORY_MAPPING