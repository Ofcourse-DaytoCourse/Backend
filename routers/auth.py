from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import httpx
import config
from db.session import get_db
from sqlalchemy.future import select
from sqlalchemy import update
from models.user import User
from crud.crud_user import get_user_by_kakao_id, create_user_with_oauth
from auth.jwt_handler import create_access_token

router = APIRouter()

class SocialLoginRequest(BaseModel):
    provider: str
    code: str
    force_reactivate: bool = False  # 복구 플래그

class SocialLoginResponse(BaseModel):
    accessToken: str
    user: dict
    is_new_user: bool

@router.post("/auth/social-login")
async def social_login(request: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    if request.provider != "kakao":
        raise HTTPException(status_code=400, detail="지원하지 않는 소셜 로그인 제공자입니다.")
    
    try:
        # 1️⃣ 카카오 토큰 요청
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": config.KAKAO_REST_API_KEY,
            "redirect_uri": config.KAKAO_REDIRECT_URI,
            "code": request.code
        }
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="카카오 토큰 요청 실패")

        token_info = token_response.json()
        access_token = token_info["access_token"]

        # 2️⃣ 카카오 사용자 정보 요청
        user_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            user_response = await client.get(user_url, headers=headers)
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="카카오 사용자 정보 요청 실패")

        user_info = user_response.json()
        kakao_id = str(user_info["id"])
        nickname = user_info.get("properties", {}).get("nickname", "")
        email = user_info.get("kakao_account", {}).get("email", "")

        # 3️⃣ 유저 확인 및 생성/차단
        result = await create_user_with_oauth(db, "kakao", kakao_id, nickname, email)

        if result.get("status") == "deactivated":
            if request.force_reactivate:
                # ✅ 복구 요청일 경우 활성화
                await db.execute(
                    update(User)
                    .where(User.user_id == result["user_id"])
                    .values(user_status="active")
                )
                await db.commit()

                user_result = await db.execute(select(User).where(User.user_id == result["user_id"]))
                user = user_result.scalar_one()

                return SocialLoginResponse(
                    accessToken=create_access_token(data={"user_id": user.user_id}),
                    user={
                        "user_id": user.user_id,
                        "nickname": user.nickname,
                        "email": user.email or ""
                    },
                    is_new_user=False
                )
            else:
                # ❌ 복구 요청이 아닌 경우 → user 포함해서 반환 (프론트 에러 방지)
                return {
                    "status": "deactivated",
                    "message": result["message"],
                    "user": {
                        "user_id": result["user_id"],
                        "nickname": nickname,
                        "email": email or ""
                    },
                    "is_new_user": False,
                    "accessToken": ""
                }

        # 4️⃣ 정상 로그인
        return SocialLoginResponse(
            accessToken=create_access_token(data={"user_id": result['user']['user_id']}),
            user=result["user"],
            is_new_user=result["is_new_user"]
        )

    except Exception as e:
        import traceback
        print(f"에러 발생: {str(e)}")
        print(f"에러 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="소셜 로그인 처리 중 오류 발생")

@router.get("/oauth/callback/kakao")
async def kakao_callback(code: str):
    return {"message": "카카오 로그인 콜백 성공", "code": code}
