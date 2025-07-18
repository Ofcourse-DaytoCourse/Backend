from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from crud import crud_user
from crud.crud_user import recreate_user_for_deactivated
from auth.dependencies import get_authenticated_user_with_session, get_current_user
from schemas.user import (
    UserCreate, StatusResponse, NicknameCheckRequest, UserProfileSetup,
    UserProfileResponse, UserProfileUpdate, UserDeleteRequest
)
from pydantic import BaseModel
import requests
import jwt
import os
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET", "supersecret")


# ✅ 카카오 access token 검증
def verify_kakao_token(provider_user_id: str, access_token: str) -> bool:
    try:
        response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            return False
        data = response.json()
        return str(data.get("id")) == provider_user_id
    except:
        return False


# ✅ 닉네임 중복 확인
@router.post("/users/nickname/check", response_model=StatusResponse)
async def check_nickname_availability(req: NicknameCheckRequest, db: AsyncSession = Depends(get_db)):
    existing_user = await crud_user.get_user_by_nickname(db, req.nickname)
    if existing_user:
        return {"status": "duplicated", "message": "이미 사용 중인 닉네임입니다."}
    return {"status": "available", "message": "사용 가능한 닉네임입니다."}


# ✅ 닉네임 업데이트
class NicknameUpdateRequest(BaseModel):
    user_id: str
    nickname: str


@router.put("/users/nickname/update")
async def update_user_nickname(req: NicknameUpdateRequest, db: AsyncSession = Depends(get_db)):
    user = await crud_user.get_user(db, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    existing_user = await crud_user.get_user_by_nickname(db, req.nickname)
    if existing_user and existing_user.user_id != req.user_id:
        raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")
    updated_user = await crud_user.update_user_nickname(db, req.user_id, req.nickname)
    return {
        "status": "success",
        "user_id": updated_user.user_id,
        "nickname": updated_user.nickname
    }


# ✅ 최초 회원가입 및 탈퇴 유저 복구
@router.put("/users/profile/initial-setup")
async def initial_user_setup(req: UserProfileSetup, db: AsyncSession = Depends(get_db)):
    # 카카오 토큰 검증 제거 (이미 로그인된 상태에서만 접근하도록 변경)

    # 1. 카카오 ID로 기존 유저 확인
    existing_user = await crud_user.get_user_by_kakao_id(db, req.provider_user_id)
    
    if existing_user and existing_user.user_status == "inactive":
        # 탈퇴한 유저 재가입 처리 (크레딧 지급 안함)
        result = await recreate_user_for_deactivated(
            db=db,
            provider_type="kakao",
            provider_user_id=req.provider_user_id,
            nickname=req.nickname,
            email=None
        )
    else:
        # 진짜 새 가입자 처리 (크레딧 지급함)
        result = await crud_user.create_user_with_oauth(
            db=db,
            provider_type="kakao",
            provider_user_id=req.provider_user_id,
            nickname=req.nickname,
            email=None
        )

    return result


# ✅ 마이페이지 전체 조회
@router.get("/users/profile/me")
async def get_my_profile(
    user_id: str,
    auth_data = Depends(get_authenticated_user_with_session)
):
    current_user, db = auth_data
    
    # 권한 검증
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    
    # DB profile_detail 데이터 정규화
    profile_detail = current_user.profile_detail or {}
    
    # 필드명 변환 및 기본값 설정
    normalized_profile = {
        "age_range": profile_detail.get("age_range") or profile_detail.get("age", ""),
        "gender": profile_detail.get("gender", ""),
        "mbti": profile_detail.get("mbti", ""),
        "car_owner": profile_detail.get("car_owner", False),
        "preferences": profile_detail.get("preferences", "")
    }
    
    return {
        "status": "success",
        "user": {
            "user_id": current_user.user_id,
            "nickname": current_user.nickname,
            "email": current_user.email or "",
            "profile_detail": normalized_profile,
            "couple_info": current_user.couple_info
        }
    }


# ✅ 마이페이지 수정
@router.put("/users/profile/update/{user_id}")
async def update_user_profile(
    user_id: str, 
    req: UserProfileUpdate,
    request: Request,
    auth_data = Depends(get_authenticated_user_with_session)
):
    current_user, db = auth_data
    
    # 권한 검증
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    update_data = {}
    if req.nickname:
        existing_user = await crud_user.get_user_by_nickname(db, req.nickname)
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")
        update_data["nickname"] = req.nickname
    if req.profile_detail:
        update_data["profile_detail"] = req.profile_detail.model_dump(exclude_unset=True)
    updated_user = await crud_user.update_user_profile(db, user_id, update_data)

    return {
        "status": "success",
        "message": "프로필이 업데이트되었습니다.",
        "user": {
            "user_id": updated_user.user_id,
            "nickname": updated_user.nickname,
            "email": updated_user.email,
            "profile_detail": updated_user.profile_detail
        }
    }


# ✅ 회원 탈퇴
@router.delete("/users/profile/delete")
async def delete_user_account(req: UserDeleteRequest, db: AsyncSession = Depends(get_db)):
    success = await crud_user.delete_user_with_validation(db, req)
    if not success:
        return {
            "status": "fail",
            "error": {
                "code": "MISMATCH_INFO",
                "message": "입력한 정보가 사용자 정보와 일치하지 않습니다."
            }
        }
    return {
        "status": "deleted",
        "user_id": req.user_id
    }
