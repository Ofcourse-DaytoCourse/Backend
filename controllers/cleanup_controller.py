from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio

from crud.crud_rate_limit import (
    cleanup_expired_logs, cleanup_old_logs_by_action, scheduled_cleanup
)
from crud.crud_deposit import expire_old_deposits
from crud.crud_sms import cleanup_expired_unmatched_deposits
from schemas.rate_limit_schema import ActionType

# 6.4.1 cleanup_rate_limit_logs 함수
async def cleanup_rate_limit_logs(
    db: AsyncSession,
    force_cleanup: bool = False
) -> Dict[str, Any]:
    """레이트 리미팅 로그 정리 비즈니스 로직"""
    
    try:
        cleanup_results = {}
        
        # 만료된 로그 삭제 (24시간 후)
        expired_count = await cleanup_expired_logs(db)
        cleanup_results["expired_logs_deleted"] = expired_count
        
        if force_cleanup:
            # 강제 정리 시 모든 액션 타입의 오래된 로그 삭제 (48시간 이상)
            for action_type in ActionType:
                old_count = await cleanup_old_logs_by_action(db, action_type, 48)
                cleanup_results[f"{action_type.value}_old_logs_deleted"] = old_count
        
        # 정리 완료 시간 기록
        cleanup_results["cleanup_completed_at"] = datetime.now(timezone.utc)
        cleanup_results["total_deleted"] = sum(
            v for k, v in cleanup_results.items() 
            if k.endswith("_deleted") and isinstance(v, int)
        )
        
        return {
            "success": True,
            "message": f"레이트 리미팅 로그 정리가 완료되었습니다. (총 {cleanup_results['total_deleted']}개 삭제)",
            "data": cleanup_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"레이트 리미팅 로그 정리 중 오류가 발생했습니다: {str(e)}",
            "error_code": "CLEANUP_ERROR"
        }

# 6.4.2 cleanup_expired_deposits 함수
async def cleanup_expired_deposits(db: AsyncSession) -> Dict[str, Any]:
    """만료된 입금 요청 정리 비즈니스 로직"""
    
    try:
        # 만료된 입금 요청들을 일괄 만료 처리
        expired_count = await expire_old_deposits(db)
        
        return {
            "success": True,
            "message": f"만료된 입금 요청 정리가 완료되었습니다. ({expired_count}개 처리)",
            "data": {
                "expired_deposits_count": expired_count,
                "cleanup_completed_at": datetime.now(timezone.utc)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"만료된 입금 요청 정리 중 오류가 발생했습니다: {str(e)}",
            "error_code": "CLEANUP_ERROR"
        }

# 6.4.3 cleanup_old_unmatched_deposits 함수
async def cleanup_old_unmatched_deposits(db: AsyncSession) -> Dict[str, Any]:
    """오래된 미매칭 입금 정리 비즈니스 로직"""
    
    try:
        # 6개월 후 만료된 미매칭 입금 정리
        cleaned_count = await cleanup_expired_unmatched_deposits(db)
        
        return {
            "success": True,
            "message": f"만료된 미매칭 입금 정리가 완료되었습니다. ({cleaned_count}개 처리)",
            "data": {
                "cleaned_unmatched_deposits": cleaned_count,
                "cleanup_completed_at": datetime.now(timezone.utc)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"미매칭 입금 정리 중 오류가 발생했습니다: {str(e)}",
            "error_code": "CLEANUP_ERROR"
        }

# 6.4.4 자동 정리 스케줄러 구현
async def run_scheduled_cleanup(
    db: AsyncSession,
    cleanup_type: str = "all"
) -> Dict[str, Any]:
    """정기 자동 정리 실행"""
    
    try:
        cleanup_results = {
            "started_at": datetime.now(timezone.utc),
            "cleanup_type": cleanup_type,
            "results": {}
        }
        
        if cleanup_type == "all" or cleanup_type == "rate_limit":
            # 레이트 리미팅 로그 정리
            rate_limit_result = await cleanup_rate_limit_logs(db)
            cleanup_results["results"]["rate_limit"] = rate_limit_result
        
        if cleanup_type == "all" or cleanup_type == "deposits":
            # 만료된 입금 요청 정리
            deposits_result = await cleanup_expired_deposits(db)
            cleanup_results["results"]["deposits"] = deposits_result
        
        if cleanup_type == "all" or cleanup_type == "unmatched":
            # 미매칭 입금 정리
            unmatched_result = await cleanup_old_unmatched_deposits(db)
            cleanup_results["results"]["unmatched"] = unmatched_result
        
        cleanup_results["completed_at"] = datetime.now(timezone.utc)
        cleanup_results["duration_seconds"] = (
            cleanup_results["completed_at"] - cleanup_results["started_at"]
        ).total_seconds()
        
        # 전체 성공 여부 확인
        all_success = all(
            result.get("success", False) 
            for result in cleanup_results["results"].values()
        )
        
        return {
            "success": all_success,
            "message": "정기 정리 작업이 완료되었습니다" if all_success else "일부 정리 작업에서 오류가 발생했습니다",
            "data": cleanup_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"정기 정리 작업 중 오류가 발생했습니다: {str(e)}",
            "error_code": "SCHEDULER_ERROR"
        }

# 병렬 정리 실행
async def run_parallel_cleanup(db: AsyncSession) -> Dict[str, Any]:
    """병렬로 모든 정리 작업 실행"""
    
    try:
        # 모든 정리 작업을 병렬로 실행
        tasks = [
            cleanup_rate_limit_logs(db),
            cleanup_expired_deposits(db),
            cleanup_old_unmatched_deposits(db)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        cleanup_summary = {
            "started_at": datetime.now(timezone.utc),
            "rate_limit_cleanup": results[0] if not isinstance(results[0], Exception) else {"success": False, "error": str(results[0])},
            "deposits_cleanup": results[1] if not isinstance(results[1], Exception) else {"success": False, "error": str(results[1])},
            "unmatched_cleanup": results[2] if not isinstance(results[2], Exception) else {"success": False, "error": str(results[2])},
            "completed_at": datetime.now(timezone.utc)
        }
        
        # 성공한 작업 수 계산
        successful_tasks = sum(
            1 for result in results 
            if not isinstance(result, Exception) and result.get("success", False)
        )
        
        return {
            "success": successful_tasks == len(tasks),
            "message": f"병렬 정리 완료: {successful_tasks}/{len(tasks)} 작업 성공",
            "data": cleanup_summary
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"병렬 정리 작업 중 오류가 발생했습니다: {str(e)}",
            "error_code": "PARALLEL_CLEANUP_ERROR"
        }

# 정리 작업 상태 조회
async def get_cleanup_status(db: AsyncSession) -> Dict[str, Any]:
    """정리 작업 필요성 및 상태 조회"""
    
    try:
        from sqlalchemy import select, func, and_
        from models.rate_limit import RateLimitLog
        from models.deposit import DepositRequest
        from models.sms import UnmatchedDeposit
        from datetime import timedelta
        
        status = {
            "checked_at": datetime.now(timezone.utc),
            "cleanup_needed": {},
            "statistics": {}
        }
        
        # 레이트 리미팅 로그 상태
        expired_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        old_threshold = datetime.now(timezone.utc) - timedelta(hours=48)
        
        # 만료된 레이트 리미팅 로그 수
        expired_rate_logs = await db.execute(
            select(func.count(RateLimitLog.rate_limit_log_id))
            .where(RateLimitLog.expires_at <= datetime.now(timezone.utc))
        )
        expired_count = expired_rate_logs.scalar()
        
        # 오래된 레이트 리미팅 로그 수
        old_rate_logs = await db.execute(
            select(func.count(RateLimitLog.rate_limit_log_id))
            .where(RateLimitLog.created_at <= old_threshold)
        )
        old_count = old_rate_logs.scalar()
        
        status["cleanup_needed"]["rate_limit_logs"] = expired_count > 0 or old_count > 100
        status["statistics"]["expired_rate_limit_logs"] = expired_count
        status["statistics"]["old_rate_limit_logs"] = old_count
        
        # 만료된 입금 요청 수
        expired_deposits = await db.execute(
            select(func.count(DepositRequest.deposit_request_id))
            .where(
                and_(
                    DepositRequest.status == "pending",
                    DepositRequest.expires_at <= datetime.now(timezone.utc)
                )
            )
        )
        expired_deposits_count = expired_deposits.scalar()
        
        status["cleanup_needed"]["expired_deposits"] = expired_deposits_count > 0
        status["statistics"]["expired_deposits"] = expired_deposits_count
        
        # 만료된 미매칭 입금 수
        expired_unmatched = await db.execute(
            select(func.count(UnmatchedDeposit.unmatched_deposit_id))
            .where(
                and_(
                    UnmatchedDeposit.status == "unmatched",
                    UnmatchedDeposit.expires_at <= datetime.now(timezone.utc)
                )
            )
        )
        expired_unmatched_count = expired_unmatched.scalar()
        
        status["cleanup_needed"]["unmatched_deposits"] = expired_unmatched_count > 0
        status["statistics"]["expired_unmatched_deposits"] = expired_unmatched_count
        
        # 전체 정리 필요 여부
        status["cleanup_needed"]["any"] = any(status["cleanup_needed"].values())
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"정리 상태 조회 중 오류가 발생했습니다: {str(e)}",
            "error_code": "STATUS_CHECK_ERROR"
        }

# 선택적 정리 실행
async def cleanup_by_type(
    db: AsyncSession,
    cleanup_types: list[str]
) -> Dict[str, Any]:
    """지정된 타입의 정리 작업만 실행"""
    
    try:
        results = {}
        
        for cleanup_type in cleanup_types:
            if cleanup_type == "rate_limit":
                results["rate_limit"] = await cleanup_rate_limit_logs(db)
            elif cleanup_type == "deposits":
                results["deposits"] = await cleanup_expired_deposits(db)
            elif cleanup_type == "unmatched":
                results["unmatched"] = await cleanup_old_unmatched_deposits(db)
            else:
                results[cleanup_type] = {
                    "success": False,
                    "message": f"지원하지 않는 정리 타입입니다: {cleanup_type}"
                }
        
        successful_count = sum(1 for result in results.values() if result.get("success", False))
        
        return {
            "success": successful_count == len(cleanup_types),
            "message": f"선택적 정리 완료: {successful_count}/{len(cleanup_types)} 작업 성공",
            "data": {
                "requested_types": cleanup_types,
                "results": results,
                "completed_at": datetime.now(timezone.utc)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"선택적 정리 작업 중 오류가 발생했습니다: {str(e)}",
            "error_code": "SELECTIVE_CLEANUP_ERROR"
        }