from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession  
from sqlalchemy import select, and_
import models.place
from typing import List, Optional

from db.session import get_db
from auth.dependencies import get_current_user, get_current_user_optional
from models.user import User
from models.shared_course import CoursePurchase
from schemas.shared_course_schema import (
    SharedCourseCreate, SharedCourseUpdate, SharedCourseResponse,
    SharedCourseReviewForCreate, SharedCourseReviewCreate, SharedCourseReviewResponse,
    CoursePurchaseCreate, CoursePurchaseResponse,
    CourseBuyerReviewCreate, CourseBuyerReviewResponse,
    SharedCourseListResponse, SharedCourseStatsResponse, SharedCourseDetailResponse, CreatorReviewResponse,
    PurchaseStatusResponse, CourseInfo, CoursePlace
)
from crud import crud_shared_course, crud_course
from controllers.payments_controller import (
    process_shared_course_credit, 
    process_course_purchase_payment,
    process_creator_save_reward,
    process_buyer_review_credit
)

router = APIRouter(prefix="/shared_courses", tags=["shared_courses"])


@router.post("/create", response_model=SharedCourseResponse)
async def create_shared_course(
    shared_course_data: SharedCourseCreate,
    review_data: SharedCourseReviewForCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """코스 공유 + 후기 작성 + 300원 지급"""
    
    # 1. 코스 소유권 확인
    course = await crud_course.get_course(db, shared_course_data.course_id)
    if not course or course.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 코스에 대한 권한이 없습니다."
        )
    
    # 2. 중복 공유 확인
    existing_shared = await crud_shared_course.get_shared_course_by_course_id(db, shared_course_data.course_id)
    if existing_shared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 공유된 코스입니다."
        )
    
    try:
        # 3. 공유 코스 생성
        shared_course = await crud_shared_course.create_shared_course(
            db, shared_course_data, current_user.user_id
        )
        
        # 4. 공유자 후기 작성
        # SharedCourseReviewForCreate를 SharedCourseReviewCreate로 변환
        review_create_data = SharedCourseReviewCreate(
            shared_course_id=shared_course.id,
            rating=review_data.rating,
            review_text=review_data.review_text,
            tags=review_data.tags,
            photo_urls=review_data.photo_urls
        )
        await crud_shared_course.create_shared_course_review(
            db, review_create_data, current_user.user_id
        )
        
        # 5. 300원 크레딧 지급 (환불 불가능)
        credit_result = await process_shared_course_credit(current_user.user_id, shared_course.id, db)
        
        if not credit_result["success"]:
            raise Exception(f"크레딧 지급 실패: {credit_result['message']}")
        
        # 모든 작업이 성공하면 한 번에 커밋
        await db.commit()
        await db.refresh(shared_course)
        return shared_course
        
    except Exception as e:
        await db.rollback()  # 실패 시 모든 변경사항 롤백
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"공유 코스 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/", response_model=SharedCourseListResponse)
async def get_shared_courses(
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "latest",
    category: Optional[str] = None,
    min_rating: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    """공유 코스 목록 조회"""
    # 통계 뷰에서 목록 조회 (평점 포함)
    courses, total_count = await crud_shared_course.get_shared_courses_stats(
        db, skip, limit, sort_by, category, min_rating
    )
    
    return SharedCourseListResponse(
        courses=courses,
        total_count=total_count,
        page=(skip // limit) + 1,
        limit=limit
    )


async def update_view_count_async(shared_course_id: int, db_session):
    """조회수 비동기 업데이트 (백그라운드 처리)"""
    try:
        async with db_session() as db:
            from sqlalchemy import update
            from models.shared_course import SharedCourse
            await db.execute(
                update(SharedCourse)
                .where(SharedCourse.id == shared_course_id)
                .values(view_count=SharedCourse.view_count + 1)
            )
            await db.commit()
    except Exception as e:
        print(f"조회수 업데이트 실패: {e}")


@router.get("/{shared_course_id}", response_model=SharedCourseDetailResponse)
async def get_shared_course_detail(
    shared_course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """공유 코스 상세 조회"""
    import asyncio
    from db.session import SessionLocal
    
    # 1. 데이터 먼저 조회 (조회수 업데이트 없이)
    shared_course = await crud_shared_course.get_shared_course(db, shared_course_id)
    if not shared_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 코스를 찾을 수 없습니다."
        )
    
    # 2. 통계 데이터 조회
    stats = await crud_shared_course.get_shared_course_stats(db, shared_course_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 코스 통계를 찾을 수 없습니다."
        )
    
    # 3. 구매 상태 확인 (로그인한 경우만)
    is_purchased = False
    can_purchase = True
    is_saved = False
    
    print(f"DEBUG: current_user = {current_user}")
    if current_user:
        print(f"DEBUG: current_user.user_id = {current_user.user_id}")
        # 자신의 코스인지 확인
        if shared_course.shared_by_user_id == current_user.user_id:
            can_purchase = False
            
        # 구매 여부 확인 - 구매 검증과 동일한 함수 사용
        purchase = await crud_shared_course.get_course_purchase(db, shared_course_id, current_user.user_id)
        print(f"DEBUG: purchase = {purchase}")
        
        if purchase:
            is_purchased = True
            can_purchase = False
            is_saved = purchase.is_saved
            print(f"DEBUG: is_purchased = {is_purchased}, can_purchase = {can_purchase}")
    else:
        print("DEBUG: current_user is None - 토큰 인증 실패")
    
    purchase_status = PurchaseStatusResponse(
        is_purchased=is_purchased,
        can_purchase=can_purchase,
        is_saved=is_saved
    )
    
    # 4. 코스 정보 조회 (구매한 경우 또는 자신의 코스인 경우)
    course_info = None
    is_own_course = current_user and shared_course.shared_by_user_id == current_user.user_id
    
    if (is_purchased or is_own_course) and shared_course.course:
        # 간단하게 places 정보 생성 (직접 DB 조회)
        places = []
        if hasattr(shared_course.course, 'places') and shared_course.course.places:
            for place in shared_course.course.places:
                # Place 정보를 직접 DB에서 조회
                place_result = await db.execute(
                    select(models.place.Place).where(models.place.Place.place_id == place.place_id)
                )
                place_info = place_result.scalar_one_or_none()
                
                coordinates = None
                if place_info and place_info.latitude and place_info.longitude:
                    coordinates = {
                        "latitude": place_info.latitude,
                        "longitude": place_info.longitude
                    }
                
                places.append(CoursePlace(
                    sequence=place.sequence_order,
                    name=place_info.name if place_info else f"장소 {place.sequence_order}",
                    address=place_info.address if place_info else "주소 정보 없음",
                    category="일반",  # 카테고리는 일단 간단하게
                    phone=place_info.phone if place_info else "",
                    estimated_duration=place.estimated_duration or 60,
                    estimated_cost=place.estimated_cost or 0,
                    coordinates=coordinates,
                    summary=place_info.summary if place_info else None,
                    description=place_info.description if place_info else None,
                    kakao_url=place_info.kakao_url if place_info else None
                ))
        
        course_info = CourseInfo(
            course_id=shared_course.course.course_id,
            title=shared_course.course.title,
            description=shared_course.course.description,
            places=places
        )
    
    # 5. 조회수 증가는 백그라운드에서 비동기 처리 (사용자는 기다리지 않음)
    asyncio.create_task(update_view_count_async(shared_course_id, SessionLocal))
    
    # 6. 창작자 후기 생성 (첫 번째 리뷰 사용)
    creator_review = None
    if shared_course.reviews and len(shared_course.reviews) > 0:
        review = shared_course.reviews[0]
        creator_review = CreatorReviewResponse(
            rating=review.rating,
            review_text=review.review_text,
            tags=review.tags or [],
            created_at=review.created_at
        )
    
    # 7. 결합된 응답 생성 (즉시 반환)
    return SharedCourseDetailResponse(
        id=shared_course.id,
        course_id=shared_course.course_id,
        shared_by_user_id=shared_course.shared_by_user_id,
        title=shared_course.title,
        description=shared_course.description,
        preview_image_url=shared_course.preview_image_url,
        price=shared_course.price,
        reward_per_save=shared_course.reward_per_save,
        view_count=shared_course.view_count + 1,  # 화면에는 +1 표시 (실제 DB는 백그라운드 업데이트)
        purchase_count=shared_course.purchase_count,
        save_count=shared_course.save_count,
        is_active=shared_course.is_active,
        shared_at=shared_course.shared_at,
        updated_at=shared_course.updated_at,
        
        # 통계 데이터
        overall_rating=stats.overall_rating,
        creator_rating=stats.creator_rating,
        avg_buyer_rating=stats.avg_buyer_rating,
        buyer_review_count=stats.buyer_review_count,
        
        # 창작자 후기
        creator_review=creator_review,
        
        # 구매자 후기들
        buyer_reviews=shared_course.buyer_reviews or [],
        
        # 구매 상태
        purchase_status=purchase_status,
        
        # 코스 정보 (구매한 경우만)
        course=course_info
    )


@router.post("/{shared_course_id}/purchase", response_model=CoursePurchaseResponse)
async def purchase_shared_course(
    shared_course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """코스 구매 (300원 차감)"""
    
    # 1. 공유 코스 존재 확인
    shared_course = await crud_shared_course.get_shared_course(db, shared_course_id)
    if not shared_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 코스를 찾을 수 없습니다."
        )
    
    # 2. 자신의 코스 구매 방지
    if shared_course.shared_by_user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자신이 공유한 코스는 구매할 수 없습니다."
        )
    
    # 3. 중복 구매 확인
    existing_purchase = await crud_shared_course.get_course_purchase(
        db, shared_course_id, current_user.user_id
    )
    if existing_purchase:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 구매한 코스입니다."
        )
    
    try:
        # 4. 결제 처리 (300원 차감)
        await process_course_purchase_payment(current_user.user_id, shared_course.price, db)
        
        # 5. 코스 복사 생성
        copied_course = await crud_course.copy_course_for_purchase(
            db, shared_course.course_id, current_user.user_id
        )
        
        # 6. 구매 기록 생성
        purchase = await crud_shared_course.create_course_purchase(
            db, shared_course_id, current_user.user_id, copied_course.course_id
        )
        
        # 7. 명시적 커밋 (중요!)
        await db.commit()
        await db.refresh(purchase)
        
        return purchase
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"코스 구매 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/{shared_course_id}/save")
async def save_purchased_course(
    shared_course_id: int,
    purchase_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 코스에 저장 + 창작자 100원 지급"""
    
    # 1. 구매 기록 확인
    purchase = await crud_shared_course.get_course_purchase(db, shared_course_id, current_user.user_id)
    if not purchase or purchase.id != purchase_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구매 기록을 찾을 수 없습니다."
        )
    
    if purchase.is_saved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 저장된 코스입니다."
        )
    
    try:
        # 2. 저장 처리
        updated_purchase = await crud_shared_course.mark_course_as_saved(
            db, purchase_id, current_user.user_id
        )
        
        # 3. 창작자에게 100원 지급
        shared_course = await crud_shared_course.get_shared_course(db, shared_course_id)
        await process_creator_save_reward(shared_course.shared_by_user_id, shared_course_id, db)
        
        return {"message": "코스가 저장되었습니다. 창작자에게 100원이 지급되었습니다."}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"코스 저장 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{shared_course_id}")
async def delete_shared_course(
    shared_course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """공유 삭제 (소프트 삭제)"""
    
    deleted_course = await crud_shared_course.delete_shared_course(
        db, shared_course_id, current_user.user_id
    )
    
    if not deleted_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 코스를 찾을 수 없거나 삭제 권한이 없습니다."
        )
    
    return {"message": "공유 코스가 삭제되었습니다."}


# 개인 관리 API들
@router.get("/my/created", response_model=List[SharedCourseResponse])
async def get_my_shared_courses(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내가 공유한 코스들"""
    courses = await crud_shared_course.get_user_shared_courses(
        db, current_user.user_id, skip, limit
    )
    return courses


@router.get("/my/purchased", response_model=List[CoursePurchaseResponse])
async def get_my_purchased_courses(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내가 구매한 코스들"""
    purchases = await crud_shared_course.get_user_purchased_courses(
        db, current_user.user_id, skip, limit
    )
    return purchases


@router.get("/my/earnings")
async def get_my_earnings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 코스 수익 현황"""
    # 추후 구현 예정
    return {"message": "수익 현황 조회 기능은 추후 구현 예정입니다."}


# 구매자 후기 API들
@router.post("/reviews/buyer", response_model=CourseBuyerReviewResponse)
async def create_buyer_review(
    review_data: CourseBuyerReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구매자 후기 작성 + 300원 지급"""
    
    # 1. 구매 확인
    purchase = await crud_shared_course.get_course_purchase(
        db, review_data.shared_course_id, current_user.user_id
    )
    if not purchase or purchase.id != review_data.purchase_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="구매한 코스가 아닙니다."
        )
    
    # 2. 중복 후기 확인
    existing_review = await crud_shared_course.get_buyer_review_by_purchase(
        db, review_data.purchase_id, current_user.user_id
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 후기를 작성하셨습니다."
        )
    
    try:
        # 3. 후기 작성
        review = await crud_shared_course.create_course_buyer_review(
            db, review_data, current_user.user_id
        )
        
        # 4. 300원 크레딧 지급 (환불 불가능)
        credit_result = await process_buyer_review_credit(current_user.user_id, review.id, db)
        
        if not credit_result["success"]:
            raise Exception(f"크레딧 지급 실패: {credit_result['message']}")
        
        # 5. 최종 커밋 후 refresh
        await db.commit()
        await db.refresh(review)
        
        return review
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"후기 작성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/reviews/buyer/course/{shared_course_id}", response_model=List[CourseBuyerReviewResponse])
async def get_course_buyer_reviews(
    shared_course_id: int,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """특정 코스의 구매자 후기들"""
    reviews = await crud_shared_course.get_course_buyer_reviews(
        db, shared_course_id, skip, limit
    )
    return reviews