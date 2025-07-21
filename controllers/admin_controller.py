# -*- coding: utf-8 -*-
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Dict, Any
from datetime import datetime, timezone

from models.user import User
from models.payment import ChargeHistory, UserBalance
from crud.crud_payment import create_charge_history, update_user_balance
from schemas.admin_schema import ManualChargeRequest, ManualChargeResult, ManualChargeTargetType
from schemas.payment_schema import ChargeHistoryCreate, SourceType

logger = logging.getLogger(__name__)

async def process_manual_charge(
    db: AsyncSession,
    request: ManualChargeRequest,
    admin_user_id: str
) -> Dict[str, Any]:
    """
    관리자 수동 충전 처리
    """
    try:
        # 대상 사용자 조회
        target_users = await get_target_users(db, request)
        
        if not target_users:
            return {
                "success": False,
                "message": "충전 대상 사용자를 찾을 수 없습니다",
                "error_code": "NO_TARGET_USERS"
            }
        
        results = []
        success_count = 0
        failed_count = 0
        total_amount = 0
        
        # 각 사용자에 대해 충전 처리
        for user in target_users:
            try:
                # 충전 이력 생성
                charge_data = ChargeHistoryCreate(
                    user_id=user.user_id,
                    amount=request.amount,
                    source_type=SourceType.ADMIN,
                    deposit_request_id=None,
                    description=f"관리자 수동 충전 - {request.description or '이벤트 충전'}",
                    is_refundable=request.is_refundable
                )
                
                charge_history = await create_charge_history(
                    db=db,
                    charge_data=charge_data
                )
                
                # 사용자 잔액 업데이트
                await update_user_balance(
                    db=db,
                    user_id=user.user_id,
                    amount=request.amount,
                    is_add=True,  # 충전이므로 True
                    is_refundable=request.is_refundable
                )
                
                balance_result = {"success": True}
                
                if balance_result["success"]:
                    results.append(ManualChargeResult(
                        user_id=user.user_id,
                        nickname=user.nickname,
                        amount=request.amount,
                        is_refundable=request.is_refundable,
                        charge_history_id=charge_history.charge_history_id,
                        success=True
                    ))
                    success_count += 1
                    total_amount += request.amount
                    
                    logger.info(f"수동 충전 성공 - user: {user.nickname}, amount: {request.amount}, admin: {admin_user_id}")
                else:
                    results.append(ManualChargeResult(
                        user_id=user.user_id,
                        nickname=user.nickname,
                        amount=request.amount,
                        is_refundable=request.is_refundable,
                        charge_history_id=0,
                        success=False,
                        error_message=balance_result.get("message", "잔액 업데이트 실패")
                    ))
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"사용자 {user.nickname} 충전 실패: {str(e)}")
                results.append(ManualChargeResult(
                    user_id=user.user_id,
                    nickname=user.nickname,
                    amount=request.amount,
                    is_refundable=request.is_refundable,
                    charge_history_id=0,
                    success=False,
                    error_message=f"충전 처리 실패: {str(e)}"
                ))
                failed_count += 1
        
        await db.commit()
        
        return {
            "success": True,
            "data": {
                "total_users": len(target_users),
                "success_count": success_count,
                "failed_count": failed_count,
                "total_amount": total_amount,
                "results": results
            }
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"수동 충전 처리 실패: {str(e)}")
        return {
            "success": False,
            "message": f"수동 충전 처리 중 오류가 발생했습니다: {str(e)}",
            "error_code": "MANUAL_CHARGE_ERROR"
        }

async def get_target_users(
    db: AsyncSession,
    request: ManualChargeRequest
) -> List[User]:
    """
    충전 대상 사용자 조회
    """
    try:
        if request.target_type == ManualChargeTargetType.ALL_USERS:
            # 전체 사용자 조회 (활성 사용자만)
            result = await db.execute(
                select(User).where(
                    and_(
                        User.user_status.in_(["active", "verified"]),
                        User.nickname.isnot(None)
                    )
                ).order_by(User.created_at.desc())
            )
            return result.scalars().all()
            
        elif request.target_type == ManualChargeTargetType.SINGLE_USER:
            # 특정 사용자 조회
            result = await db.execute(
                select(User).where(
                    and_(
                        User.nickname == request.nickname,
                        User.user_status.in_(["active", "verified"])
                    )
                )
            )
            user = result.scalar_one_or_none()
            return [user] if user else []
        
        return []
        
    except Exception as e:
        logger.error(f"대상 사용자 조회 실패: {str(e)}")
        return []

async def get_user_list_for_admin(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    search_nickname: str = None
) -> Dict[str, Any]:
    """
    관리자용 사용자 목록 조회 (검색 기능 포함)
    """
    try:
        # 기본 쿼리
        query = select(User).where(
            and_(
                User.user_status.in_(["active", "verified"]),
                User.nickname.isnot(None)
            )
        )
        
        # 닉네임 검색
        if search_nickname and search_nickname.strip():
            query = query.where(User.nickname.ilike(f"%{search_nickname.strip()}%"))
        
        # 페이지네이션
        skip = (page - 1) * size
        query = query.order_by(User.created_at.desc()).offset(skip).limit(size)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        return {
            "success": True,
            "data": {
                "users": [
                    {
                        "user_id": user.user_id,
                        "nickname": user.nickname,
                        "email": user.email,
                        "user_status": user.user_status,
                        "created_at": user.created_at
                    } for user in users
                ],
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": len(users)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {str(e)}")
        return {
            "success": False,
            "message": f"사용자 목록 조회 중 오류가 발생했습니다: {str(e)}",
            "error_code": "USER_LIST_ERROR"
        }