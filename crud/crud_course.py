from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.course import Course
from models.place_category import PlaceCategory
from schemas.course import CourseCreate

async def get_or_create_category(db: AsyncSession, category_name: str) -> int:
    """카테고리가 있으면 반환, 없으면 생성 후 반환"""
    try:
        # 기존 카테고리 찾기
        result = await db.execute(
            select(PlaceCategory).where(PlaceCategory.category_name == category_name)
        )
        existing_category = result.scalar_one_or_none()
        
        if existing_category:
            return existing_category.category_id
        
        # 새 카테고리 생성
        # 기존 최대 ID 찾기
        max_id_result = await db.execute(
            select(PlaceCategory.category_id).order_by(PlaceCategory.category_id.desc()).limit(1)
        )
        max_id = max_id_result.scalar_one_or_none()
        new_id = (max_id or 0) + 1
        
        new_category = PlaceCategory(
            category_id=new_id,
            category_name=category_name
        )
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        
        return new_category.category_id
        
    except Exception as e:
        print(f"카테고리 생성/조회 실패: {e}")
        await db.rollback()
        return 1  # 기본 카테고리 ID

async def create_course(db: AsyncSession, course_in: CourseCreate):
    course_data = course_in.model_dump()
    # places는 별도 처리, user_request, preferences만 제거
    places_data = course_data.pop('places', [])
    course_data.pop('user_request', None) 
    course_data.pop('preferences', None)
    
    # 코스 기본 정보 저장
    db_course = Course(**course_data)
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    
    # places 정보 저장 (place_id 기반으로 변경)
    if places_data:
        try:
            from models.place import Place
            from models.course_place import CoursePlace
            
            for place_data in places_data:
                try:
                    # place_id 받아오기 (AI가 기존 장소의 place_id를 보냄)
                    place_id = place_data.get("place_id")
                    
                    if not place_id:
                        print(f"place_id 없음, 건너뛰기: {place_data}")
                        continue
                    
                    # 기존 places 테이블에서 place_id로 장소 찾기
                    result = await db.execute(
                        select(Place).where(Place.place_id == place_id)
                    )
                    existing_place = result.scalar_one_or_none()
                    
                    if not existing_place:
                        print(f"장소를 찾을 수 없음: {place_id}")
                        continue
                    
                    # course_places 테이블에 연결 정보만 저장
                    db_course_place = CoursePlace(
                        course_id=db_course.course_id,
                        place_id=existing_place.place_id,
                        sequence_order=place_data.get("sequence", 1),
                        estimated_duration=place_data.get("estimated_duration"),
                        estimated_cost=place_data.get("estimated_cost")
                    )
                    db.add(db_course_place)
                    await db.commit()
                    
                    print(f"✅ 장소 연결 성공: {existing_place.name} ({place_id})")
                    
                except Exception as place_error:
                    print(f"장소 연결 실패: {place_error}")
                    await db.rollback()
                    continue
                    
        except Exception as places_error:
            print(f"Places 연결 전체 실패: {places_error}")
            # places 연결 실패해도 코스는 저장되도록 함
            pass
    
    return db_course

async def get_course(db: AsyncSession, course_id: int):
    result = await db.execute(select(Course).where(Course.course_id == course_id))
    return result.scalar_one_or_none()

async def get_all_courses(db: AsyncSession):
    result = await db.execute(select(Course))
    return result.scalars().all()

async def get_all_courses_for_user(db: AsyncSession, user_id: str):
    # 자신의 코스 조회
    my_courses_result = await db.execute(select(Course).where(Course.user_id == user_id))
    my_courses = my_courses_result.scalars().all()
    
    # 커플 관계 확인하여 공유된 코스도 조회
    try:
        from models.couple import Couple
        
        # 커플 관계 찾기 (user1_id 또는 user2_id로 등록된 경우)
        couple_result = await db.execute(
            select(Couple).where(
                (Couple.user1_id == user_id) | (Couple.user2_id == user_id)
            )
        )
        couple = couple_result.scalar_one_or_none()
        
        if couple:
            # 상대방 user_id 찾기
            partner_id = couple.user2_id if couple.user1_id == user_id else couple.user1_id
            
            # 상대방의 공유된 코스 조회
            shared_courses_result = await db.execute(
                select(Course).where(
                    (Course.user_id == partner_id) & 
                    (Course.is_shared_with_couple == True)
                )
            )
            shared_courses = shared_courses_result.scalars().all()
            
            # 내 코스 + 공유받은 코스 합치기
            all_courses = list(my_courses) + list(shared_courses)
            return all_courses
        
    except Exception as e:
        print(f"커플 코스 조회 실패: {e}")
    
    # 커플 관계가 없거나 오류 시 자신의 코스만 반환
    return my_courses

async def get_course_detail(db: AsyncSession, course_id: int, user_id: str):
    # 먼저 자신의 코스인지 확인
    result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = result.scalar_one_or_none()
    
    # 자신의 코스가 아니라면 커플의 공유된 코스인지 확인
    if not course:
        try:
            from models.couple import Couple
            
            # 커플 관계 찾기
            couple_result = await db.execute(
                select(Couple).where(
                    (Couple.user1_id == user_id) | (Couple.user2_id == user_id)
                )
            )
            couple = couple_result.scalar_one_or_none()
            
            if couple:
                # 상대방 user_id 찾기
                partner_id = couple.user2_id if couple.user1_id == user_id else couple.user1_id
                
                # 상대방의 공유된 코스인지 확인
                shared_result = await db.execute(
                    select(Course).where(
                        (Course.course_id == course_id) & 
                        (Course.user_id == partner_id) & 
                        (Course.is_shared_with_couple == True)
                    )
                )
                course = shared_result.scalar_one_or_none()
                
        except Exception as e:
            print(f"공유 코스 조회 실패: {e}")
    
    if not course:
        return None
    
    # course_places와 places 정보 함께 조회
    try:
        from models.course_place import CoursePlace
        from models.place import Place
        
        # course_places, places, place_category를 조인하여 상세 장소 정보 조회
        from models.place_category import PlaceCategory
        
        places_result = await db.execute(
            select(CoursePlace, Place, PlaceCategory.category_name)
            .join(Place, CoursePlace.place_id == Place.place_id)
            .outerjoin(PlaceCategory, Place.category_id == PlaceCategory.category_id)
            .where(CoursePlace.course_id == course_id)
            .order_by(CoursePlace.sequence_order)
        )
        
        places_data = []
        for course_place, place, category_name in places_result:
            places_data.append({
                "sequence": course_place.sequence_order,
                "place_id": place.place_id,
                "name": place.name,
                "address": place.address,
                "category": category_name or "기타",
                "coordinates": {
                    "latitude": place.latitude,
                    "longitude": place.longitude
                },
                "description": place.description,
                "summary": place.summary,
                "phone": place.phone,
                "kakao_url": place.kakao_url,
                "estimated_duration": course_place.estimated_duration,
                "estimated_cost": course_place.estimated_cost
            })
        
        # 코스 정보에 장소 데이터 추가
        course_dict = {
            "course_id": course.course_id,
            "title": course.title,
            "description": course.description,
            "user_id": course.user_id,
            "total_duration": course.total_duration,
            "estimated_cost": course.estimated_cost,
            "is_shared_with_couple": course.is_shared_with_couple,
            "created_at": course.created_at,
            "places": places_data
        }
        
        return course_dict
        
    except Exception as e:
        print(f"장소 정보 조회 실패: {e}")
        # 에러 발생 시에도 코스 기본 정보는 반환
        return {
            "course_id": course.course_id,
            "title": course.title,
            "description": course.description,
            "user_id": course.user_id,
            "total_duration": course.total_duration,
            "estimated_cost": course.estimated_cost,
            "is_shared_with_couple": course.is_shared_with_couple,
            "created_at": course.created_at,
            "places": []
        }

async def get_course_with_comments(db: AsyncSession, course_id: int, user_id: str):
    # 먼저 자신의 코스인지 확인
    course_result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = course_result.scalar_one_or_none()
    
    # 자신의 코스가 아니라면 커플의 공유된 코스인지 확인
    if not course:
        try:
            from models.couple import Couple
            
            # 커플 관계 찾기
            couple_result = await db.execute(
                select(Couple).where(
                    (Couple.user1_id == user_id) | (Couple.user2_id == user_id)
                )
            )
            couple = couple_result.scalar_one_or_none()
            
            if couple:
                # 상대방 user_id 찾기
                partner_id = couple.user2_id if couple.user1_id == user_id else couple.user1_id
                
                # 상대방의 공유된 코스인지 확인
                shared_result = await db.execute(
                    select(Course).where(
                        (Course.course_id == course_id) & 
                        (Course.user_id == partner_id) & 
                        (Course.is_shared_with_couple == True)
                    )
                )
                course = shared_result.scalar_one_or_none()
                
        except Exception as e:
            print(f"공유 코스 조회 실패: {e}")
    
    if not course:
        return None
    
    # course_places와 places 정보 함께 조회
    try:
        from models.course_place import CoursePlace
        from models.place import Place
        
        # course_places, places, place_category를 조인하여 상세 장소 정보 조회
        from models.place_category import PlaceCategory
        
        result = await db.execute(
            select(CoursePlace, Place, PlaceCategory.category_name)
            .join(Place, CoursePlace.place_id == Place.place_id)
            .outerjoin(PlaceCategory, Place.category_id == PlaceCategory.category_id)
            .where(CoursePlace.course_id == course.course_id)
            .order_by(CoursePlace.sequence_order)
        )
        
        places_data = []
        for course_place, place, category_name in result:
            places_data.append({
                "sequence": course_place.sequence_order,
                "place_id": place.place_id,
                "name": place.name,
                "address": place.address,
                "category": category_name or "기타",
                "coordinates": {
                    "latitude": place.latitude,
                    "longitude": place.longitude
                },
                "description": place.description,
                "summary": place.summary,
                "phone": place.phone,
                "kakao_url": place.kakao_url,
                "estimated_duration": course_place.estimated_duration,
                "estimated_cost": course_place.estimated_cost
            })
        
        # 댓글 조회
        comments_data = []
        try:
            from models.comment import Comment
            
            comments_result = await db.execute(
                select(Comment)
                .where(Comment.course_id == course.course_id)
                .order_by(Comment.timestamp.asc())
            )
            comments = comments_result.scalars().all()
            
            for comment in comments:
                comments_data.append({
                    "comment_id": comment.comment_id,
                    "course_id": comment.course_id,
                    "user_id": comment.user_id,
                    "nickname": comment.nickname,
                    "comment": comment.comment,
                    "timestamp": comment.timestamp.isoformat() if comment.timestamp else None
                })
                
        except Exception as comment_error:
            print(f"댓글 조회 실패: {comment_error}")
        
        return {
            "course": {
                "course_id": course.course_id,
                "title": course.title,
                "description": course.description,
                "user_id": course.user_id,
                "is_shared_with_couple": course.is_shared_with_couple,
                "created_at": course.created_at,
                "places": places_data
            },
            "comments": comments_data
        }
        
    except Exception as e:
        print(f"장소 정보 조회 실패: {e}")
        # 에러 발생 시에도 코스 기본 정보와 댓글은 조회 시도
        comments_data = []
        try:
            from models.comment import Comment
            
            comments_result = await db.execute(
                select(Comment)
                .where(Comment.course_id == course.course_id)
                .order_by(Comment.timestamp.asc())
            )
            comments = comments_result.scalars().all()
            
            for comment in comments:
                comments_data.append({
                    "comment_id": comment.comment_id,
                    "course_id": comment.course_id,
                    "user_id": comment.user_id,
                    "nickname": comment.nickname,
                    "comment": comment.comment,
                    "timestamp": comment.timestamp.isoformat() if comment.timestamp else None
                })
                
        except Exception as comment_error:
            print(f"댓글 조회 실패: {comment_error}")
        
        return {
            "course": {
                "course_id": course.course_id,
                "title": course.title,
                "description": course.description,
                "user_id": course.user_id,
                "is_shared_with_couple": course.is_shared_with_couple,
                "created_at": course.created_at,
                "places": []
            },
            "comments": comments_data
        }

async def share_course(db: AsyncSession, course_id: int, user_id: str):
    # ORM 객체를 직접 조회
    result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = result.scalar_one_or_none()
    
    if not course:
        return False
    
    course.is_shared_with_couple = not course.is_shared_with_couple
    await db.commit()
    await db.refresh(course)
    return True

async def delete_course(db: AsyncSession, course_id: int, user_id: str):
    # ORM 객체를 직접 조회 (dict가 아닌)
    result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = result.scalar_one_or_none()
    
    if not course:
        return False
    
    await db.delete(course)
    await db.commit()
    return True

async def update_course_description(db: AsyncSession, course_id: int, user_id: str, description: str):
    # ORM 객체를 직접 조회
    result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = result.scalar_one_or_none()
    
    if not course:
        return False
    
    course.description = description
    await db.commit()
    await db.refresh(course)
    return True

async def update_course_title(db: AsyncSession, course_id: int, user_id: str, title: str):
    # ORM 객체를 직접 조회
    result = await db.execute(select(Course).where(Course.course_id == course_id, Course.user_id == user_id))
    course = result.scalar_one_or_none()
    
    if not course:
        return False
    
    course.title = title
    await db.commit()
    await db.refresh(course)
    return True