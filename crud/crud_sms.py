from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy import and_, or_, update as sqlalchemy_update, desc
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import re
import json
from models.sms import SmsLog, UnmatchedDeposit, BalanceChangeLog
from models.deposit import DepositRequest
from models.payment import ChargeHistory, UserBalance
from models.user import User
from schemas.sms_schema import SmsLogCreate, SmsLogUpdate, SmsParsedData, ManualMatchRequest

# 4.3.1 create_sms_log 함수
async def create_sms_log(
    db: AsyncSession,
    sms_data: SmsLogCreate
) -> SmsLog:
    """SMS 로그 생성"""
    
    # 중복 SMS 검사 (금액+이름+시간 기준)
    if sms_data.parsed_amount and sms_data.parsed_name and sms_data.parsed_time:
        existing_sms = await check_duplicate_sms(
            db, sms_data.parsed_amount, sms_data.parsed_name, sms_data.parsed_time
        )
        if existing_sms:
            raise ValueError("이미 처리된 SMS입니다")
    
    sms_log = SmsLog(
        raw_message=sms_data.raw_message,
        parsed_data=sms_data.parsed_data,
        parsed_amount=sms_data.parsed_amount,
        parsed_name=sms_data.parsed_name,
        parsed_time=sms_data.parsed_time,
        processing_status=sms_data.processing_status.value,
        error_message=sms_data.error_message
    )
    
    db.add(sms_log)
    await db.commit()
    await db.refresh(sms_log)
    
    return sms_log

async def check_duplicate_sms(
    db: AsyncSession,
    amount: int,
    name: str,
    time: datetime
) -> Optional[SmsLog]:
    """중복 SMS 확인 (시간+금액+입금자명 3개 일치)"""
    result = await db.execute(
        select(SmsLog).where(
            and_(
                SmsLog.parsed_amount == amount,
                SmsLog.parsed_name == name,
                SmsLog.parsed_time == time
            )
        )
    )
    return result.scalar_one_or_none()

# 4.3.2 create_unmatched_deposit 함수
async def create_unmatched_deposit(
    db: AsyncSession,
    sms_log: SmsLog
) -> UnmatchedDeposit:
    """미매칭 입금 생성"""
    unmatched_deposit = UnmatchedDeposit(
        raw_message=sms_log.raw_message,
        parsed_amount=sms_log.parsed_amount,
        parsed_name=sms_log.parsed_name,
        parsed_time=sms_log.parsed_time
    )
    
    db.add(unmatched_deposit)
    await db.commit()
    await db.refresh(unmatched_deposit)
    
    return unmatched_deposit

# 4.3.3 create_balance_change_log 함수
async def create_balance_change_log(
    db: AsyncSession,
    user_id: str,
    change_type: str,
    amount: int,
    balance_before: int,
    balance_after: int,
    reference_table: Optional[str] = None,
    reference_id: Optional[int] = None,
    description: Optional[str] = None
) -> BalanceChangeLog:
    """잔액 변경 로그 생성"""
    balance_log = BalanceChangeLog(
        user_id=user_id,
        change_type=change_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reference_table=reference_table,
        reference_id=reference_id,
        description=description
    )
    
    db.add(balance_log)
    await db.commit()
    await db.refresh(balance_log)
    
    return balance_log

# 4.3.4 get_unmatched_deposits 함수
async def get_unmatched_deposits(
    db: AsyncSession,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
) -> List[UnmatchedDeposit]:
    """미매칭 입금 목록 조회"""
    query = select(UnmatchedDeposit)
    
    if status:
        query = query.where(UnmatchedDeposit.status == status)
    
    query = query.order_by(UnmatchedDeposit.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def get_unmatched_deposit(
    db: AsyncSession,
    unmatched_deposit_id: int
) -> Optional[UnmatchedDeposit]:
    """미매칭 입금 조회"""
    result = await db.execute(
        select(UnmatchedDeposit).where(
            UnmatchedDeposit.unmatched_deposit_id == unmatched_deposit_id
        )
    )
    return result.scalar_one_or_none()

# 4.3.5 match_deposit_manually 함수
async def match_deposit_manually(
    db: AsyncSession,
    match_request: ManualMatchRequest
) -> Dict[str, Any]:
    """수동 매칭 처리"""
    
    # 미매칭 입금 조회
    unmatched_deposit = await get_unmatched_deposit(db, match_request.unmatched_deposit_id)
    if not unmatched_deposit:
        raise ValueError("미매칭 입금이 존재하지 않습니다")
    
    if unmatched_deposit.status != "unmatched":
        raise ValueError("이미 처리된 입금입니다")
    
    # 사용자 존재 확인
    user_result = await db.execute(select(User).where(User.user_id == match_request.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError("사용자가 존재하지 않습니다")
    
    try:
        # 충전 이력 생성
        from crud.crud_payment import create_charge_history, get_or_create_user_balance
        from schemas.payment_schema import ChargeHistoryCreate, SourceType
        
        charge_data = ChargeHistoryCreate(
            user_id=match_request.user_id,
            amount=match_request.confirmed_amount,
            source_type=SourceType.DEPOSIT,
            description=f"수동 매칭: {unmatched_deposit.parsed_name}"
        )
        
        charge_history = await create_charge_history(db, charge_data)
        
        # 사용자 잔액 업데이트
        user_balance = await get_or_create_user_balance(db, match_request.user_id)
        balance_before = user_balance.total_balance
        
        user_balance.add_balance(match_request.confirmed_amount, True)
        user_balance.updated_at = datetime.now(timezone.utc)
        
        # 잔액 변경 로그 생성
        await create_balance_change_log(
            db=db,
            user_id=match_request.user_id,
            change_type="charge",
            amount=match_request.confirmed_amount,
            balance_before=balance_before,
            balance_after=user_balance.total_balance,
            reference_table="charge_histories",
            reference_id=charge_history.charge_history_id,
            description="수동 매칭에 의한 충전"
        )
        
        # 미매칭 입금 상태 업데이트
        unmatched_deposit.status = "matched"
        unmatched_deposit.matched_user_id = match_request.user_id
        unmatched_deposit.matched_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "수동 매칭이 완료되었습니다",
            "charge_history_id": charge_history.charge_history_id,
            "charged_amount": match_request.confirmed_amount,
            "new_balance": user_balance.total_balance
        }
        
    except Exception as e:
        await db.rollback()
        raise e

# 4.3.6 CRUD 기타 관련 - SMS 파싱 및 매칭 함수들
async def parse_bank_sms(raw_message: str) -> SmsParsedData:
    """은행 SMS 파싱"""
    
    # 주요은행 SMS 패턴 (4대 은행)
    patterns = {
        "kb": {
            "amount": r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)원",
            "name": r"입금\s*:\s*([^\s]+)",
            "balance": r"잔액\s*:\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)원"
        },
        "nh": {
            "amount": r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)원",
            "name": r"([^\s]+)님",
            "balance": r"잔액\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)원"
        }
    }
    
    parsed_data = SmsParsedData(raw_text=raw_message)
    
    # 금액 추출
    for bank, pattern_set in patterns.items():
        amount_match = re.search(pattern_set["amount"], raw_message)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            try:
                parsed_data.amount = int(float(amount_str))
            except ValueError:
                continue
            break
    
    # 입금자명 추출
    for bank, pattern_set in patterns.items():
        name_match = re.search(pattern_set["name"], raw_message)
        if name_match:
            parsed_data.deposit_name = name_match.group(1).strip()
            break
    
    # 잔액 추출
    for bank, pattern_set in patterns.items():
        if "balance" in pattern_set:
            balance_match = re.search(pattern_set["balance"], raw_message)
            if balance_match:
                balance_str = balance_match.group(1).replace(',', '')
                try:
                    parsed_data.balance = int(float(balance_str))
                except ValueError:
                    continue
                break
    
    # 거래 시간 (현재 시각으로 임시 설정)
    parsed_data.transaction_time = datetime.now(timezone.utc)
    
    return parsed_data

async def process_sms_message(
    db: AsyncSession,
    raw_message: str
) -> Dict[str, Any]:
    """SMS 메시지 수신 및 처리 로직"""
    
    try:
        # 1. SMS 파싱
        parsed_data = await parse_bank_sms(raw_message)
        
        if not parsed_data.amount or not parsed_data.deposit_name:
            # 파싱 실패
            sms_data = SmsLogCreate(
                raw_message=raw_message,
                processing_status="failed",
                error_message="SMS 파싱 실패"
            )
            sms_log = await create_sms_log(db, sms_data)
            
            return {
                "success": False,
                "message": "SMS 파싱에 실패했습니다",
                "sms_log_id": sms_log.sms_log_id
            }
        
        # 2. SMS 로그 생성
        sms_data = SmsLogCreate(
            raw_message=raw_message,
            parsed_data=parsed_data.dict(),
            parsed_amount=parsed_data.amount,
            parsed_name=parsed_data.deposit_name,
            parsed_time=parsed_data.transaction_time,
            processing_status="received"
        )
        
        sms_log = await create_sms_log(db, sms_data)
        
        # 3. 입금 요청 매칭
        deposit_request = await find_matching_deposit_request(
            db, parsed_data.deposit_name, parsed_data.amount
        )
        
        if deposit_request:
            # 매칭 성공 - 자동 처리
            result = await process_matched_deposit(db, sms_log, deposit_request)
            return result
        else:
            # 매칭 실패 - 미매칭 테이블에 저장
            unmatched_deposit = await create_unmatched_deposit(db, sms_log)
            
            # SMS 로그 상태 업데이트
            await update_sms_log_status(db, sms_log.sms_log_id, "processed")
            
            return {
                "success": True,
                "message": "입금 확인되었으나 매칭할 요청이 존재하지 않습니다",
                "sms_log_id": sms_log.sms_log_id,
                "unmatched_deposit_id": unmatched_deposit.unmatched_deposit_id,
                "requires_manual_matching": True
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"SMS 처리 중 오류 발생: {str(e)}"
        }

async def find_matching_deposit_request(
    db: AsyncSession,
    deposit_name: str,
    amount: int,
    time_range_hours: int = 24
) -> Optional[DepositRequest]:
    """매칭할 입금 요청 찾기 (입금자명만 일치하면 OK)"""
    
    result = await db.execute(
        select(DepositRequest).where(
            and_(
                DepositRequest.deposit_name == deposit_name,
                # DepositRequest.amount == amount,  # 금액 조건 제거
                DepositRequest.status == "pending"
                # 시간 조건 제거 - 입금 확인되면 테이블에서 삭제되므로 불필요
            )
        )
    )
    return result.scalar_one_or_none()

async def process_matched_deposit(
    db: AsyncSession,
    sms_log: SmsLog,
    deposit_request: DepositRequest
) -> Dict[str, Any]:
    """매칭된 입금 처리"""
    
    try:
        from crud.crud_payment import create_charge_history, get_or_create_user_balance
        from crud.crud_deposit import mark_deposit_completed
        from schemas.payment_schema import ChargeHistoryCreate, SourceType
        
        # 1. 입금 요청 완료 처리
        await mark_deposit_completed(db, deposit_request.deposit_request_id)
        
        # 2. 충전 이력 생성 (실제 입금 금액으로)
        actual_amount = sms_log.parsed_amount  # 실제 입금한 금액 사용
        charge_data = ChargeHistoryCreate(
            user_id=deposit_request.user_id,
            deposit_request_id=deposit_request.deposit_request_id,
            amount=actual_amount,
            source_type=SourceType.DEPOSIT,
            description=f"입금 완료: {deposit_request.deposit_name} ({actual_amount}원)"
        )
        
        charge_history = await create_charge_history(db, charge_data)
        
        # 3. 사용자 잔액 업데이트 (실제 입금 금액으로)
        user_balance = await get_or_create_user_balance(db, deposit_request.user_id)
        balance_before = user_balance.total_balance
        
        user_balance.add_balance(actual_amount, True)
        user_balance.updated_at = datetime.now(timezone.utc)
        
        # 4. 잔액 변경 로그 생성 (실제 입금 금액으로)
        await create_balance_change_log(
            db=db,
            user_id=deposit_request.user_id,
            change_type="charge",
            amount=actual_amount,
            balance_before=balance_before,
            balance_after=user_balance.total_balance,
            reference_table="charge_histories",
            reference_id=charge_history.charge_history_id,
            description="입금 완료에 의한 충전"
        )
        
        # 5. SMS 로그 업데이트
        sms_log.matched_deposit_id = deposit_request.deposit_request_id
        sms_log.processing_status = "processed"
        sms_log.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "입금이 성공적으로 처리되었습니다",
            "sms_log_id": sms_log.sms_log_id,
            "matched_deposit_id": deposit_request.deposit_request_id,
            "charge_history_id": charge_history.charge_history_id,
            "charged_amount": actual_amount,
            "new_balance": user_balance.total_balance
        }
        
    except Exception as e:
        await db.rollback()
        raise e

async def update_sms_log_status(
    db: AsyncSession,
    sms_log_id: int,
    status: str,
    error_message: Optional[str] = None
) -> Optional[SmsLog]:
    """SMS 로그 상태 업데이트"""
    update_data = SmsLogUpdate(
        processing_status=status,
        error_message=error_message
    )
    
    update_dict = update_data.dict(exclude_unset=True)
    update_dict['updated_at'] = datetime.now(timezone.utc)
    
    await db.execute(
        sqlalchemy_update(SmsLog)
        .where(SmsLog.sms_log_id == sms_log_id)
        .values(**update_dict)
    )
    await db.commit()
    
    result = await db.execute(select(SmsLog).where(SmsLog.sms_log_id == sms_log_id))
    return result.scalar_one_or_none()

async def get_sms_logs(
    db: AsyncSession,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
) -> List[SmsLog]:
    """SMS 로그 목록 조회"""
    query = select(SmsLog)
    
    if status:
        query = query.where(SmsLog.processing_status == status)
    
    query = query.order_by(SmsLog.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def get_balance_change_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    change_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
) -> List[BalanceChangeLog]:
    """잔액 변경 로그 조회"""
    query = select(BalanceChangeLog)
    
    conditions = []
    if user_id:
        conditions.append(BalanceChangeLog.user_id == user_id)
    if change_type:
        conditions.append(BalanceChangeLog.change_type == change_type)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(BalanceChangeLog.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def cleanup_expired_unmatched_deposits(db: AsyncSession) -> int:
    """만료된 미매칭 입금 정리 (6개월 후)"""
    current_time = datetime.now(timezone.utc)
    
    result = await db.execute(
        sqlalchemy_update(UnmatchedDeposit)
        .where(
            and_(
                UnmatchedDeposit.status == "unmatched",
                UnmatchedDeposit.expires_at <= current_time
            )
        )
        .values(status="ignored")
    )
    await db.commit()
    
    return result.rowcount

# 간단 매칭용 함수들
async def find_unmatched_deposit_by_name_amount(
    db: AsyncSession,
    deposit_name: str,
    amount: int
) -> Optional[UnmatchedDeposit]:
    """이름+금액으로 미매칭 입금 찾기"""
    result = await db.execute(
        select(UnmatchedDeposit).where(
            and_(
                UnmatchedDeposit.parsed_name == deposit_name,
                UnmatchedDeposit.parsed_amount == amount,
                UnmatchedDeposit.status == "unmatched"
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()

async def process_simple_match(
    db: AsyncSession,
    unmatched_deposit: UnmatchedDeposit,
    user_id: str
) -> Dict[str, Any]:
    """간단 매칭 처리 - 사용자에게 직접 충전"""
    try:
        from crud.crud_payment import create_charge_history, update_user_balance
        from schemas.payment_schema import ChargeHistoryCreate, SourceType
        
        # 1. 충전 내역 생성
        charge_data = ChargeHistoryCreate(
            user_id=user_id,
            deposit_request_id=None,  # 입금요청 없이 직접 충전
            amount=unmatched_deposit.parsed_amount,
            source_type=SourceType.ADMIN,  # 수동 매칭이므로 admin으로 처리
            description=f"입금자명 매칭: {unmatched_deposit.parsed_name}"
        )
        
        charge_history = await create_charge_history(db, charge_data)
        
        # 2. 사용자 잔액 업데이트
        await update_user_balance(db, user_id, unmatched_deposit.parsed_amount)
        
        # 3. 미매칭 입금 상태 업데이트
        unmatched_deposit.status = "matched"
        unmatched_deposit.matched_user_id = user_id
        unmatched_deposit.matched_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "매칭이 완료되었습니다",
            "charge_history_id": charge_history.charge_history_id,
            "charged_amount": unmatched_deposit.parsed_amount
        }
        
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "message": f"매칭 처리 중 오류가 발생했습니다: {str(e)}"
        }