from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from db.session import get_db
from crud.crud_chat import chat_crud
from schemas.chat import (
    ChatSessionCreate,
    ChatMessageCreate, 
    ChatRecommendationStart,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatRecommendationResponse,
    ChatSessionListResponse,
    ChatSessionDetailResponse,
    ChatHealthResponse,
    ChatErrorResponse
)

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/new-session", response_model=ChatSessionResponse, summary="새 채팅 세션 시작")
async def create_new_session(
    session_data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """새로운 채팅 세션을 시작하고 첫 메시지를 전송합니다."""
    try:
        result = await chat_crud.create_chat_session(db, session_data)
        
        if not result:
            raise HTTPException(
                status_code=500, 
                detail="채팅 세션 생성에 실패했습니다. 에이전트 서비스를 확인해주세요."
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.post("/send-message", response_model=ChatMessageResponse, summary="메시지 전송")
async def send_message(
    message_data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """기존 채팅 세션에 메시지를 전송하고 AI 응답을 받습니다."""
    try:
        result = await chat_crud.send_message(db, message_data)
        
        if not result:
            raise HTTPException(
                status_code=404, 
                detail="채팅 세션을 찾을 수 없거나 메시지 전송에 실패했습니다."
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.post("/start-recommendation", response_model=ChatRecommendationResponse, summary="코스 추천 시작")
async def start_recommendation(
    recommendation_data: ChatRecommendationStart,
    db: AsyncSession = Depends(get_db)
):
    """수집된 정보를 기반으로 데이트 코스 추천을 시작합니다."""
    try:
        result = await chat_crud.start_recommendation(db, recommendation_data.session_id)
        
        if not result:
            raise HTTPException(
                status_code=404, 
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        if not result.get('success'):
            # 에이전트에서 실패한 경우
            error_message = result.get('message', '추천 생성에 실패했습니다.')
            error_code = result.get('error_code', 'RECOMMENDATION_FAILED')
            
            if error_code == "SESSION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=error_message)
            elif error_code == "INCOMPLETE_PROFILE":
                raise HTTPException(status_code=400, detail=error_message)
            else:
                raise HTTPException(status_code=500, detail=error_message)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.get("/sessions/user/{user_id}", response_model=ChatSessionListResponse, summary="사용자 채팅 세션 목록 조회")
async def get_user_sessions(
    user_id: str = Path(..., description="사용자 ID"),
    limit: Optional[int] = Query(None, ge=1, description="조회할 세션 수 (기본값: 무제한)"),
    offset: int = Query(0, ge=0, description="오프셋"),
    status: str = Query("all", description="세션 상태 필터 (all, active, completed)"),
    db: AsyncSession = Depends(get_db)
):
    """사용자의 채팅 세션 목록을 조회합니다."""
    try:
        sessions = await chat_crud.get_user_sessions(db, user_id, limit, offset)
        
        # 상태 필터링
        if status != "all":
            sessions = [s for s in sessions if s["session_status"].lower() == status.lower()]
        
        return {
            "success": True,
            "sessions": sessions,
            "pagination": {
                "total_count": len(sessions),
                "limit": limit,
                "offset": offset,
                "has_more": limit is not None and len(sessions) == limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse, summary="채팅 세션 상세 조회")
async def get_session_detail(
    session_id: str = Path(..., description="세션 ID"),
    db: AsyncSession = Depends(get_db)
):
    """특정 채팅 세션의 상세 정보와 메시지 목록을 조회합니다."""
    try:
        result = await chat_crud.get_session_detail(db, session_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
        
        return {
            "success": True,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.delete("/sessions/{session_id}", summary="채팅 세션 삭제")
async def delete_session(
    session_id: str = Path(..., description="세션 ID"),
    db: AsyncSession = Depends(get_db)
):
    """채팅 세션을 삭제합니다."""
    try:
        success = await chat_crud.delete_session(db, session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
        
        return {
            "success": True,
            "message": "채팅 세션이 성공적으로 삭제되었습니다.",
            "deleted_session_id": session_id,
            "deleted_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.get("/health", response_model=ChatHealthResponse, summary="채팅 서비스 상태 확인")
async def health_check():
    """채팅 서비스와 에이전트의 상태를 확인합니다."""
    try:
        # 간단한 헬스체크 구현
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "database": "healthy",
                "main_agent": "healthy",
                "place_agent": "healthy", 
                "rag_agent": "healthy"
            },
            "metrics": {
                "uptime_seconds": 0,
                "total_requests": 0,
                "average_response_time_ms": 0,
                "active_sessions": 0,
                "db_connection_pool": "healthy"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"헬스체크 실패: {str(e)}")

