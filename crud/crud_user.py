from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy import delete, update as sqlalchemy_update, or_
from models.user import User
from models.user_oauth import UserOAuth
from models.couple import Couple
from models.couple_request import CoupleRequest
from schemas.user import UserCreate, UserDeleteRequest
from models.chat_session import ChatSession
from models.course import Course
from models.comment import Comment
import uuid



def generate_temp_nickname(kakao_name: str) -> str:
    unique_id = str(uuid.uuid4())[:8]
    return f"{kakao_name}_{unique_id}"

# 이메일로 유저 조회
async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# 닉네임 중복 확인 (탈퇴 유저 포함)
async def get_user_by_nickname(db: AsyncSession, nickname: str):
    result = await db.execute(
        select(User).where(User.nickname == nickname)
    )
    return result.scalar_one_or_none()


# 새로운 범용 함수 추가
async def get_user_by_provider_id(db: AsyncSession, provider_type: str, provider_user_id: str):
    result = await db.execute(
        select(UserOAuth).where(
            UserOAuth.provider_type == provider_type,
            UserOAuth.provider_user_id == provider_user_id
        )
    )
    oauth_user = result.scalar_one_or_none()
    if oauth_user:
        user_result = await db.execute(select(User).where(User.user_id == oauth_user.user_id))
        return user_result.scalar_one_or_none()
    return None

# 기존 함수는 호환성을 위해 유지하되 새 함수 사용
async def get_user_by_kakao_id(db: AsyncSession, kakao_id: str):
    return await get_user_by_provider_id(db, "kakao", kakao_id)


# 유저 생성
async def create_user(db: AsyncSession, user_in: UserCreate):
    db_user = User(**user_in.model_dump())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# ✅ OAuth 유저 생성 (자동 복구 활성화됨)
async def create_user_with_oauth(
    db: AsyncSession,
    provider_type: str,
    provider_user_id: str,
    nickname: str,
    email: str
):
    result = await db.execute(
        select(UserOAuth).where(
            UserOAuth.provider_type == provider_type,
            UserOAuth.provider_user_id == provider_user_id
        )
    )
    oauth_user = result.scalar_one_or_none()

    if oauth_user:
        user_result = await db.execute(select(User).where(User.user_id == oauth_user.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            if user.user_status == "inactive":
                # 탈퇴한 유저 즉시 DROP & RECREATE
                result = await recreate_user_for_deactivated(
                    db=db,
                    provider_type=provider_type,
                    provider_user_id=provider_user_id, 
                    nickname=f"복구유저_{user.user_id[:8]}",
                    email=email or ""
                )
                return result

            return {
                "status": "success",
                "is_new_user": False,
                "user": {
                    "user_id": user.user_id,
                    "nickname": user.nickname,
                    "email": user.email or ""
                }
            }

    # 새 유저 생성
    db_user = User(
        email=email,
        nickname=generate_temp_nickname(nickname),
        user_status="active"
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    db_oauth = UserOAuth(
        provider_type=provider_type,
        provider_user_id=provider_user_id,
        user_id=db_user.user_id
    )
    db.add(db_oauth)
    await db.commit()

    return {
        "status": "success",
        "is_new_user": True,
        "user": {
            "user_id": db_user.user_id,
            "nickname": db_user.nickname,
            "email": db_user.email or ""
        }
    }


# user_id로 유저 조회
async def get_user(db: AsyncSession, user_id: str):
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


# 유저 정보 전체 수정
async def update_user(db: AsyncSession, user_id: str, user_in: UserCreate):
    db_user = await get_user(db, user_id)
    if not db_user:
        return None
    for key, value in user_in.model_dump(exclude_unset=True).items():
        setattr(db_user, key, value)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# 닉네임 변경
async def update_user_nickname(db: AsyncSession, user_id: str, nickname: str):
    db_user = await get_user(db, user_id)
    if not db_user:
        return None
    db_user.nickname = nickname
    await db.commit()
    await db.refresh(db_user)
    return db_user


# 프로필 수정
async def update_user_profile(db: AsyncSession, user_id: str, update_data: dict):
    db_user = await get_user(db, user_id)
    if not db_user:
        return None

    update_values = {}
    if "nickname" in update_data:
        update_values["nickname"] = update_data["nickname"]

    if "profile_detail" in update_data:
        current_profile = db_user.profile_detail or {}
        new_profile = {**current_profile, **update_data["profile_detail"]}
        update_values["profile_detail"] = new_profile

    if update_values:
        stmt = sqlalchemy_update(User).where(User.user_id == user_id).values(**update_values)
        result = await db.execute(stmt)
        if result.rowcount == 0:
            return None
        await db.commit()
        
        # 캐시 무효화를 위해 객체 강제 새로고침
        await db.refresh(db_user)

    return db_user


# 회원 탈퇴 시 연인 관계 자동 해제
async def disconnect_couple_on_user_deactivation(db: AsyncSession, user_id: str):
    """회원 탈퇴 시 연인 관계 자동 해제 + 관련 연인 신청 삭제"""
    # 사용자 정보 조회
    user_result = await db.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()
    
    if user:
        # 1. 연인 관계 삭제
        couple_query = select(Couple).where(
            or_(Couple.user1_id == user_id, Couple.user2_id == user_id)
        )
        couple_result = await db.execute(couple_query)
        couple = couple_result.scalar_one_or_none()
        
        if couple:
            await db.delete(couple)
            print(f"✅ 연인 관계 해제: {user_id}")
        
        # 2. 🔥 탈퇴 사용자와 관련된 모든 연인 신청 삭제
        await db.execute(
            delete(CoupleRequest).where(
                or_(
                    CoupleRequest.requester_id == user_id,  # 탈퇴자가 보낸 신청
                    CoupleRequest.partner_nickname == user.nickname  # 탈퇴자가 받은 신청
                )
            )
        )
        
        await db.commit()
        print(f"✅ 연인 신청 기록 삭제: {user.nickname}")
        return True
    
    return False

# 회원 탈퇴 (논리 삭제)
async def delete_user_with_validation(db: AsyncSession, req: UserDeleteRequest):
    user = await get_user(db, req.user_id)
    if not user or user.nickname != req.nickname:
        return None
    
    # 🔥 연인 관계 자동 해제
    await disconnect_couple_on_user_deactivation(db, req.user_id)
    # 채팅 세션 삭제
    await db.execute(delete(ChatSession).where(ChatSession.user_id == req.user_id))

    # 코스 삭제
    await db.execute(delete(Course).where(Course.user_id == req.user_id))

    # 댓글 삭제
    await db.execute(delete(Comment).where(Comment.user_id == req.user_id))
    
    # 기존 사용자 탈퇴 처리
    user.user_status = "inactive"
    user.couple_info = None  # 연인 정보 초기화
    await db.commit()
    return True


# 마이페이지 상세정보 수정
async def update_profile_detail(db: AsyncSession, user_id: str, profile_data: dict):
    db_user = await get_user(db, user_id)
    if not db_user:
        return None

    current_profile = db_user.profile_detail or {}
    filtered_profile_data = {
        k: v for k, v in profile_data.items()
        if v is not None and v != "" and v != []
    }
    new_profile = {**current_profile, **filtered_profile_data}
    update_values = {
        "profile_detail": new_profile,
        "updated_at": func.now()
    }
    if "age" in filtered_profile_data:
        update_values["age"] = filtered_profile_data["age"]
    if "gender" in filtered_profile_data:
        update_values["gender"] = filtered_profile_data["gender"]
    if "mbti" in filtered_profile_data:
        update_values["mbti"] = filtered_profile_data["mbti"]
    if "general_preferences" in filtered_profile_data:
        update_values["general_preferences"] = filtered_profile_data["general_preferences"]

    stmt = sqlalchemy_update(User).where(User.user_id == user_id).values(**update_values)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount > 0:
        return await get_user(db, user_id)
    return None


# 탈퇴한 유저 재가입 처리 (크레딧 지급 없음)
async def recreate_user_for_deactivated(
    db: AsyncSession,
    provider_type: str,
    provider_user_id: str,
    nickname: str,
    email: str
):
    # 1. OAuth ID로 기존 OAuth 정보 찾기
    oauth_result = await db.execute(
        select(UserOAuth).where(
            UserOAuth.provider_type == provider_type,
            UserOAuth.provider_user_id == provider_user_id
        )
    )
    oauth_user = oauth_result.scalar_one_or_none()
    
    if oauth_user:
        # 2. 기존 유저 정보 조회
        user_result = await db.execute(select(User).where(User.user_id == oauth_user.user_id))
        existing_user = user_result.scalar_one_or_none()
        
        if existing_user and existing_user.user_status == "inactive":
            # 3. 기존 유저 정보 초기화 (탈퇴한 유저를 새 가입자처럼 만들기)
            existing_user.nickname = nickname
            existing_user.email = email
            existing_user.user_status = "active"
            existing_user.profile_detail = None
            existing_user.couple_info = None
            # 중요: 크레딧 지급 없음 (무한 가입 방지)
            
            # 4. OAuth 정보는 그대로 유지 (토큰 제거됨)
            
            await db.commit()
            await db.refresh(existing_user)
            
            return {
                "status": "success",
                "is_new_user": True,
                "user": {
                    "user_id": existing_user.user_id,
                    "nickname": existing_user.nickname,
                    "email": existing_user.email or ""
                }
            }
    
    # 예외 상황 처리
    raise Exception("탈퇴한 유저를 찾을 수 없습니다.")
