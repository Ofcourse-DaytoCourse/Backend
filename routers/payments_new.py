# -*- coding: utf-8 -*-
"""
새로운 환불 시스템 라우터
charge_history_id 의존성 제거, 단순한 환불 가능 금액 기반 시스템
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from db.session import get_db
from crud.crud_refund_new import (
    get_user_refundable_amount, create_refund_request, 
    get_user_refund_history, approve_refund_new, reject_refund_new,
    get_refund_request, get_all_refund_requests
)
from schemas.refund_schema import RefundRequestCreate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/payments", tags=["payments-refund"])
logger = logging.getLogger(__name__)

# ================================================================
# 1. 환불 가능 금액 조회
# ================================================================

@router.get("/refund/available")
async def get_refund_available_amount(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 환불 가능 금액 조회 API
    - 전체 환불 가능 잔액 반환
    - 대기중인 환불 요청 여부 확인
    """
    try:
        user_id = current_user.user_id
        
        result = await get_user_refundable_amount(db, user_id)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"환불 가능 금액 조회 오류 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 가능 금액 조회 중 오류가 발생했습니다"
        )

# ================================================================
# 2. 환불 신청
# ================================================================

@router.post("/refund/request")
async def create_user_refund_request(
    request: RefundRequestCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 신청 API (새로운 시스템)
    - 원하는 금액만큼 환불 신청
    - 사용자당 1개의 대기중인 요청만 허용
    """
    try:
        user_id = current_user.user_id
        
        refund_request = await create_refund_request(db, user_id, request)
        
        logger.info(f"환불 신청 완료 - user_id: {user_id}, amount: {request.refund_amount}")
        
        return {
            "success": True,
            "message": "환불 신청이 완료되었습니다",
            "data": {
                "refund_request_id": refund_request.refund_request_id,
                "refund_amount": refund_request.refund_amount,
                "status": refund_request.status,
                "created_at": refund_request.created_at
            }
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"환불 신청 오류 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 신청 중 오류가 발생했습니다"
        )

# ================================================================
# 3. 환불 내역 조회
# ================================================================

@router.get("/refund/history")
async def get_refund_history(
    page: int = 1,
    size: int = 10,
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 환불 내역 조회 API
    - 페이지네이션 지원
    - 상태별 필터링 가능
    """
    try:
        if page < 1 or size < 1 or size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        user_id = current_user.user_id
        skip = (page - 1) * size
        
        refund_history = await get_user_refund_history(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=size,
            status_filter=status_filter
        )
        
        return {
            "success": True,
            "data": {
                "refund_history": [
                    {
                        "refund_request_id": item.refund_request_id,
                        "refund_amount": item.refund_amount,
                        "bank_name": item.bank_name,
                        "account_number": item.account_number,
                        "account_holder": item.account_holder,
                        "status": item.status,
                        "reason": item.reason,
                        "created_at": item.created_at,
                        "processed_at": item.processed_at,
                        "admin_memo": item.admin_memo
                    } for item in refund_history
                ],
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": len(refund_history)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 내역 조회 오류 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 내역 조회 중 오류가 발생했습니다"
        )

# ================================================================
# 4. 관리자 전용 API (기존 admin.py에서 이동)
# ================================================================

@router.post("/admin/refund/{refund_request_id}/approve")
async def approve_refund_admin(
    refund_request_id: int,
    admin_memo: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 승인 API (관리자 전용)
    - 새로운 시스템 적용
    """
    try:
        # TODO: 관리자 권한 체크 추가
        
        refund_request = await get_refund_request(db, refund_request_id)
        if not refund_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="환불 요청을 찾을 수 없습니다"
            )
        
        approved_request = await approve_refund_new(db, refund_request, admin_memo)
        
        logger.info(f"환불 승인 완료 - refund_id: {refund_request_id}")
        
        return {
            "success": True,
            "message": "환불이 승인되었습니다",
            "data": {
                "refund_request_id": approved_request.refund_request_id,
                "status": approved_request.status,
                "processed_at": approved_request.processed_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 승인 오류 - refund_id: {refund_request_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 승인 중 오류가 발생했습니다"
        )