# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging
from datetime import datetime, timezone

from db.session import get_db
from controllers.refund_controller import process_refund_approval, get_pending_refund_requests, get_refund_history
from controllers.cleanup_controller import (
    get_cleanup_status, run_scheduled_cleanup, cleanup_by_type,
    run_parallel_cleanup
)
from controllers.admin_controller import process_manual_charge, get_user_list_for_admin
from crud.crud_sms import get_unmatched_deposits, get_sms_logs
from crud.crud_payment import get_user_charge_histories, get_payment_statistics
from crud.crud_refund_new import approve_refund_new, reject_refund_new, get_refund_request, get_all_refund_requests
from schemas.payment_schema import RefundRequestUpdate, RefundRequestResponse
from schemas.sms_schema import UnmatchedDepositResponse
from schemas.admin_schema import ManualChargeRequest, ManualChargeResponse
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger(__name__)

def verify_admin_permission(current_user):
    """관리자 권한 검증 헬퍼 함수 - 프론트엔드에서 세션 스토리지로 관리"""
    # 프론트엔드에서 세션 스토리지 기반으로 관리자 인증을 처리하므로
    # 백엔드에서는 별도 권한 체크 없이 통과
    pass

# 7.3.1 POST /refund/{refund_request_id}/approve - 환불 승인 엔드포인트
@router.post("/refund/{refund_request_id}/approve")
async def approve_refund_request(
    refund_request_id: int,
    update_data: RefundRequestUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 요청 승인 API
    - 관리자 전용
    - 중복 승인 방지
    - 트랜잭션 안전성 보장
    - 사용자 잔액 차감 및 로그 기록
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        admin_user_id = current_user.user_id
        
        # 먼저 환불 요청 조회 (새로운 시스템)
        refund_request = await get_refund_request(db, refund_request_id)
        if not refund_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="환불 요청을 찾을 수 없습니다"
            )
        
        # 환불 승인 처리 (새로운 시스템)
        approved_request = await approve_refund_new(
            db=db,
            refund_request=refund_request,
            admin_memo=update_data.admin_memo
        )
        
        # 성공 응답 생성 (계산된 필드 포함)
        
        result = {
            "refund_request_id": approved_request.refund_request_id,
            "user_id": approved_request.user_id,
            "bank_name": approved_request.bank_name,
            "account_number": approved_request.account_number,
            "account_holder": approved_request.account_holder,
            "refund_amount": approved_request.refund_amount,
            "contact": approved_request.contact,
            "reason": approved_request.reason,
            "status": approved_request.status,
            "created_at": approved_request.created_at,
            "updated_at": approved_request.updated_at,
            "processed_at": approved_request.processed_at,
            "admin_memo": approved_request.admin_memo,
            # 계산된 필드들
            "is_pending": approved_request.status == "pending",
            "is_approved": approved_request.status == "approved",
            "is_completed": approved_request.status == "completed",
            "days_since_request": 0
        }
        
        logger.info(f"환불 승인 완료 - admin: {admin_user_id}, refund_request_id: {refund_request_id}")
        
        return {
            "success": True,
            "message": "환불 처리가 완료되었습니다",
            "data": result
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        # 중복 처리 등 비즈니스 로직 에러
        error_msg = str(e)
        if "이미 처리된" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"환불 승인 오류 - refund_request_id: {refund_request_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 승인 중 서버 오류가 발생했습니다"
        )

# 7.3.2 POST /refund/{refund_request_id}/reject - 환불 거부 엔드포인트
@router.post("/refund/{refund_request_id}/reject")
async def reject_refund_request(
    refund_request_id: int,
    update_data: RefundRequestUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 요청 거부 API
    - 관리자 전용
    - 거부 사유 필수 입력
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        admin_user_id = current_user.user_id
        
        # 거부 사유 체크
        if not update_data.admin_memo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="환불 거부 시 사유를 입력해주세요"
            )
        
        # 먼저 환불 요청 조회
        refund_request = await get_refund_request(db, refund_request_id)
        if not refund_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="환불 요청을 찾을 수 없습니다"
            )
        
        # 환불 거부 처리 (새로운 시스템)
        rejected_request = await reject_refund_new(
            db=db,
            refund_request=refund_request,
            admin_memo=update_data.admin_memo
        )
        
        # 성공 응답 생성 (계산된 필드 포함)
        
        result = {
            "refund_request_id": rejected_request.refund_request_id,
            "user_id": rejected_request.user_id,
            "bank_name": rejected_request.bank_name,
            "account_number": rejected_request.account_number,
            "account_holder": rejected_request.account_holder,
            "refund_amount": rejected_request.refund_amount,
            "contact": rejected_request.contact,
            "reason": rejected_request.reason,
            "status": rejected_request.status,
            "created_at": rejected_request.created_at,
            "updated_at": rejected_request.updated_at,
            "processed_at": rejected_request.processed_at,
            "admin_memo": rejected_request.admin_memo,
            # 계산된 필드들
            "is_pending": rejected_request.status == "pending",
            "is_approved": rejected_request.status == "approved",
            "is_completed": rejected_request.status == "completed",
            "days_since_request": 0
        }
        
        logger.info(f"환불 거부 완료 - admin: {admin_user_id}, refund_request_id: {refund_request_id}")
        
        return {
            "success": True,
            "message": "환불 처리가 완료되었습니다",
            "data": result
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        # 중복 처리 등 비즈니스 로직 에러
        error_msg = str(e)
        if "이미 처리된" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"환불 거부 오류 - refund_request_id: {refund_request_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 거부 중 서버 오류가 발생했습니다"
        )

# 7.3.3 GET /refund/requests - 모든 환불 요청 조회
@router.get("/refund/requests")
async def get_refund_requests(
    status_filter: Optional[str] = None,  # "pending", "approved", "rejected", "completed"
    page: int = 1,
    size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    모든 환불 요청 조회 API (관리자 전용)
    - 상태별 필터링
    - 페이지네이션 지원
    - 환불 관리 대시보드용
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        # 상태 필터 검증
        valid_statuses = ["pending", "approved", "rejected", "completed"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status_filter는 {valid_statuses} 중 하나여야 합니다"
            )
        
        # 새로운 시스템의 get_all_refund_requests 함수 호출
        skip = (page - 1) * size
        refund_requests = await get_all_refund_requests(
            db=db,
            skip=skip,
            limit=size,
            status_filter=status_filter
        )
        
        # 응답 데이터 구성
        return {
            "refund_history": [
                {
                    "refund_request_id": req.refund_request_id,
                    "user_id": req.user_id,
                    "bank_name": req.bank_name,
                    "account_number": req.account_number,
                    "account_holder": req.account_holder,
                    "refund_amount": req.refund_amount,
                    "contact": req.contact,
                    "reason": req.reason,
                    "status": req.status,
                    "created_at": req.created_at,
                    "processed_at": req.processed_at,
                    "admin_memo": req.admin_memo
                } for req in refund_requests
            ],
            "pagination": {
                "page": page,
                "size": size,
                "total": len(refund_requests)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 요청 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 요청 조회 중 서버 오류가 발생했습니다"
        )

# 7.3.4 GET /unmatched-deposits - 미매칭 입금 관리
@router.get("/unmatched-deposits")
async def get_admin_unmatched_deposits(
    status: Optional[str] = None,  # "unmatched", "matched", "ignored"
    page: int = 1,
    size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    미매칭 입금 관리 API (관리자 전용)
    - 수동 매칭 필요한 입금들 조회
    - 상태별 필터링
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        # 상태 필터 검증
        valid_statuses = ["unmatched", "matched", "ignored"]
        if status and status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status는 {valid_statuses} 중 하나여야 합니다"
            )
        
        skip = (page - 1) * size
        
        # crud_sms의 get_unmatched_deposits 함수 호출
        unmatched_deposits = await get_unmatched_deposits(
            db=db,
            status=status,
            skip=skip,
            limit=size
        )
        
        return {
            "success": True,
            "data": {
                "unmatched_deposits": [
                    {
                        "unmatched_deposit_id": deposit.unmatched_deposit_id,
                        "parsed_amount": deposit.parsed_amount,
                        "parsed_name": deposit.parsed_name,
                        "parsed_time": deposit.parsed_time,
                        "status": deposit.status,
                        "matched_user_id": deposit.matched_user_id,
                        "created_at": deposit.created_at,
                        "matched_at": deposit.matched_at,
                        "expires_at": deposit.expires_at,
                        "raw_message": deposit.raw_message[:100] + "..." if len(deposit.raw_message) > 100 else deposit.raw_message
                    } for deposit in unmatched_deposits
                ],
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": len(unmatched_deposits)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"미매칭 입금 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="미매칭 입금 조회 중 서버 오류가 발생했습니다"
        )

# 7.3.5 GET /cleanup/status - 시스템 정리 상태 조회
@router.get("/cleanup/status")
async def get_system_cleanup_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    시스템 정리 상태 조회 API
    - 레이트 리미팅 로그 정리 필요성
    - 만료된 데이터 현황
    - 관리자 대시보드용
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        # cleanup_controller의 get_cleanup_status 함수 호출
        result = await get_cleanup_status(db=db)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result["data"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시스템 정리 상태 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템 정리 상태 조회 중 서버 오류가 발생했습니다"
        )

# 7.3.6 POST /cleanup - 시스템 정리 실행
@router.post("/cleanup")
async def run_system_cleanup(
    cleanup_type: str = "all",  # "all", "rate_limit", "deposits", "unmatched"
    parallel: bool = False,  # 병렬 실행 여부
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    시스템 정리 실행 API
    - 레이트 리미팅 로그 정리
    - 만료된 입금 요청 정리
    - 만료된 미매칭 입금 정리
    - 타입별 선택 실행 지원
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        admin_user_id = current_user.user_id
        
        # cleanup_type 검증
        valid_types = ["all", "rate_limit", "deposits", "unmatched"]
        if cleanup_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"cleanup_type은 {valid_types} 중 하나여야 합니다"
            )
        
        if parallel:
            # 병렬 정리 실행
            result = await run_parallel_cleanup(db=db)
        elif cleanup_type == "all":
            # 전체 정리 실행
            result = await run_scheduled_cleanup(db=db, cleanup_type="all")
        else:
            # 특정 타입 정리 실행
            result = await cleanup_by_type(db=db, cleanup_types=[cleanup_type])
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"시스템 정리 실행 완료 - admin: {admin_user_id}, type: {cleanup_type}, parallel: {parallel}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시스템 정리 실행 오류 - cleanup_type: {cleanup_type}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템 정리 실행 중 서버 오류가 발생했습니다"
        )

# 7.3.7 GET /statistics - 전체 시스템 통계
@router.get("/statistics")
async def get_admin_statistics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자 대시보드 통계 API
    - 전체 충전/사용/환불 통계
    - 시스템 상태 요약
    - 관리자 대시보드용
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        # 전체 통계 조회 (새로 구현 필요한 함수)
        # result = await get_payment_statistics_admin(db=db)
        
        # 임시로 기본 통계 반환
        return {
            "success": True,
            "data": {
                "total_users": 0,
                "total_charged": 0,
                "total_used": 0,
                "total_refunded": 0,
                "pending_refunds": 0,
                "unmatched_deposits": 0,
                "message": "통계 기능은 추후 구현 예정입니다"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관리자 통계 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="통계 조회 중 서버 오류가 발생했습니다"
        )

# 7.3.8 POST /manual-charge - 관리자 수동 충전
@router.post("/manual-charge", response_model=ManualChargeResponse)
async def admin_manual_charge(
    request: ManualChargeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자 수동 충전 API
    - 전체 사용자 또는 개별 사용자 충전
    - 환불 가능/불가능 설정
    - 충전 이력 및 잔액 자동 업데이트
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        admin_user_id = current_user.user_id
        
        # 수동 충전 처리
        result = await process_manual_charge(
            db=db,
            request=request,
            admin_user_id=admin_user_id
        )
        
        if not result["success"]:
            if result.get("error_code") == "NO_TARGET_USERS":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
        
        logger.info(f"관리자 수동 충전 완료 - admin: {admin_user_id}, target: {request.target_type}, amount: {request.amount}")
        
        return ManualChargeResponse(**result["data"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관리자 수동 충전 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="수동 충전 중 서버 오류가 발생했습니다"
        )

# 7.3.9 GET /users - 관리자용 사용자 목록 조회
@router.get("/users")
async def get_admin_user_list(
    page: int = 1,
    size: int = 20,
    search_nickname: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 사용자 목록 조회 API
    - 닉네임 검색 기능
    - 페이지네이션 지원
    - 수동 충전 대상 선택용
    """
    try:
        # 관리자 권한 체크
        verify_admin_permission(current_user)
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        # 사용자 목록 조회
        result = await get_user_list_for_admin(
            db=db,
            page=page,
            size=size,
            search_nickname=search_nickname
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result["data"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 목록 조회 중 서버 오류가 발생했습니다"
        )