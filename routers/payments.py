# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from db.session import get_db
from auth.rate_limiter import record_deposit_generate_action, record_refund_request_action, record_balance_deduct_action
from controllers.payments_controller import (
    generate_deposit_name, process_payment, deduct_balance,
    get_payment_history, get_user_deposit_summary
)
from controllers.refund_controller import (
    create_refund_request as create_user_refund_request, get_refund_history as get_user_refund_history, calculate_refundable_amount
)
from crud.crud_refund_new import create_refund_request as create_refund_request_new, get_user_refund_history as get_refund_history_new
from schemas.deposit_schema import DepositRequestCreate, DepositGenerateResponse
from schemas.payment_schema import (
    BalanceDeductRequest, RefundRequestResponse,
    PaymentHistoryResponse, RefundableAmountResponse
)
from schemas.refund_schema import RefundRequestCreate
from auth.dependencies import get_current_user
from crud.crud_payment import get_user_balance

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
logger = logging.getLogger(__name__)

# 사용자 잔액 조회 API
@router.get("/balance")
async def get_current_user_balance(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """사용자 잔액 조회 API"""
    try:
        user_balance = await get_user_balance(db, current_user.user_id)
        
        if not user_balance:
            return {"balance": 0}
        
        return {"balance": user_balance.current_balance}
        
    except Exception as e:
        logger.error(f"잔액 조회 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="잔액 조회 중 서버 오류가 발생했습니다"
        )

# 7.1.1 POST /deposit/generate - 입금 요청 생성 API
@router.post("/deposit/generate", response_model=DepositGenerateResponse)
async def create_deposit_request(
    request: DepositRequestCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    입금 요청 생성 API
    - 제한 사항: 1분당 1회
    - 사용자별 고유 입금 계좌 생성
    - 1시간 후 자동 만료
    """
    try:
        user_id = current_user.user_id
        
        # payments_controller의 generate_deposit_name 함수 호출
        result = await generate_deposit_name(
            db=db,
            user_id=user_id,
            bank_name=request.bank_name,
            account_number=request.account_number
        )
        
        if not result["success"]:
            if result.get("error_code") == "RATE_LIMIT_EXCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
        
        return DepositGenerateResponse(**result["data"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"입금 요청 생성 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="입금 요청 생성 중 서버 오류가 발생했습니다"
        )

# 7.1.2 POST /deduct - 잔액 차감 API
@router.post("/deduct")
async def deduct_user_balance(
    request: BalanceDeductRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(record_balance_deduct_action)
):
    """
    잔액 차감 API (결제 처리)
    - 제한 사항: 1분당 10회
    - 잔액 부족 시 에러 반환
    - 차감 내역 자동 기록
    """
    try:
        user_id = current_user.user_id
        
        # payments_controller의 deduct_balance 함수 호출
        result = await deduct_balance(
            db=db,
            user_id=user_id,
            deduct_request=request
        )
        
        if not result["success"]:
            if result.get("error_code") == "INSUFFICIENT_BALANCE":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"잔액 차감 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="잔액 차감 중 서버 오류가 발생했습니다"
        )

# 7.1.3 GET /history - 사용자 결제 내역 조회 API
@router.get("/history")
async def get_user_payment_history(
    page: int = 1,
    size: int = 10,
    history_type: Optional[str] = None,  # "charge", "usage", None
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 결제 내역 조회 API
    - 충전/사용 내역 통합 조회
    - 페이지네이션 지원
    - 내역 타입별 필터링 (charge/usage)
    """
    try:
        user_id = current_user.user_id
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        # history_type 검증
        if history_type and history_type not in ["charge", "usage"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="history_type은 'charge' 또는 'usage'만 허용됩니다"
            )
        
        # payments_controller의 get_payment_history 함수 호출
        result = await get_payment_history(
            db=db,
            user_id=user_id,
            page=page,
            size=size,
            history_type=history_type
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
        logger.error(f"사용자 결제 내역 조회 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 결제 내역 조회 중 서버 오류가 발생했습니다"
        )

# 7.1.4 GET /refundable/{charge_history_id} - 환불 가능 금액 조회
@router.get("/refundable/{charge_history_id}", response_model=RefundableAmountResponse)
async def get_refundable_charge_amount(
    charge_history_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 가능 금액 조회 API
    - 특정 충전건의 환불 가능 금액 계산
    - 이미 사용된 금액 제외
    - 부분 사용 시 잔여 금액만 계산
    """
    try:
        user_id = current_user.user_id
        
        # refund_controller의 calculate_refundable_amount 함수 호출
        result = await calculate_refundable_amount(
            db=db,
            user_id=user_id,
            charge_history_id=charge_history_id
        )
        
        if not result["success"]:
            if result.get("error_code") == "CHARGE_HISTORY_NOT_FOUND":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result["message"]
                )
            elif result.get("error_code") == "UNAUTHORIZED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
        
        return RefundableAmountResponse(**result["data"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 가능 금액 조회 실패 - user_id: {current_user.user_id}, charge_history_id: {charge_history_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 가능 금액 조회 중 서버 오류가 발생했습니다"
        )

# 7.1.5 POST /refund/request - 환불 신청 API
@router.post("/refund/request")
async def create_refund_request(
    request: RefundRequestCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    환불 신청 API
    - 관리자 승인 필요
    - 중복 환불 신청 방지
    - 승인 후 자동 계좌 이체 처리
    """
    try:
        user_id = current_user.user_id
        
        # 디버깅: 요청 데이터 로깅
        logger.info(f"환불 요청 데이터 - user_id: {user_id}, request: {request}")
        logger.info(f"요청 데이터 타입 - refund_amount: {type(request.refund_amount)}")
        
        # 새로운 환불 시스템 사용
        refund_request = await create_refund_request_new(
            db=db,
            user_id=user_id,
            refund_data=request
        )
        
        # RefundRequest 객체를 dict로 변환 (계산된 필드 포함)
        from datetime import datetime, timezone
        
        result_data = {
            "refund_request_id": refund_request.refund_request_id,
            "user_id": refund_request.user_id,
            "bank_name": refund_request.bank_name,
            "account_number": refund_request.account_number,
            "account_holder": refund_request.account_holder,
            "refund_amount": refund_request.refund_amount,
            "contact": refund_request.contact,
            "reason": refund_request.reason,
            "status": refund_request.status,  # 문자열 그대로 (use_enum_values=True)
            "created_at": refund_request.created_at,
            "updated_at": refund_request.updated_at,
            "processed_at": refund_request.processed_at,
            "admin_memo": refund_request.admin_memo,
            # 계산된 필드들
            "is_pending": refund_request.status == "pending",
            "is_approved": refund_request.status == "approved",
            "is_completed": refund_request.status == "completed",
            "days_since_request": 0  # 방금 생성된 요청이므로 0일
        }
        
        return {
            "success": True,
            "message": "환불 신청이 완료되었습니다",
            "data": result_data
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        # 비즈니스 로직 에러 (환불 불가능, 금액 초과 등)
        error_msg = str(e)
        if "이미 처리중인" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        elif "환불 가능 금액" in error_msg or "최소 환불 금액" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"환불 신청 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        logger.error(f"환불 신청 에러 타입: {type(e)}")
        import traceback
        logger.error(f"환불 신청 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 신청 중 서버 오류가 발생했습니다"
        )

# 7.1.6 GET /refund/history - 환불 신청 내역 조회 API
@router.get("/refund/history")
async def get_refund_history(
    page: int = 1,
    size: int = 10,
    status_filter: Optional[str] = None,  # "pending", "approved", "rejected", "completed"
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 신청 내역 조회 API
    - 사용자별 환불 신청 현황
    - 상태별 필터링 지원
    - 페이지네이션 지원
    """
    try:
        user_id = current_user.user_id
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 1000:
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
        
        # 새로운 환불 시스템 사용
        skip = (page - 1) * size
        refund_requests = await get_refund_history_new(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=size,
            status_filter=status_filter
        )
        
        # 응답 데이터 구성
        from datetime import datetime, timezone
        
        return {
            "success": True,
            "data": {
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
                        "updated_at": req.updated_at,
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
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 신청 내역 조회 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 신청 내역 조회 중 서버 오류가 발생했습니다"
        )

# 7.1.7 GET /refundable-histories - 환불 가능한 충전 내역 조회 API
@router.get("/refundable-histories")
async def get_refundable_histories(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    환불 가능한 충전 내역 조회 API (대기중 환불 요청 제외)
    - 환불 가능한 충전 내역만 조회
    - 대기중인 환불 요청이 있는 내역 제외
    """
    try:
        user_id = current_user.user_id
        
        # refund_controller의 get_refundable_histories 함수 호출
        from controllers.refund_controller import get_refundable_histories as get_user_refundable_histories
        result = await get_user_refundable_histories(db=db, user_id=user_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result["data"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"환불 가능 내역 조회 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환불 가능 내역 조회 중 서버 오류가 발생했습니다"
        )

# 7.1.8 사용자 요약 정보 API - 충전금 및 잔액
@router.get("/deposit/summary")
async def get_deposit_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자 요약 정보 API
    - 총 충전 금액 표시
    - 현재 잔액 확인
    - 최근 거래 내역
    """
    try:
        user_id = current_user.user_id
        
        # payments_controller의 get_user_deposit_summary 함수 호출
        result = await get_user_deposit_summary(db=db, user_id=user_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result["data"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 요약 정보 조회 실패 - user_id: {current_user.user_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 요약 정보 조회 중 서버 오류가 발생했습니다"
        )