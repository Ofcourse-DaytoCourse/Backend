from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from db.session import get_db
from schemas.course import CourseCreate, CourseRead
from crud import crud_course

router = APIRouter()

# 코스 추천 API (AI 추천)
@router.post("/courses/recommendation", summary="AI 코스 추천")
async def recommend_course(course_in: CourseCreate, db: AsyncSession = Depends(get_db)):
    try:
        # 간단한 AI 추천 로직 (실제로는 더 복잡한 AI 서비스 호출)
        user_request = course_in.user_request or "맞춤형 데이트 코스"
        
        # 더미 추천 데이터 생성
        ai_response = f"""🌟 **{user_request}**에 대한 맞춤형 데이트 코스를 추천해드릴게요!

**추천 코스:**
1. **카페에서 브런치** (2시간)
   📍 강남구 신사동 - 분위기 좋은 루프탑 카페
   💰 2-3만원

2. **공원 산책** (1시간)
   📍 한강공원 - 자연을 만끽하며 여유로운 시간
   💰 무료

3. **영화 관람** (2시간)
   📍 CGV 강남점 - 최신 영화 관람
   💰 3-4만원

4. **맛집에서 저녁식사** (1.5시간)
   📍 이태원 맛집 - 로맨틱한 분위기의 레스토랑
   💰 8-12만원

**총 소요시간:** 약 6.5시간
**예상 비용:** 13-19만원
**추천 포인트:** 다양한 활동으로 구성된 알찬 데이트 코스"""

        return {
            "status": "success",
            "course_content": ai_response,
            "title": f"{user_request} 추천 코스",
            "description": ai_response,
            "places": [
                {"name": "루프탑 카페", "category_name": "카페", "address": "강남구 신사동"},
                {"name": "한강공원", "category_name": "공원", "address": "한강공원"},
                {"name": "CGV 강남점", "category_name": "영화관", "address": "강남구"},
                {"name": "이태원 레스토랑", "category_name": "레스토랑", "address": "이태원"}
            ],
            "total_duration": 390,  # 6.5시간
            "estimated_cost": 160000  # 16만원
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"코스 추천 실패: {str(e)}")

# 코스 저장 API
@router.post("/courses/save", summary="코스 저장")
async def save_course_endpoint(course_in: CourseCreate, db: AsyncSession = Depends(get_db)):
    try:
        # 실제 DB에 코스 저장
        course = await crud_course.create_course(db, course_in)
        if not course:
            raise HTTPException(status_code=400, detail="코스를 저장할 수 없습니다.")
        return {"status": "success", "course_id": course.course_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"코스 저장 실패: {str(e)}")

# ✅ 3-2. 추천 코스 내역 조회 (GET /courses/list)
@router.get("/courses/list", summary="추천 코스 내역 조회")
async def list_courses(user_id: str = Query(..., description="사용자 ID"), db: AsyncSession = Depends(get_db)):
    courses = await crud_course.get_all_courses_for_user(db, user_id=user_id)
    # 결과를 직렬화 가능한 형태로 변환
    course_list = []
    for course in courses:
        # 자신의 코스인지 확인
        is_my_course = course.user_id == user_id
        
        course_list.append({
            "course_id": course.course_id,
            "title": course.title,
            "description": course.description,
            "user_id": course.user_id,
            "is_shared_with_couple": course.is_shared_with_couple,
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "places": [],
            "creator_nickname": "나" if is_my_course else "상대방",
            "is_my_course": is_my_course,
            "is_shared_course": not is_my_course  # 공유받은 코스인지 표시
        })
    return {"courses": course_list}

# ✅ 3-3. 코스 상세 조회 (나만 보는) (GET /courses/detail)
@router.get("/courses/detail", summary="코스 상세 조회")
async def read_course_detail(
    user_id: str = Query(..., description="사용자 ID"),
    course_id: int = Query(..., description="코스 ID"),
    db: AsyncSession = Depends(get_db),
):
    course = await crud_course.get_course_detail(db, user_id=user_id, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
    return {"course": course}

# ✅ 3-4. 코스 상세 + 댓글 통합 조회 (연인과 공유) (GET /courses/comments)
@router.get("/courses/comments", summary="코스 + 댓글 통합 조회")
async def course_with_comments(
    user_id: str = Query(..., description="사용자 ID"),
    course_id: int = Query(..., description="코스 ID"),
    db: AsyncSession = Depends(get_db),
):
    course_with_comments = await crud_course.get_course_with_comments(db, user_id=user_id, course_id=course_id)
    if not course_with_comments:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
    return course_with_comments

# ✅ 3-5. 코스 삭제 (DELETE /courses/delete)
@router.delete("/courses/delete", summary="코스 삭제")
async def delete_course_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
):
    user_id = request_data.get("user_id")
    course_id = request_data.get("course_id")
    
    if not user_id or not course_id:
        raise HTTPException(status_code=400, detail="user_id와 course_id가 필요합니다.")
    
    deleted = await crud_course.delete_course(db, user_id=user_id, course_id=course_id)
    if not deleted:
        raise HTTPException(status_code=403, detail="삭제할 권한이 없거나 코스를 찾을 수 없습니다.")
    return {"status": "course_deleted", "course_id": course_id}

# ✅ 3-6. 코스 공유 (POST /courses/share)
@router.post("/courses/share", summary="코스 공유")
async def share_course_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
):
    course_id = request_data.get("course_id")
    user_id = request_data.get("user_id")
    
    if not course_id or not user_id:
        raise HTTPException(status_code=400, detail="course_id와 user_id가 필요합니다.")
    
    success = await crud_course.share_course(db, course_id=course_id, user_id=user_id)
    if not success:
        return {"status": "error", "message": "코스 공유 링크를 생성할 수 없습니다. 다시 시도해주세요."}
    return {"status": "success"}

# ✅ 3-7. 코스 설명 수정 (PUT /courses/description)
@router.put("/courses/description", summary="코스 설명 수정")
async def update_description_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
):
    course_id = request_data.get("course_id")
    description = request_data.get("description")
    user_id = request_data.get("user_id")
    
    if not course_id or not user_id or description is None:
        raise HTTPException(status_code=400, detail="course_id, user_id, description이 필요합니다.")
    
    updated = await crud_course.update_course_description(db, course_id, user_id, description)
    if not updated:
        raise HTTPException(status_code=403, detail="설명 수정 권한이 없거나 코스를 찾을 수 없습니다.")
    return {"status": "description_updated", "course_id": course_id, "description": description}

# ✅ 3-8. 코스 제목 수정 (PUT /courses/title)
@router.put("/courses/title", summary="코스 제목 수정")
async def update_title_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
):
    course_id = request_data.get("course_id")
    title = request_data.get("title")
    user_id = request_data.get("user_id")
    
    if not course_id or not user_id or not title:
        raise HTTPException(status_code=400, detail="course_id, user_id, title이 필요합니다.")
    
    updated = await crud_course.update_course_title(db, course_id, user_id, title)
    if not updated:
        raise HTTPException(status_code=403, detail="제목 수정 권한이 없거나 코스를 찾을 수 없습니다.")
    return {"status": "title_updated", "course_id": course_id, "title": title}
