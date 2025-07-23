from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.place_review import PlaceReview
from schemas.place_review import ReviewCreateRequest
from utils.redis_client import redis_client

class CRUDPlaceReview:
    async def create_review(self, db: AsyncSession, user_id: str, review: ReviewCreateRequest):
        try:
            # 1. 외래키 존재 여부 확인
            from models.place import Place
            from models.course import Course
            
            # place_id 존재 확인
            place_result = await db.execute(select(Place).where(Place.place_id == review.place_id))
            if not place_result.scalar_one_or_none():
                raise ValueError(f"place_id '{review.place_id}'가 존재하지 않습니다.")
            
            # course_id 존재 확인  
            course_result = await db.execute(select(Course).where(Course.course_id == review.course_id))
            if not course_result.scalar_one_or_none():
                raise ValueError(f"course_id '{review.course_id}'가 존재하지 않습니다.")
            
            # 2. 중복 후기 확인
            existing_review = await db.execute(
                select(PlaceReview)
                .where(PlaceReview.user_id == user_id)
                .where(PlaceReview.place_id == review.place_id)
                .where(PlaceReview.is_deleted == False)
            )
            if existing_review.scalar_one_or_none():
                raise ValueError(f"이미 해당 장소에 후기를 작성하셨습니다.")
            
            # 3. 후기 생성
            db_review = PlaceReview(
                user_id=user_id,
                place_id=review.place_id,
                course_id=review.course_id,
                rating=review.rating,
                review_text=review.review_text,
                tags=review.tags or [],
                photo_urls=review.photo_urls or []
            )
            db.add(db_review)
            await db.commit()
            await db.refresh(db_review)
            
            # 캐시는 20분마다 자동 갱신되므로 즉시 삭제하지 않음
            
            return db_review
            
        except Exception as e:
            await db.rollback()
            print(f"🔍 후기 작성 오류 상세: {str(e)}")
            print(f"🔍 user_id: {user_id}")
            print(f"🔍 place_id: {review.place_id}")
            print(f"🔍 course_id: {review.course_id}")
            raise e

    async def get_user_reviews(self, db: AsyncSession, user_id: str, skip: int = 0, limit: int = 20):
        from models.place import Place
        
        result = await db.execute(
            select(PlaceReview, Place.name.label('place_name'))
            .join(Place, PlaceReview.place_id == Place.place_id, isouter=True)
            .where(PlaceReview.user_id == user_id)
            .where(PlaceReview.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .order_by(PlaceReview.created_at.desc())
        )
        
        reviews_with_place_names = []
        for row in result.fetchall():
            review = row[0]  # PlaceReview 객체
            place_name = row[1]  # place_name
            
            # 동적으로 place_name 속성 추가
            review.place_name = place_name
            reviews_with_place_names.append(review)
            
        return reviews_with_place_names

    async def get_place_reviews(self, db: AsyncSession, place_id: str, skip: int = 0, limit: int = 20):
        result = await db.execute(
            select(PlaceReview)
            .where(PlaceReview.place_id == place_id)
            .where(PlaceReview.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .order_by(PlaceReview.created_at.desc())
        )
        return result.scalars().all()

    async def update_review(self, db: AsyncSession, review_id: int, user_id: str, review_data: dict):
        result = await db.execute(
            select(PlaceReview)
            .where(PlaceReview.id == review_id)
            .where(PlaceReview.user_id == user_id)
            .where(PlaceReview.is_deleted == False)
        )
        db_review = result.scalar_one_or_none()
        
        if not db_review:
            return None
        
        for key, value in review_data.items():
            if hasattr(db_review, key):
                setattr(db_review, key, value)
        
        await db.commit()
        await db.refresh(db_review)
        
        # 캐시는 20분마다 자동 갱신되므로 즉시 삭제하지 않음
        
        return db_review

    async def delete_review(self, db: AsyncSession, review_id: int, user_id: str):
        result = await db.execute(
            select(PlaceReview)
            .where(PlaceReview.id == review_id)
            .where(PlaceReview.user_id == user_id)
            .where(PlaceReview.is_deleted == False)
        )
        db_review = result.scalar_one_or_none()
        
        if not db_review:
            return None
        
        db_review.is_deleted = True
        await db.commit()
        await db.refresh(db_review)
        
        # 캐시는 20분마다 자동 갱신되므로 즉시 삭제하지 않음
        
        return db_review

    async def reactivate_deleted_review(self, db: AsyncSession, user_id: str, place_id: str, new_review_data):
        """삭제된 후기를 찾아서 내용 수정하고 재활성화"""
        try:
            # 삭제된 후기 찾기
            result = await db.execute(
                select(PlaceReview)
                .where(PlaceReview.user_id == user_id)
                .where(PlaceReview.place_id == place_id)
                .where(PlaceReview.is_deleted == True)
            )
            deleted_review = result.scalar_one_or_none()
            
            if not deleted_review:
                return None
            
            # 내용 업데이트하고 재활성화
            deleted_review.course_id = new_review_data.course_id
            deleted_review.rating = new_review_data.rating
            deleted_review.review_text = new_review_data.review_text
            deleted_review.tags = new_review_data.tags or []
            deleted_review.photo_urls = new_review_data.photo_urls or []
            deleted_review.is_deleted = False  # 재활성화
            
            await db.commit()
            await db.refresh(deleted_review)
            
            # 장소 목록 캐시 무효화
            self._invalidate_places_cache()
            
            return deleted_review
            
        except Exception as e:
            await db.rollback()
            print(f"🔍 후기 재활성화 오류: {str(e)}")
            raise e

place_review = CRUDPlaceReview()