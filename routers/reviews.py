from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List
import logging
from db.session import get_db
from auth.dependencies import get_current_user
from models.user import User
from models.place import Place
from models.course import Course
from models.place_review import PlaceReview
from schemas.place_review import ReviewCreateRequest, ReviewResponse
from crud.crud_place_review import place_review
from controllers.payments_controller import process_review_credit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("/")
async def create_place_review(
    review: ReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    장소 후기 작성 API + 크레딧 지급
    
    - **place_id**: 후기를 작성할 장소 ID
    - **course_id**: 해당 장소가 포함된 코스 ID
    - **rating**: 별점 (1-5)
    - **review_text**: 후기 텍스트 (선택사항)
    - **tags**: 태그 목록 (선택사항)
    - **photo_urls**: 사진 URL 목록 (선택사항)
    
    크레딧 지급 규정:
    - 평점만: 100원 (환불 불가능)
    - 평점 + 텍스트: 300원 (환불 불가능)  
    - 평점 + 텍스트 + 사진: 500원 (환불 불가능)
    """
    # 로깅용으로 user_id 미리 저장 (세션 롤백 후에도 사용 가능)
    user_id = current_user.user_id
    place_id = review.place_id
    
    try:
        # 1. 후기 작성
        created_review = await place_review.create_review(db, user_id, review)
        is_new_review = True  # 신규 작성
        
        # 2. 크레딧 지급 (실패해도 후기는 유지)
        logger.info(f"후기 작성 완료: {user_id}, 후기 ID: {created_review.id}")
        
        try:
            credit_result = await process_review_credit(
                user_id, 
                created_review.__dict__, 
                db
            )
            
            if credit_result["success"]:
                logger.info(f"크레딧 지급 성공: {user_id}, {credit_result['amount']}원")
            else:
                logger.warning(f"크레딧 지급 실패: {user_id}, {credit_result['message']}")
                
        except Exception as credit_error:
            logger.error(f"크레딧 지급 중 예외 발생: {user_id}, {str(credit_error)}")
            # 크레딧 지급 실패해도 후기는 성공으로 처리
        
        # 응답에 is_reactivated 플래그 추가
        return {
            "id": created_review.id,
            "user_id": created_review.user_id,
            "place_id": created_review.place_id,
            "course_id": created_review.course_id,
            "rating": created_review.rating,
            "review_text": created_review.review_text,
            "tags": created_review.tags,
            "photo_urls": created_review.photo_urls,
            "created_at": created_review.created_at.isoformat(),
            "updated_at": created_review.updated_at.isoformat(),
            "is_reactivated": False
        }
        
    except (ValueError, IntegrityError) as e:
        error_msg = str(e)
        # 중복 후기 오류인 경우 (ValueError 또는 IntegrityError), 삭제된 후기가 있는지 확인하고 재활성화 시도
        if ("이미 해당 장소에 후기를 작성하셨습니다" in error_msg or 
            "duplicate key value violates unique constraint" in error_msg or
            "uq_user_place_review" in error_msg):
            try:
                logger.info(f"중복 후기 오류 감지, 재활성화 시도: {user_id}, place_id: {place_id}")
                
                # 삭제된 후기 재활성화 시도
                reactivated_review = await place_review.reactivate_deleted_review(
                    db, user_id, place_id, review
                )
                
                if reactivated_review:
                    is_new_review = False  # 재활성화된 후기
                    logger.info(f"후기 재활성화 완료: {user_id}, 후기 ID: {reactivated_review.id}")
                    
                    # 재활성화된 경우 크레딧은 지급하지 않음 (이미 받았음)
                    logger.info(f"재활성화된 후기이므로 크레딧 지급하지 않음: {user_id}")
                    
                    # 응답에 is_reactivated 플래그 추가
                    return {
                        "id": reactivated_review.id,
                        "user_id": reactivated_review.user_id,
                        "place_id": reactivated_review.place_id,
                        "course_id": reactivated_review.course_id,
                        "rating": reactivated_review.rating,
                        "review_text": reactivated_review.review_text,
                        "tags": reactivated_review.tags,
                        "photo_urls": reactivated_review.photo_urls,
                        "created_at": reactivated_review.created_at.isoformat(),
                        "updated_at": reactivated_review.updated_at.isoformat(),
                        "is_reactivated": True
                    }
                else:
                    # 삭제된 후기도 없으면 원래 오류 발생
                    logger.warning(f"삭제된 후기 없음, 정말 중복: {user_id}, place_id: {place_id}")
                    raise HTTPException(status_code=400, detail="이미 해당 장소에 후기를 작성하셨습니다.")
                    
            except Exception as reactivate_error:
                logger.error(f"후기 재활성화 실패: {user_id}, {str(reactivate_error)}")
                raise HTTPException(status_code=400, detail="이미 해당 장소에 후기를 작성하셨습니다.")
        else:
            # 다른 비즈니스 로직 오류
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        # 서버 내부 오류
        raise HTTPException(status_code=500, detail=f"후기 작성 중 오류가 발생했습니다: {str(e)}")

@router.get("/my", response_model=List[ReviewResponse])
async def get_my_reviews(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    내가 작성한 후기 조회 API
    
    - **skip**: 건너뛸 항목 수 (페이지네이션)
    - **limit**: 가져올 항목 수 (최대 20)
    """
    try:
        return await place_review.get_user_reviews(db, current_user.user_id, skip, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"내 후기 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/place/{place_id}", response_model=List[ReviewResponse])
async def get_reviews_by_place(
    place_id: str,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    장소별 후기 조회 API
    
    - **place_id**: 조회할 장소 ID
    - **skip**: 건너뛸 항목 수 (페이지네이션)
    - **limit**: 가져올 항목 수 (최대 20)
    """
    try:
        return await place_review.get_place_reviews(db, place_id, skip, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"후기 조회 중 오류가 발생했습니다: {str(e)}")

@router.put("/{review_id}", response_model=ReviewResponse)
async def update_place_review(
    review_id: int,
    review_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    후기 수정 API
    
    - **review_id**: 수정할 후기 ID
    - **review_data**: 수정할 데이터
    """
    try:
        updated_review = await place_review.update_review(db, review_id, current_user.user_id, review_data)
        if not updated_review:
            raise HTTPException(status_code=404, detail="후기를 찾을 수 없거나 수정 권한이 없습니다.")
        return updated_review
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"후기 수정 중 오류가 발생했습니다: {str(e)}")

@router.delete("/{review_id}")
async def delete_place_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    후기 삭제 API
    
    - **review_id**: 삭제할 후기 ID
    """
    try:
        deleted_review = await place_review.delete_review(db, review_id, current_user.user_id)
        if not deleted_review:
            raise HTTPException(status_code=404, detail="후기를 찾을 수 없거나 삭제 권한이 없습니다.")
        return {"status": "success", "message": "후기가 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"후기 삭제 중 오류가 발생했습니다: {str(e)}")

@router.get("/check/{place_id}/{course_id}")
async def check_review_permission(
    place_id: str,
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    후기 작성 가능 여부 확인 API
    
    - **place_id**: 확인할 장소 ID
    - **course_id**: 확인할 코스 ID
    
    반환값:
    - can_write: 작성 가능 여부 (boolean)
    - reason: 작성 불가능한 이유 (string)
    """
    try:
        print(f"🔍 권한 확인 요청: place_id={place_id}, course_id={course_id}, user_id={current_user.user_id}")
        
        # place_id 존재 확인
        place_result = await db.execute(select(Place).where(Place.place_id == place_id))
        place_obj = place_result.scalar_one_or_none()
        if not place_obj:
            print(f"🚨 장소 없음: {place_id}")
            return {"can_write": False, "reason": "장소 정보를 찾을 수 없습니다."}
        
        # course_id 존재 확인  
        course_result = await db.execute(select(Course).where(Course.course_id == course_id))
        course_obj = course_result.scalar_one_or_none()
        if not course_obj:
            print(f"🚨 코스 없음: {course_id}")
            return {"can_write": False, "reason": "코스 정보를 찾을 수 없습니다."}
        
        # 중복 후기 확인
        existing_review = await db.execute(
            select(PlaceReview)
            .where(PlaceReview.user_id == current_user.user_id)
            .where(PlaceReview.place_id == place_id)
            .where(PlaceReview.is_deleted == False)
        )
        existing = existing_review.scalar_one_or_none()
        if existing:
            print(f"🚨 중복 후기 발견: review_id={existing.id}")
            return {"can_write": False, "reason": "이미 해당 장소에 후기를 작성하셨습니다."}
        
        print(f"✅ 후기 작성 가능: place_id={place_id}")
        return {"can_write": True, "reason": ""}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"권한 확인 중 오류가 발생했습니다: {str(e)}")