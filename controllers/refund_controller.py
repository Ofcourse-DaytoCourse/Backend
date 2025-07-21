from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from crud.crud_payment import (
    get_refundable_amount, create_refund_request, process_refund,
    get_refundable_charge_histories, get_user_refund_requests
)
from crud.crud_rate_limit import check_rate_limit, record_action_if_allowed
from schemas.refund_schema import RefundRequestCreate
from schemas.rate_limit_schema import ActionType

# 6.3.1 calculate_refundable_amount 함수
async def calculate_refundable_amount(
    db: AsyncSession,
    user_id: str,
    charge_history_id: int
) -> Dict[str, Any]:
    """환불 가능 금액 계산 비즈니스 로직"""
    
    try:
        print(f"🔍 calculate_refundable_amount 시작 - user_id: {user_id}, charge_history_id: {charge_history_id}")
        # 환불 가능 금액 조회
        refundable_info = await get_refundable_amount(db, charge_history_id, user_id)
        
        return {
            "success": True,
            "data": {
                "charge_history_id": refundable_info["charge_history_id"],
                "original_amount": refundable_info["original_amount"],
                "refunded_amount": refundable_info["refunded_amount"],
                "refundable_amount": refundable_info["refundable_amount"],
                "is_refundable": refundable_info["is_refundable"],
                "refund_status": refundable_info["refund_status"],
                "has_pending_request": refundable_info["has_pending_request"],
                "pending_request_amount": refundable_info["pending_request_amount"],
                "can_request_refund": (
                    refundable_info["is_refundable"] and 
                    refundable_info["refundable_amount"] > 0 and
                    not refundable_info["has_pending_request"]
                )
            }
        }
        
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"환불 가능 금액 계산 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.3.2 create_refund_request 함수
async def create_refund_request(
    db: AsyncSession,
    user_id: str,
    refund_data: RefundRequestCreate
) -> Dict[str, Any]:
    """환불 요청 생성 비즈니스 로직"""
    
    try:
        print(f"🔍 환불 요청 시작 - user_id: {user_id}")
        print(f"🔍 환불 데이터: {refund_data}")
        
        # 환불 가능성 사전 확인
        print(f"🔍 환불 가능성 확인 시작")
        refundable_check = await calculate_refundable_amount(
            db, user_id, refund_data.charge_history_id
        )
        print(f"🔍 환불 가능성 확인 결과: {refundable_check}")
        
        if not refundable_check["success"]:
            return refundable_check
        
        refundable_info = refundable_check["data"]
        if not refundable_info["can_request_refund"]:
            return {
                "success": False,
                "message": "환불 요청할 수 없는 충전 내역입니다",
                "error_code": "REFUND_NOT_ALLOWED",
                "details": {
                    "is_refundable": refundable_info["is_refundable"],
                    "refundable_amount": refundable_info["refundable_amount"],
                    "has_pending_request": refundable_info["has_pending_request"]
                }
            }
        
        # 요청 금액 검증
        if refund_data.refund_amount > refundable_info["refundable_amount"]:
            return {
                "success": False,
                "message": f"환불 가능 금액을 초과했습니다. (최대: {refundable_info['refundable_amount']}원)",
                "error_code": "AMOUNT_EXCEEDED",
                "max_refundable_amount": refundable_info["refundable_amount"]
            }
        
        # 환불 요청 생성
        from crud.crud_payment import create_refund_request as crud_create_refund_request
        try:
            refund_request = await crud_create_refund_request(db, user_id, refund_data)
        except Exception as e:
            print(f"🔴 CRUD 환불 요청 생성 오류: {str(e)}")
            print(f"🔴 오류 타입: {type(e)}")
            import traceback
            print(f"🔴 스택 트레이스: {traceback.format_exc()}")
            raise e
        
        
        return {
            "success": True,
            "message": "환불 요청이 성공적으로 생성되었습니다",
            "data": {
                "refund_request_id": refund_request.refund_request_id,
                "user_id": refund_request.user_id,
                "charge_history_id": refund_request.charge_history_id,
                "refund_amount": refund_request.refund_amount,
                "bank_name": refund_request.bank_name,
                "account_number": refund_request.account_number,
                "account_holder": refund_request.account_holder,
                "contact": refund_request.contact,
                "reason": refund_request.reason,
                "status": refund_request.status,
                "created_at": refund_request.created_at,
                "estimated_processing_days": "3-5 영업일"
            }
        }
        
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"환불 요청 생성 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.3.3 process_refund_approval 함수
async def process_refund_approval(
    db: AsyncSession,
    refund_request_id: int,
    approved: bool,
    admin_user_id: str,
    admin_memo: Optional[str] = None
) -> Dict[str, Any]:
    """환불 승인 처리 비즈니스 로직"""
    
    try:
        # 환불 처리 (CRUD에서 트랜잭션 처리됨)
        refund_request = await process_refund(db, refund_request_id, approved, admin_memo)
        
        if approved:
            return {
                "success": True,
                "message": "환불이 승인되었습니다",
                "data": {
                    "refund_request_id": refund_request.refund_request_id,
                    "user_id": refund_request.user_id,
                    "refund_amount": refund_request.refund_amount,
                    "status": refund_request.status,
                    "processed_at": refund_request.processed_at,
                    "admin_memo": refund_request.admin_memo,
                    "admin_user_id": admin_user_id,
                    "next_steps": "계좌 이체 처리 중"
                }
            }
        else:
            return {
                "success": True,
                "message": "환불이 거절되었습니다",
                "data": {
                    "refund_request_id": refund_request.refund_request_id,
                    "user_id": refund_request.user_id,
                    "refund_amount": refund_request.refund_amount,
                    "status": refund_request.status,
                    "processed_at": refund_request.processed_at,
                    "admin_memo": refund_request.admin_memo,
                    "admin_user_id": admin_user_id,
                    "rejection_reason": admin_memo
                }
            }
            
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"환불 승인 처리 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.3.4 부분 환불 처리 구현
async def get_refundable_histories(
    db: AsyncSession,
    user_id: str
) -> Dict[str, Any]:
    """사용자의 환불 가능한 충전 내역 조회"""
    
    try:
        # 환불 가능한 충전 내역 조회
        charge_histories = await get_refundable_charge_histories(db, user_id)
        
        refundable_items = []
        total_refundable_amount = 0
        
        for charge_history in charge_histories:
            refundable_amount = charge_history.get_refundable_amount()
            if refundable_amount > 0:
                # 진행 중인 환불 요청 확인
                from crud.crud_payment import get_pending_refund_request
                pending_request = await get_pending_refund_request(
                    db, charge_history.charge_history_id
                )
                
                refundable_items.append({
                    "charge_history_id": charge_history.charge_history_id,
                    "original_amount": charge_history.amount,
                    "refunded_amount": charge_history.refunded_amount,
                    "refundable_amount": refundable_amount,
                    "source_type": charge_history.source_type,
                    "refund_status": charge_history.refund_status,
                    "created_at": charge_history.created_at,
                    "description": charge_history.description,
                    "has_pending_request": pending_request is not None,
                    "pending_request_amount": pending_request.refund_amount if pending_request else 0,
                    "can_request_more": pending_request is None and refundable_amount > 0
                })
                
                if pending_request is None:  # 진행 중인 요청이 없는 경우만 합계에 포함
                    total_refundable_amount += refundable_amount
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "total_refundable_amount": total_refundable_amount,
                "refundable_items_count": len(refundable_items),
                "refundable_items": refundable_items
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"환불 가능 내역 조회 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.3.5 환불 로직 테스트 - 환불 히스토리 조회
async def get_refund_history(
    db: AsyncSession,
    user_id: Optional[str],
    page: int = 1,
    size: int = 10,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """사용자 환불 내역 조회 (user_id가 None이면 모든 사용자)"""
    
    try:
        skip = (page - 1) * size
        
        # 환불 요청 목록 조회
        refund_requests = await get_user_refund_requests(db, user_id, skip, size)
        
        # 상태별 필터링
        if status_filter:
            refund_requests = [
                req for req in refund_requests 
                if req.status == status_filter
            ]
        
        # 상태별 통계
        all_requests = await get_user_refund_requests(db, user_id, 0, 1000)  # 전체 조회
        statistics = {
            "total_requests": len(all_requests),
            "pending_requests": len([r for r in all_requests if r.status == "pending"]),
            "approved_requests": len([r for r in all_requests if r.status == "approved"]),
            "rejected_requests": len([r for r in all_requests if r.status == "rejected"]),
            "completed_requests": len([r for r in all_requests if r.status == "completed"]),
            "total_requested_amount": sum(r.refund_amount for r in all_requests),
            "total_approved_amount": sum(
                r.refund_amount for r in all_requests 
                if r.status in ["approved", "completed"]
            )
        }
        
        refund_items = []
        for request in refund_requests:
            # 관련 충전 내역 정보
            from crud.crud_payment import get_charge_history
            print(f"🔍 charge_history 조회 시작 - charge_history_id: {request.charge_history_id}")
            charge_history = await get_charge_history(db, request.charge_history_id)
            print(f"🔍 charge_history 조회 결과: {charge_history}")
            
            print(f"🔍 refund_items.append 시작")
            print(f"🔍 request.refund_request_id: {request.refund_request_id}")
            print(f"🔍 request.charge_history_id: {request.charge_history_id}")
            print(f"🔍 request.refund_amount: {request.refund_amount}")
            print(f"🔍 request.created_at: {request.created_at}")
            print(f"🔍 request.created_at type: {type(request.created_at)}")
            
            print(f"🔍 datetime 연산 시작")
            if request.created_at:
                # timezone-naive인 경우 로컬 시간으로 간주하고 현재 시간과 비교
                if request.created_at.tzinfo is None:
                    # 로컬 시간으로 간주
                    days_calc = (datetime.now() - request.created_at).days
                else:
                    # timezone-aware인 경우 UTC로 변환하여 비교
                    days_calc = (datetime.now(timezone.utc) - request.created_at).days
            else:
                days_calc = 0
            print(f"🔍 datetime 연산 완료: {days_calc}")
            
            refund_items.append({
                "refund_request_id": request.refund_request_id,
                "charge_history_id": request.charge_history_id,
                "refund_amount": request.refund_amount,
                "bank_name": request.bank_name,
                "account_number": request.account_number,
                "account_holder": request.account_holder,
                "contact": request.contact,
                "reason": request.reason,
                "status": request.status,
                "created_at": request.created_at,
                "processed_at": request.processed_at,
                "admin_memo": request.admin_memo,
                "charge_info": {
                    "original_amount": charge_history.amount if charge_history else 0,
                    "source_type": charge_history.source_type if charge_history else None,
                    "charge_date": charge_history.created_at if charge_history else None
                },
                "days_since_request": days_calc
            })
            print(f"🔍 refund_items.append 완료")
        
        print(f"🔍 for 루프 완료, refund_items 개수: {len(refund_items)}")
        print(f"🔍 return 준비")
        return {
            "success": True,
            "data": {
                "refund_history": refund_items,
                "statistics": statistics,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total_items": len(refund_items),
                    "filtered_by_status": status_filter
                }
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"환불 내역 조회 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 관리자용 환불 관리 함수들
async def get_pending_refund_requests(
    db: AsyncSession,
    page: int = 1,
    size: int = 10
) -> Dict[str, Any]:
    """대기 중인 환불 요청 목록 조회 (관리자용)"""
    
    try:
        from crud.crud_payment import get_refund_request
        from sqlalchemy import select, and_
        from models.payment import RefundRequest
        
        skip = (page - 1) * size
        
        # 대기 중인 환불 요청 조회
        result = await db.execute(
            select(RefundRequest)
            .where(RefundRequest.status == "pending")
            .order_by(RefundRequest.created_at.asc())
            .offset(skip)
            .limit(size)
        )
        
        pending_requests = result.scalars().all()
        
        # 총 개수 조회
        from sqlalchemy.sql import func
        count_result = await db.execute(
            select(func.count(RefundRequest.refund_request_id))
            .where(RefundRequest.status == "pending")
        )
        total_pending = count_result.scalar()
        
        requests_data = []
        for request in pending_requests:
            # 관련 충전 내역 정보
            from crud.crud_payment import get_charge_history
            charge_history = await get_charge_history(db, request.charge_history_id)
            
            requests_data.append({
                "refund_request_id": request.refund_request_id,
                "user_id": request.user_id,
                "charge_history_id": request.charge_history_id,
                "refund_amount": request.refund_amount,
                "bank_name": request.bank_name,
                "account_number": request.account_number,
                "account_holder": request.account_holder,
                "contact": request.contact,
                "reason": request.reason,
                "created_at": request.created_at,
                "days_waiting": (datetime.now(timezone.utc) - request.created_at).days,
                "charge_info": {
                    "original_amount": charge_history.amount if charge_history else 0,
                    "source_type": charge_history.source_type if charge_history else None,
                    "refundable_amount": charge_history.get_refundable_amount() if charge_history else 0
                }
            })
        
        return {
            "success": True,
            "data": {
                "pending_requests": requests_data,
                "total_pending": total_pending,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total_pages": (total_pending + size - 1) // size
                }
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"대기 중인 환불 요청 조회 중 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

async def validate_refund_request_data(refund_data: RefundRequestCreate) -> Dict[str, Any]:
    """환불 요청 데이터 검증"""
    
    errors = []
    
    # 금액 검증
    if refund_data.refund_amount <= 0:
        errors.append("환불 금액은 0보다 커야 합니다")
    elif refund_data.refund_amount < 1000:
        errors.append("최소 환불 금액은 1,000원입니다")
    
    # 은행 정보 검증
    if not refund_data.bank_name or len(refund_data.bank_name.strip()) == 0:
        errors.append("은행명을 입력해주세요")
    
    if not refund_data.account_number or len(refund_data.account_number.strip()) == 0:
        errors.append("계좌번호를 입력해주세요")
    
    if not refund_data.account_holder or len(refund_data.account_holder.strip()) == 0:
        errors.append("계좌 소유자명을 입력해주세요")
    
    # 연락처 검증
    if not refund_data.contact or len(refund_data.contact.strip()) == 0:
        errors.append("연락처를 입력해주세요")
    
    # 사유 검증
    if not refund_data.reason or len(refund_data.reason.strip()) < 10:
        errors.append("환불 사유는 최소 10자 이상 입력해주세요")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }