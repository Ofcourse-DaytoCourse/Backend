"""
장소 관련 API 라우터
장소 검색, 조회, 필터링 기능 제공
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from db.session import get_db
from models.place import Place
from models.place_category import PlaceCategory
from schemas.place import PlaceRead, PlaceListResponse
from crud.crud_place import place as place_crud
from auth.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/places", tags=["places"])


@router.get("/", response_model=PlaceListResponse)
async def get_places(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(20, ge=1, le=100, description="가져올 항목 수"),
    category_id: Optional[int] = Query(None, description="카테고리 ID"),
    search: Optional[str] = Query(None, description="장소명 검색어"),
    region: Optional[str] = Query(None, description="지역 필터 (구 단위)"),
    sort_by: Optional[str] = Query("name", description="정렬 방식: name, rating_desc, review_count_desc, latest"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="최소 평점 필터"),
    has_parking: Optional[bool] = Query(None, description="주차 가능 여부 필터"),
    has_phone: Optional[bool] = Query(None, description="전화번호 유무 필터"),
    db: AsyncSession = Depends(get_db)
):
    """
    장소 목록 조회 API
    
    - **skip**: 페이지네이션을 위한 건너뛸 항목 수
    - **limit**: 한 페이지에 표시할 항목 수 (최대 100)
    - **category_id**: 특정 카테고리의 장소만 조회
    - **search**: 장소명으로 검색
    - **region**: 지역별 필터링 (예: "강남구", "홍대")
    - **sort_by**: 정렬 방식 (name, rating_desc, review_count_desc, latest)
    - **min_rating**: 최소 평점 필터
    - **has_parking**: 주차 가능 여부 필터
    - **has_phone**: 전화번호 유무 필터
    """
    try:
        places, total_count = await place_crud.get_places_with_filters(
            db=db,
            skip=skip,
            limit=limit,
            category_id=category_id,
            search=search,
            region=region,
            sort_by=sort_by,
            min_rating=min_rating,
            has_parking=has_parking,
            has_phone=has_phone
        )
        
        return PlaceListResponse(
            places=places,
            total_count=total_count,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"장소 목록 조회 중 오류가 발생했습니다: {str(e)}")


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place_detail(
    place_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    장소 상세 정보 조회 API
    
    - **place_id**: 조회할 장소의 고유 ID
    """
    place = await place_crud.get_place(db=db, place_id=place_id)
    if not place:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다.")
    
    return place


@router.get("/search/", response_model=PlaceListResponse)
async def search_places(
    q: str = Query(..., min_length=1, description="검색어"),
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(20, ge=1, le=100, description="가져올 항목 수"),
    db: AsyncSession = Depends(get_db)
):
    """
    장소 검색 API
    
    - **q**: 검색어 (장소명, 주소에서 검색)
    - **skip**: 페이지네이션을 위한 건너뛸 항목 수
    - **limit**: 한 페이지에 표시할 항목 수
    """
    try:
        places, total_count = await place_crud.search_places(
            db=db,
            search_term=q,
            skip=skip,
            limit=limit
        )
        
        return PlaceListResponse(
            places=places,
            total_count=total_count,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"장소 검색 중 오류가 발생했습니다: {str(e)}")


@router.get("/categories/", response_model=List[dict])
async def get_place_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    장소 카테고리 목록 조회 API
    """
    try:
        result = await db.execute(select(PlaceCategory))
        categories = result.scalars().all()
        return [
            {
                "category_id": category.category_id,
                "name": category.category_name,  # category.name → category.category_name
                "description": getattr(category, 'description', '')  # description 필드가 없을 수도 있음
            }
            for category in categories
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테고리 조회 중 오류가 발생했습니다: {str(e)}")