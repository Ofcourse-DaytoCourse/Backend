from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, select, func
from typing import List, Tuple, Optional
import hashlib
from models.place import Place
from models.place_category import PlaceCategory
from models.place_review import PlaceReview
from schemas.place import PlaceCreate, PlaceRead
from utils.redis_client import redis_client

class CRUDPlace:
    async def create_place(self, db: AsyncSession, place_in: PlaceCreate):
        """새로운 장소 생성"""
        db_place = Place(**place_in.dict())
        db.add(db_place)
        await db.commit()
        await db.refresh(db_place)
        return db_place

    async def get_place(self, db: AsyncSession, place_id: str) -> Optional[Place]:
        """장소 ID로 단일 장소 조회"""
        result = await db.execute(
            select(Place)
            .options(selectinload(Place.category))
            .where(Place.place_id == place_id)
        )
        return result.scalar_one_or_none()

    def _generate_cache_key(
        self,
        skip: int,
        limit: int,
        category_id: Optional[int],
        search: Optional[str],
        region: Optional[str],
        sort_by: Optional[str],
        min_rating: Optional[float],
        has_parking: Optional[bool],
        has_phone: Optional[bool]
    ) -> str:
        """캐시 키 생성"""
        params = {
            'skip': skip,
            'limit': limit,
            'category_id': category_id,
            'search': search,
            'region': region,
            'sort_by': sort_by,
            'min_rating': min_rating,
            'has_parking': has_parking,
            'has_phone': has_phone
        }
        # 파라미터를 문자열로 변환하고 해시 생성
        params_str = str(sorted(params.items()))
        hash_obj = hashlib.md5(params_str.encode())
        return f"places_list:{hash_obj.hexdigest()}"

    async def get_places_with_filters(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 20,
        category_id: Optional[int] = None,
        search: Optional[str] = None,
        region: Optional[str] = None,
        sort_by: Optional[str] = "review_count_desc",
        min_rating: Optional[float] = None,
        has_parking: Optional[bool] = None,
        has_phone: Optional[bool] = None
    ) -> Tuple[List[PlaceRead], int]:
        """필터링된 장소 목록 조회 (캐싱 적용)"""
        
        # 캐시 키 생성
        cache_key = self._generate_cache_key(
            skip, limit, category_id, search, region, sort_by, min_rating, has_parking, has_phone
        )
        
        # 캐시에서 조회 시도
        cached_result = redis_client.get(cache_key)
        if cached_result:
            print(f"🚀 캐시에서 장소 목록 조회: {cache_key}")
            places_data = [PlaceRead(**place) for place in cached_result['places']]
            return places_data, cached_result['total_count']
        
        print(f"💾 DB에서 장소 목록 조회 (캐시 미스): {cache_key}")
        # 기본 쿼리
        query = select(Place).options(selectinload(Place.category))
        
        # 카테고리 필터
        if category_id:
            query = query.where(Place.category_id == category_id)
        
        # 검색 필터 (장소명, 주소)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Place.name.ilike(search_term),
                    Place.address.ilike(search_term)
                )
            )
        
        # 지역 필터 (주소에서 구 단위 검색)
        if region:
            query = query.where(Place.address.ilike(f"%{region}%"))
        
        # 주차 필터
        if has_parking is not None:
            query = query.where(Place.is_parking == has_parking)
            
        # 전화번호 필터
        if has_phone is not None:
            if has_phone:
                query = query.where(Place.phone.isnot(None))
                query = query.where(Place.phone != '')
            else:
                query = query.where(or_(Place.phone.is_(None), Place.phone == ''))
        
        # 후기 데이터가 필요한 경우 조인 및 그룹화 처리
        needs_review_join = (
            (min_rating is not None and min_rating > 0) or
            sort_by in ["rating_desc", "review_count_desc"]
        )
        
        if needs_review_join:
            # 후기 테이블과 조인하고 그룹화
            query = query.outerjoin(PlaceReview, Place.place_id == PlaceReview.place_id)\
                         .group_by(Place.place_id)
            
            # 평점 필터
            if min_rating is not None and min_rating > 0:
                query = query.having(func.coalesce(func.avg(PlaceReview.rating), 0) >= min_rating)
            
            # 정렬 처리
            if sort_by == "rating_desc":
                query = query.order_by(func.coalesce(func.avg(PlaceReview.rating), 0).desc())
            elif sort_by == "review_count_desc":
                query = query.order_by(func.count(PlaceReview.id).desc())
            else:
                query = query.order_by(Place.name)
        else:
            # 후기 데이터가 필요 없는 경우
            if sort_by == "latest":
                query = query.order_by(Place.created_at.desc())
            else:  # name 또는 기본값
                query = query.order_by(Place.name)
        
        # 총 개수 조회 (count 쿼리)
        count_query = select(func.count()).select_from(Place)
        if category_id:
            count_query = count_query.where(Place.category_id == category_id)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Place.name.ilike(search_term),
                    Place.address.ilike(search_term)
                )
            )
        if region:
            count_query = count_query.where(Place.address.ilike(f"%{region}%"))
        if has_parking is not None:
            count_query = count_query.where(Place.is_parking == has_parking)
        if has_phone is not None:
            if has_phone:
                count_query = count_query.where(Place.phone.isnot(None))
                count_query = count_query.where(Place.phone != '')
            else:
                count_query = count_query.where(or_(Place.phone.is_(None), Place.phone == ''))
        if min_rating is not None and min_rating > 0:
            # 평점 필터를 count 쿼리에도 적용
            count_query = select(func.count()).select_from(
                select(Place.place_id).outerjoin(PlaceReview, Place.place_id == PlaceReview.place_id)
                .group_by(Place.place_id)
                .having(func.coalesce(func.avg(PlaceReview.rating), 0) >= min_rating)
            )
        
        # 실행
        count_result = await db.execute(count_query)
        total_count = count_result.scalar()
        
        # 페이지네이션 적용하여 데이터 조회
        result = await db.execute(query.offset(skip).limit(limit))
        places = result.scalars().all()
        
        # 모든 장소의 후기 통계를 한 번에 조회 (20배 성능 향상)
        place_ids = [place.place_id for place in places]
        
        if place_ids:
            # 단일 쿼리로 모든 장소의 후기 통계 조회
            review_stats_query = select(
                PlaceReview.place_id,
                func.avg(PlaceReview.rating).label('avg_rating'),
                func.count(PlaceReview.id).label('review_count')
            ).where(PlaceReview.place_id.in_(place_ids)).group_by(PlaceReview.place_id)
            
            review_stats_result = await db.execute(review_stats_query)
            
            # 통계 데이터를 딕셔너리로 변환 (O(1) 조회)
            stats_dict = {}
            for row in review_stats_result:
                stats_dict[row.place_id] = {
                    'avg_rating': round(float(row.avg_rating), 1) if row.avg_rating else 0.0,
                    'review_count': int(row.review_count) if row.review_count else 0
                }
        else:
            stats_dict = {}

        # PlaceRead 스키마로 변환 (통계는 딕셔너리에서 즉시 조회)
        place_reads = []
        for place in places:
            # 통계 데이터 가져오기 (없으면 기본값)
            stats = stats_dict.get(place.place_id, {'avg_rating': 0.0, 'review_count': 0})
            
            place_read = PlaceRead(
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                phone=place.phone,
                description=place.description,
                summary=place.summary,
                is_parking=place.is_parking,
                is_open=place.is_open,
                open_hours=place.open_hours,
                latitude=place.latitude,
                longitude=place.longitude,
                price=place.price,
                info_urls=place.info_urls,
                kakao_url=place.kakao_url,
                category_id=place.category_id,
                category_name=place.category.name if place.category else None,
                created_at=place.created_at,
                updated_at=place.updated_at,
                average_rating=stats['avg_rating'],
                review_count=stats['review_count']
            )
            place_reads.append(place_read)
        
        # 결과를 캐시에 저장 (10분간 유지)
        cache_data = {
            'places': [place.dict() for place in place_reads],
            'total_count': total_count
        }
        redis_client.set(cache_key, cache_data)  # 무제한 저장 (20분마다 갱신)
        print(f"💾 캐시에 장소 목록 저장: {len(place_reads)}개 장소")
        
        return place_reads, total_count
    
    async def get_places_by_ids(self, db: AsyncSession, place_ids: List[str]) -> List[PlaceRead]:
        """place_id 리스트로 장소들 조회 (AI 검색 결과용)"""
        if not place_ids:
            return []
        
        # place_id 리스트로 장소들 조회
        query = (
            select(Place)
            .options(selectinload(Place.category))
            .where(Place.place_id.in_(place_ids))
        )
        
        result = await db.execute(query)
        places = result.scalars().all()
        
        # 리뷰 통계 조회 (평균 평점, 리뷰 수)
        if places:
            review_stats_query = (
                select(
                    PlaceReview.place_id,
                    func.avg(PlaceReview.rating).label('avg_rating'),
                    func.count(PlaceReview.id).label('review_count')
                )
                .where(PlaceReview.place_id.in_(place_ids))
                .group_by(PlaceReview.place_id)
            )
            
            review_stats_result = await db.execute(review_stats_query)
            stats_dict = {}
            for row in review_stats_result:
                stats_dict[row.place_id] = {
                    'avg_rating': round(float(row.avg_rating), 1) if row.avg_rating else 0.0,
                    'review_count': int(row.review_count) if row.review_count else 0
                }
        else:
            stats_dict = {}
        
        # PlaceRead 스키마로 변환
        place_reads = []
        for place in places:
            stats = stats_dict.get(place.place_id, {'avg_rating': 0.0, 'review_count': 0})
            
            place_read = PlaceRead(
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                phone=place.phone,
                description=place.description,
                summary=place.summary,
                is_parking=place.is_parking,
                is_open=place.is_open,
                open_hours=place.open_hours,
                latitude=place.latitude,
                longitude=place.longitude,
                price=place.price,
                info_urls=place.info_urls,
                kakao_url=place.kakao_url,
                category_id=place.category_id,
                category_name=place.category.name if place.category else None,
                created_at=place.created_at,
                updated_at=place.updated_at,
                average_rating=stats['avg_rating'],
                review_count=stats['review_count']
            )
            place_reads.append(place_read)
        
        return place_reads

    async def search_places(
        self, 
        db: AsyncSession, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> Tuple[List[PlaceRead], int]:
        """장소 검색"""
        return await self.get_places_with_filters(
            db=db,
            skip=skip,
            limit=limit,
            search=search_term
        )

    async def update_place(self, db: AsyncSession, place_id: str, place_in: dict):
        """장소 정보 수정"""
        db_place = await self.get_place(db, place_id)
        if not db_place:
            return None
        
        for key, value in place_in.items():
            if hasattr(db_place, key):
                setattr(db_place, key, value)
        
        await db.commit()
        await db.refresh(db_place)
        return db_place

    async def delete_place(self, db: AsyncSession, place_id: str):
        """장소 삭제"""
        db_place = await self.get_place(db, place_id)
        if not db_place:
            return None
        
        await db.delete(db_place)
        await db.commit()
        return db_place

# 싱글톤 인스턴스 생성
place = CRUDPlace()