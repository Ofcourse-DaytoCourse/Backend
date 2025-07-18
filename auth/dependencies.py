from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db, SessionLocal
from crud.crud_user import get_user
from auth.jwt_handler import verify_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials
    user_id = verify_token(token)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

async def get_authenticated_user_with_session(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """JWT 인증과 DB 세션을 단일 함수로 통합 - ROLLBACK 문제 해결"""
    async with SessionLocal() as db:
        try:
            # 🔍 디버깅: 받은 인증 정보 확인
            print(f"🔍 받은 credentials: {credentials}")
            if credentials:
                print(f"🔍 credentials.scheme: {credentials.scheme}")
                print(f"🔍 credentials.credentials: {credentials.credentials}")
            else:
                print("🔍 credentials가 None입니다")
            
            # JWT 토큰 검증
            token = credentials.credentials
            user_id = verify_token(token)
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 사용자 조회
            user = await get_user(db, user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            # 사용자와 DB 세션 반환
            return user, db
            
        except HTTPException:
            # HTTP 예외는 그대로 전파
            raise
        except Exception as e:
            # 예상치 못한 오류 시 롤백 후 예외 발생
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication error: {str(e)}"
            )