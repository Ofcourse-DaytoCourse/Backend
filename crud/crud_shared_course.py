from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from datetime import datetime
import hashlib

from models.shared_course import SharedCourse, SharedCourseReview, CoursePurchase, CourseBuyerReview
from models.course import Course
from models.user import User
from schemas.shared_course_schema import (
    SharedCourseCreate, SharedCourseUpdate,
    SharedCourseReviewCreate, CourseBuyerReviewCreate
)
from utils.redis_client import redis_client


# SharedCourse CRUD
async def create_shared_course(db: AsyncSession, shared_course: SharedCourseCreate, user_id: str):
    """코스 공유 생성"""
    db_shared_course = SharedCourse(
        shared_by_user_id=user_id,
        **shared_course.dict()
    )
    db.add(db_shared_course)
    await db.flush()  # commit 대신 flush
    return db_shared_course


async def get_shared_course(db: AsyncSession, shared_course_id: int):
    """공유 코스 상세 조회"""
    from models.course import Course
    result = await db.execute(
        select(SharedCourse)
        .options(
            selectinload(SharedCourse.course).selectinload(Course.places),
            selectinload(SharedCourse.shared_by_user),
            selectinload(SharedCourse.reviews),
            selectinload(SharedCourse.buyer_reviews)
        )
        .where(and_(SharedCourse.id == shared_course_id, SharedCourse.is_active == True))
    )
    return result.scalar_one_or_none()


async def get_shared_courses(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 20,
    sort_by: str = "latest",
    category: Optional[str] = None,
    min_rating: Optional[float] = None
):
    """공유 코스 목록 조회"""
    query = select(SharedCourse).where(SharedCourse.is_active == True)
    
    # 정렬 옵션
    if sort_by == "latest":
        query = query.order_by(SharedCourse.shared_at.desc())
    elif sort_by == "popular":
        query = query.order_by(SharedCourse.purchase_count.desc())
    elif sort_by == "rating":
        # 통계 뷰에서 평점순 정렬 (추후 구현)
        query = query.order_by(SharedCourse.shared_at.desc())
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    shared_courses = result.scalars().all()
    
    # 총 개수 조회
    count_result = await db.execute(
        select(func.count(SharedCourse.id)).where(SharedCourse.is_active == True)
    )
    total_count = count_result.scalar()
    
    return shared_courses, total_count


async def update_shared_course(db: AsyncSession, shared_course_id: int, update_data: SharedCourseUpdate, user_id: str):
    """공유 코스 업데이트 (소유자만)"""
    result = await db.execute(
        select(SharedCourse).where(
            and_(
                SharedCourse.id == shared_course_id,
                SharedCourse.shared_by_user_id == user_id
            )
        )
    )
    db_shared_course = result.scalar_one_or_none()
    
    if not db_shared_course:
        return None
    
    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(db_shared_course, key, value)
    
    db_shared_course.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(db_shared_course)
    
    return db_shared_course


async def delete_shared_course(db: AsyncSession, shared_course_id: int, user_id: str):
    """공유 코스 삭제 (소프트 삭제)"""
    result = await db.execute(
        select(SharedCourse).where(
            and_(
                SharedCourse.id == shared_course_id,
                SharedCourse.shared_by_user_id == user_id
            )
        )
    )
    db_shared_course = result.scalar_one_or_none()
    
    if not db_shared_course:
        return None
    
    db_shared_course.is_active = False
    await db.commit()
    
    return db_shared_course


# SharedCourseReview CRUD
async def create_shared_course_review(db: AsyncSession, review: SharedCourseReviewCreate, user_id: str):
    """공유자 후기 작성"""
    db_review = SharedCourseReview(
        user_id=user_id,
        **review.dict()
    )
    db.add(db_review)
    await db.flush()  # commit 대신 flush
    return db_review


async def get_shared_course_review_by_course_and_user(db: AsyncSession, shared_course_id: int, user_id: str):
    """특정 사용자의 특정 코스 후기 조회"""
    result = await db.execute(
        select(SharedCourseReview).where(
            and_(
                SharedCourseReview.shared_course_id == shared_course_id,
                SharedCourseReview.user_id == user_id,
                SharedCourseReview.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


# CoursePurchase CRUD
async def create_course_purchase(db: AsyncSession, shared_course_id: int, buyer_user_id: str, copied_course_id: int):
    """코스 구매 기록 생성"""
    db_purchase = CoursePurchase(
        buyer_user_id=buyer_user_id,
        shared_course_id=shared_course_id,
        copied_course_id=copied_course_id,
        purchase_amount=300
    )
    db.add(db_purchase)
    await db.flush()  # commit은 상위에서 처리
    return db_purchase


async def get_course_purchase(db: AsyncSession, shared_course_id: int, buyer_user_id: str):
    """구매 기록 조회"""
    result = await db.execute(
        select(CoursePurchase).where(
            and_(
                CoursePurchase.shared_course_id == shared_course_id,
                CoursePurchase.buyer_user_id == buyer_user_id
            )
        )
    )
    return result.scalar_one_or_none()


async def mark_course_as_saved(db: AsyncSession, purchase_id: int, buyer_user_id: str):
    """코스를 내 코스에 저장 처리"""
    result = await db.execute(
        select(CoursePurchase).where(
            and_(
                CoursePurchase.id == purchase_id,
                CoursePurchase.buyer_user_id == buyer_user_id
            )
        )
    )
    db_purchase = result.scalar_one_or_none()
    
    if not db_purchase:
        return None
    
    db_purchase.is_saved = True
    db_purchase.saved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(db_purchase)
    
    return db_purchase


# CourseBuyerReview CRUD
async def create_course_buyer_review(db: AsyncSession, review: CourseBuyerReviewCreate, buyer_user_id: str):
    """구매자 후기 작성"""
    db_review = CourseBuyerReview(
        buyer_user_id=buyer_user_id,
        **review.dict()
    )
    db.add(db_review)
    await db.flush()  # commit 대신 flush 사용
    await db.refresh(db_review)
    return db_review


async def get_course_buyer_reviews(db: AsyncSession, shared_course_id: int, skip: int = 0, limit: int = 10):
    """특정 코스의 구매자 후기 목록"""
    result = await db.execute(
        select(CourseBuyerReview)
        .options(selectinload(CourseBuyerReview.buyer_user))
        .where(
            and_(
                CourseBuyerReview.shared_course_id == shared_course_id,
                CourseBuyerReview.is_deleted == False
            )
        )
        .order_by(CourseBuyerReview.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_buyer_review_by_purchase(db: AsyncSession, purchase_id: int, buyer_user_id: str):
    """구매자의 특정 구매에 대한 후기 조회"""
    result = await db.execute(
        select(CourseBuyerReview).where(
            and_(
                CourseBuyerReview.purchase_id == purchase_id,
                CourseBuyerReview.buyer_user_id == buyer_user_id,
                CourseBuyerReview.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def update_course_buyer_review(db: AsyncSession, review_id: int, user_id: str, review_data: dict):
    """커뮤니티 코스 후기 수정"""
    result = await db.execute(
        select(CourseBuyerReview)
        .where(CourseBuyerReview.id == review_id)
        .where(CourseBuyerReview.buyer_user_id == user_id)
        .where(CourseBuyerReview.is_deleted == False)
    )
    db_review = result.scalar_one_or_none()
    
    if not db_review:
        return None
    
    for key, value in review_data.items():
        if hasattr(db_review, key):
            setattr(db_review, key, value)
    
    await db.commit()
    await db.refresh(db_review)
    return db_review


async def delete_course_buyer_review(db: AsyncSession, review_id: int, user_id: str):
    """커뮤니티 코스 후기 삭제"""
    result = await db.execute(
        select(CourseBuyerReview)
        .where(CourseBuyerReview.id == review_id)
        .where(CourseBuyerReview.buyer_user_id == user_id)
        .where(CourseBuyerReview.is_deleted == False)
    )
    db_review = result.scalar_one_or_none()
    
    if not db_review:
        return None
    
    db_review.is_deleted = True
    await db.commit()
    await db.refresh(db_review)
    return db_review


async def get_my_course_buyer_reviews(db: AsyncSession, user_id: str, skip: int = 0, limit: int = 20):
    """내가 작성한 커뮤니티 코스 후기 조회"""
    result = await db.execute(
        select(CourseBuyerReview, SharedCourse.title.label('course_title'))
        .join(SharedCourse, CourseBuyerReview.shared_course_id == SharedCourse.id, isouter=True)
        .where(CourseBuyerReview.buyer_user_id == user_id)
        .where(CourseBuyerReview.is_deleted == False)
        .offset(skip)
        .limit(limit)
        .order_by(CourseBuyerReview.created_at.desc())
    )
    
    reviews_with_course_names = []
    for row in result.fetchall():
        review = row[0]  # CourseBuyerReview 객체
        course_title = row[1]  # course_title
        
        # 동적으로 course_title 속성 추가
        review.course_title = course_title
        reviews_with_course_names.append(review)
        
    return reviews_with_course_names


async def reactivate_deleted_course_buyer_review(db: AsyncSession, user_id: str, shared_course_id: int, new_review_data):
    """삭제된 커뮤니티 코스 후기를 찾아서 내용 수정하고 재활성화"""
    try:
        # 삭제된 후기 찾기
        result = await db.execute(
            select(CourseBuyerReview)
            .where(CourseBuyerReview.buyer_user_id == user_id)
            .where(CourseBuyerReview.shared_course_id == shared_course_id)
            .where(CourseBuyerReview.is_deleted == True)
        )
        deleted_review = result.scalar_one_or_none()
        
        if not deleted_review:
            return None
        
        # 내용 업데이트하고 재활성화
        deleted_review.purchase_id = new_review_data.purchase_id
        deleted_review.rating = new_review_data.rating
        deleted_review.review_text = new_review_data.review_text
        deleted_review.tags = new_review_data.tags or []
        deleted_review.photo_urls = new_review_data.photo_urls or []
        deleted_review.is_deleted = False  # 재활성화
        
        await db.commit()
        await db.refresh(deleted_review)
        return deleted_review
        
    except Exception as e:
        await db.rollback()
        print(f"🔍 커뮤니티 코스 후기 재활성화 오류: {str(e)}")
        raise e


# 통계 조회
async def get_shared_course_stats(db: AsyncSession, shared_course_id: int):
    """공유 코스 통계 조회"""
    result = await db.execute(
        text("SELECT * FROM shared_course_stats WHERE shared_course_id = :id"),
        {"id": shared_course_id}
    )
    return result.first()


# 사용자별 조회
async def get_user_shared_courses(db: AsyncSession, user_id: str, skip: int = 0, limit: int = 20):
    """사용자가 공유한 코스들"""
    result = await db.execute(
        select(SharedCourse)
        .where(
            and_(
                SharedCourse.shared_by_user_id == user_id,
                SharedCourse.is_active == True
            )
        )
        .order_by(SharedCourse.shared_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_user_purchased_courses(db: AsyncSession, user_id: str, skip: int = 0, limit: int = 20):
    """사용자가 구매한 코스들"""
    result = await db.execute(
        select(CoursePurchase)
        .options(
            selectinload(CoursePurchase.shared_course),
            selectinload(CoursePurchase.copied_course)
        )
        .where(CoursePurchase.buyer_user_id == user_id)
        .order_by(CoursePurchase.purchased_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_shared_course_by_course_id(db: AsyncSession, course_id: int):
    """코스 ID로 공유 코스 조회 (중복 공유 확인용)"""
    result = await db.execute(
        select(SharedCourse).where(SharedCourse.course_id == course_id)
    )
    return result.scalar_one_or_none()


def _generate_shared_courses_cache_key(
    skip: int,
    limit: int,
    sort_by: str,
    category: Optional[str],
    min_rating: Optional[float]
) -> str:
    """공유 코스 목록 캐시 키 생성"""
    params = {
        'skip': skip,
        'limit': limit,
        'sort_by': sort_by,
        'category': category,
        'min_rating': min_rating
    }
    # 파라미터를 문자열로 변환하고 해시 생성  
    params_str = str(sorted(params.items()))
    hash_obj = hashlib.md5(params_str.encode())
    return f"shared_courses_list:{hash_obj.hexdigest()}"


def _convert_raw_to_dict(row):
    """DB raw 데이터를 딕셔너리로 변환 (통합 변환 함수)"""
    return {
        'id': row[0],
        'shared_course_id': row[1], 
        'title': row[2],
        'shared_by_user_id': row[3],
        'view_count': row[4],
        'purchase_count': row[5],
        'save_count': row[6],
        'price': row[7],
        'shared_at': row[8],
        'creator_rating': row[9],
        'creator_review_text': row[10],
        'buyer_review_count': row[11],
        'avg_buyer_rating': float(row[12]) if row[12] else None,
        'overall_rating': float(row[13]) if row[13] else None
    }


async def get_shared_courses_stats(db: AsyncSession, skip: int = 0, limit: int = 20, 
                                 sort_by: str = "purchase_count_desc", category: Optional[str] = None, 
                                 min_rating: Optional[float] = None):
    """공유 코스 목록 조회 (통계 뷰 활용, 캐싱 적용)"""
    from sqlalchemy import text
    
    # 캐시 키 생성
    cache_key = _generate_shared_courses_cache_key(skip, limit, sort_by, category, min_rating)
    
    # 캐시에서 조회 시도
    cached_result = redis_client.get(cache_key)
    if cached_result:
        print(f"🚀 캐시에서 커뮤니티 코스 목록 조회: {cache_key}")
        return cached_result['courses'], cached_result['total_count']
    
    print(f"💾 DB에서 커뮤니티 코스 목록 조회 (캐시 미스): {cache_key}")
    
    # 기본 쿼리 (id 필드도 함께 반환)
    query = """
        SELECT shared_course_id as id, shared_course_id, title, shared_by_user_id, 
               view_count, purchase_count, save_count, price, shared_at,
               creator_rating, creator_review_text, buyer_review_count, 
               avg_buyer_rating, overall_rating
        FROM shared_course_stats 
        WHERE 1=1
    """
    
    # 필터링 조건 추가
    params = {}
    if min_rating:
        query += " AND overall_rating >= :min_rating"
        params["min_rating"] = min_rating
    
    # 정렬 조건
    if sort_by == "latest":
        query += " ORDER BY shared_at DESC"
    elif sort_by == "popular":
        query += " ORDER BY view_count DESC"
    elif sort_by == "rating":
        query += " ORDER BY overall_rating DESC"
    elif sort_by == "purchases" or sort_by == "purchase_count_desc":
        query += " ORDER BY purchase_count DESC"
    else:
        # 기본값도 구매 많은 순으로 변경
        query += " ORDER BY purchase_count DESC"
    
    # 페이징
    query += " LIMIT :limit OFFSET :skip"
    params["limit"] = limit
    params["skip"] = skip
    
    # 데이터 조회
    result = await db.execute(text(query), params)
    raw_courses = result.fetchall()
    
    # 총 개수 조회
    count_query = "SELECT COUNT(*) as total FROM shared_course_stats WHERE 1=1"
    if min_rating:
        count_query += " AND overall_rating >= :min_rating"
    
    count_result = await db.execute(text(count_query), 
                                   {"min_rating": min_rating} if min_rating else {})
    total_count = count_result.scalar()
    
    # 통합 변환 함수로 raw 데이터를 딕셔너리로 변환
    courses = [_convert_raw_to_dict(row) for row in raw_courses]
    
    # 결과를 캐시에 저장 (무제한 저장, 20분마다 갱신)
    cache_data = {
        'courses': courses,
        'total_count': total_count
    }
    redis_client.set(cache_key, cache_data)  # 무제한 저장 (20분마다 갱신)
    print(f"💾 캐시에 커뮤니티 코스 목록 저장: {len(courses)}개 코스")
    
    return courses, total_count