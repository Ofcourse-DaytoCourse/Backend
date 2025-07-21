# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from db.session import get_db
from controllers.sms_controller import (
    process_sms_end_to_end, get_manual_match_candidates, parse_sms_message
)
from crud.crud_sms import (
    get_sms_logs, get_unmatched_deposits, match_deposit_manually,
    get_unmatched_deposit
)
from schemas.sms_schema import (
    SmsParseRequest, SmsParseResponse, ManualMatchRequest,
    UnmatchedDepositResponse
)
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/sms", tags=["sms"])
logger = logging.getLogger(__name__)

# 7.2.1 POST /parse - SMS 메시지 파싱 및 처리 API (중요 기능!)
@router.post("/parse", response_model=SmsParseResponse)
async def parse_sms_message_endpoint(
    request: SmsParseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    SMS 메시지 파싱 및 처리 API (외부 시스템 연동용)
    - 금융 시스템에서 실시간 연동 가능
    - 자동 SMS 파싱 (금액+이름+시간 추출 포함)
    - 매칭 성공시 즉시 자동 충전 처리
    - 매칭 실패시 수동 매칭용 대기열에 저장
    """
    try:
        # SMS 메시지 기본 로깅 (보안용)
        logger.info(f"SMS 수신: {request.raw_message[:50]}...")
        
        # sms_controller의 process_sms_end_to_end 함수 호출
        # 이 함수는 SMS 파싱 + 매칭 + 충전 처리까지 종합적으로 담당하는 핵심 함수
        result = await process_sms_end_to_end(
            db=db,
            raw_message=request.raw_message
        )
        
        if not result["success"]:
            # SMS 파싱 실패시 즉시 SMS 로그 기록
            if result.get("error_code") == "PARSE_FAILED":
                logger.warning(f"SMS 파싱 실패: {request.raw_message}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
            elif result.get("error_code") == "DUPLICATE_SMS":
                # 중복 SMS는 무시하도록 처리 (금융 시스템 연동용 대응)
                logger.info(f"중복 SMS 무시 처리: {request.raw_message}")
                return SmsParseResponse(
                    success=True,
                    message="이미 처리된 SMS 메시지입니다 (중복 차단)",
                    flow="duplicate_blocked",
                    sms_log_id=None,
                    processing_status="duplicate"
                )
            else:
                logger.error(f"SMS 처리 실패: {result['message']}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result["message"]
                )
        
        # 성공한 경우 플로우별 응답
        flow = result.get("flow", "unknown")
        sms_data = result["data"]["sms_parse"]
        
        if flow == "matched_and_processed":
            # 매칭 성공 및 충전 완료된 경우
            process_data = result["data"]["process_result"]
            logger.info(f"SMS 자동 충전 완료 - user_id: {process_data.get('user_id')}, amount: {sms_data['parsed_amount']}")
            
            return SmsParseResponse(
                success=True,
                message="SMS 메시지 파싱 및 충전이 완료되었습니다",
                flow=flow,
                sms_log_id=sms_data["sms_log_id"],
                processing_status="auto_charged",
                matched_user_id=process_data.get("user_id"),
                charged_amount=process_data.get("processed_amount")
            )
            
        elif flow == "unmatched_stored":
            # 매칭 실패로 수동 매칭용 대기열에 저장
            unmatched_data = result["data"]["unmatched_result"]
            logger.info(f"SMS 수동 매칭 대기 - amount: {sms_data['parsed_amount']}, name: {sms_data['parsed_name']}")
            
            return SmsParseResponse(
                success=True,
                message="유효한 입금이지만 자동 매칭이 되지 않아 수동 매칭용으로 저장되었습니다",
                flow=flow,
                sms_log_id=sms_data["sms_log_id"],
                processing_status="unmatched",
                unmatched_deposit_id=unmatched_data.get("unmatched_deposit_id")
            )
        
        else:
            # 기타 처리된 상황
            logger.warning(f"기타 처리된 SMS 메시지 상황: {flow}")
            return SmsParseResponse(
                success=True,
                message="SMS 메시지가 처리되었습니다",
                flow=flow,
                sms_log_id=sms_data.get("sms_log_id"),
                processing_status="processed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SMS 파싱 엔드포인트 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SMS 처리 중 서버 오류가 발생했습니다"
        )

# 7.2.2 POST /manual-match - 수동 매칭 API
@router.post("/manual-match")
async def manual_match_deposit(
    request: ManualMatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    수동 매칭으로 입금 처리 API
    - 관리자가 미매칭 입금건을 수동으로 매칭
    - 매칭 후 즉시 충전으로 전환
    """
    try:
        # 관리자 권한 확인 (필요시 활성화)
        # if not current_user.get("is_admin"):
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
        
        # crud_sms의 match_deposit_manually 함수 호출
        result = await match_deposit_manually(db=db, match_request=request)
        
        logger.info(f"수동 매칭 완료 - user_id: {request.user_id}, amount: {request.confirmed_amount}")
        
        return {
            "success": True,
            "message": "수동 매칭이 완료되었습니다",
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"수동 매칭 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="수동 매칭 중 서버 오류가 발생했습니다"
        )

# 7.2.2.5 POST /simple-match - 간단 매칭 API (사용자용)
@router.post("/simple-match")
async def simple_match_deposit(
    request: dict,  # {"actual_deposit_name": str, "deposit_amount": int}
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    간단 매칭 API
    - 사용자가 입금자명 + 금액만으로 미매칭 입금을 찾아서 충전
    - 복잡한 후보 선택 없이 직접 매칭
    """
    try:
        actual_deposit_name = request.get("actual_deposit_name", "").strip()
        deposit_amount = request.get("deposit_amount", 0)
        
        if not actual_deposit_name:
            raise HTTPException(
                status_code=400,
                detail="입금자명을 입력해주세요"
            )
        
        if deposit_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="유효한 입금 금액을 입력해주세요"
            )
        
        # unmatched_deposits에서 이름+금액 정확히 일치하는 것 찾기
        from crud.crud_sms import find_unmatched_deposit_by_name_amount, process_simple_match
        
        unmatched_deposit = await find_unmatched_deposit_by_name_amount(
            db, actual_deposit_name, deposit_amount
        )
        
        if not unmatched_deposit:
            return {
                "success": False,
                "message": "일치하는 입금 내역을 찾을 수 없습니다. 입금자명과 금액을 다시 확인해주세요."
            }
        
        # 매칭 처리 (사용자에게 충전)
        result = await process_simple_match(
            db, unmatched_deposit, current_user.user_id
        )
        
        if result["success"]:
            logger.info(f"간단 매칭 완료 - user: {current_user.user_id}, amount: {deposit_amount}")
            
            return {
                "success": True,
                "message": "매칭이 완료되어 잔액에 반영되었습니다!",
                "charged_amount": deposit_amount
            }
        else:
            return {
                "success": False,
                "message": result["message"]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"간단 매칭 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="매칭 처리 중 서버 오류가 발생했습니다"
        )

# 7.2.3 GET /manual-match-candidates/{unmatched_deposit_id} - 수동 매칭 후보 조회
@router.get("/manual-match-candidates/{unmatched_deposit_id}")
async def get_manual_match_candidates_endpoint(
    unmatched_deposit_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    수동 매칭용 후보 사용자 조회 API
    - 입금자명과 유사한 사용자 조회 (필요시 포함 제외)
    - 관리자 매칭용 후보 목록 (필요시 포함되지만 현재는 제외됨)
    """
    try:
        # sms_controller의 get_manual_match_candidates 함수 호출
        result = await get_manual_match_candidates(
            db=db,
            unmatched_deposit_id=unmatched_deposit_id
        )
        
        if not result["success"]:
            if result.get("error_code") == "UNMATCHED_DEPOSIT_NOT_FOUND":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
        
        return result["data"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"수동 매칭 후보 조회 실패 - unmatched_deposit_id: {unmatched_deposit_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="수동 매칭 후보 조회 중 서버 오류가 발생했습니다"
        )

# 7.2.4 GET /logs - SMS 로그 조회 API
@router.get("/logs")
async def get_sms_logs_endpoint(
    status: Optional[str] = None,  # "received", "processed", "failed"
    page: int = 1,
    size: int = 10,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    SMS 로그 조회 API
    - 상태별 필터링 지원
    - 페이지네이션 지원
    - 관리자용 모니터링
    """
    try:
        # 관리자 권한 확인 (필요시 활성화)
        # if not current_user.get("is_admin"):
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
        
        # 페이지네이션 검증
        if page < 1 or size < 1 or size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 페이지네이션 파라미터입니다"
            )
        
        # 상태 필터 검증
        valid_statuses = ["received", "processed", "failed"]
        if status and status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status는 {valid_statuses} 중 하나여야 합니다"
            )
        
        skip = (page - 1) * size
        
        # crud_sms의 get_sms_logs 함수 호출
        sms_logs = await get_sms_logs(
            db=db,
            status=status,
            skip=skip,
            limit=size
        )
        
        return {
            "success": True,
            "data": {
                "sms_logs": [
                    {
                        "sms_log_id": log.sms_log_id,
                        "raw_message": log.raw_message[:100] + "..." if len(log.raw_message) > 100 else log.raw_message,
                        "parsed_amount": log.parsed_amount,
                        "parsed_name": log.parsed_name,
                        "parsed_time": log.parsed_time,
                        "processing_status": log.processing_status,
                        "created_at": log.created_at,
                        "updated_at": log.updated_at
                    } for log in sms_logs
                ],
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": len(sms_logs)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SMS 로그 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SMS 로그 조회 중 서버 오류가 발생했습니다"
        )

# 7.2.5 GET /unmatched-deposits - 미매칭 입금 조회 API
@router.get("/unmatched-deposits")
async def get_unmatched_deposits_endpoint(
    status: Optional[str] = None,  # "unmatched", "matched", "ignored"
    page: int = 1,
    size: int = 10,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    미매칭 입금 조회 API
    - 상태별 필터링 지원
    - 페이지네이션 지원
    - 수동 매칭용 관리
    """
    try:
        # 관리자 권한 확인 (필요시 활성화)
        # if not current_user.get("is_admin"):
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
        
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
                        "expires_at": deposit.expires_at
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
        logger.error(f"미매칭 입금 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="미매칭 입금 조회 중 서버 오류가 발생했습니다"
        )