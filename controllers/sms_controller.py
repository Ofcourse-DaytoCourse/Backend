# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import re

from crud.crud_sms import (
    create_sms_log, create_unmatched_deposit, process_sms_message,
    find_matching_deposit_request, process_matched_deposit, check_duplicate_sms
)
from crud.crud_deposit import get_pending_deposits_by_amount
from schemas.sms_schema import SmsLogCreate, SmsParsedData

# 6.2.1 parse_sms_message 함수
async def parse_sms_message(
    db: AsyncSession,
    raw_message: str
) -> Dict[str, Any]:
    """SMS 메시지 파싱 비즈니스 로직"""
    
    try:
        # SMS 파싱 (예시 형식: "07/18 16:50 *420576 입금 8원 떼껄룩스")
        parsed_data = parse_bank_sms_format(raw_message)
        
        if not parsed_data["success"]:
            return {
                "success": False,
                "message": "SMS 파싱에 실패했습니다",
                "error_code": "PARSE_FAILED",
                "raw_message": raw_message,
                "error_details": parsed_data["error"]
            }
        
        # 중복 SMS 체크 (6대 아이폰에서 같은 메시지가 여러번 올 수 있음)
        if await check_duplicate_sms(
            db, 
            parsed_data["amount"], 
            parsed_data["deposit_name"], 
            parsed_data["transaction_time"]
        ):
            return {
                "success": False,
                "message": "이미 처리된 SMS입니다",
                "error_code": "DUPLICATE_SMS",
                "parsed_data": parsed_data
            }
        
        # SMS 로그 생성 (datetime 객체를 ISO 문자열로 변환)
        parsed_data_for_log = parsed_data.copy()
        if isinstance(parsed_data["transaction_time"], datetime):
            parsed_data_for_log["transaction_time"] = parsed_data["transaction_time"].isoformat()
        
        sms_data = SmsLogCreate(
            raw_message=raw_message,
            parsed_data=parsed_data_for_log,
            parsed_amount=parsed_data["amount"],
            parsed_name=parsed_data["deposit_name"],
            parsed_time=parsed_data["transaction_time"],
            processing_status="received"
        )
        
        sms_log = await create_sms_log(db, sms_data)
        
        return {
            "success": True,
            "message": "SMS 파싱이 완료되었습니다",
            "data": {
                "sms_log_id": sms_log.sms_log_id,
                "parsed_amount": parsed_data["amount"],
                "parsed_name": parsed_data["deposit_name"],
                "parsed_time": parsed_data["transaction_time"],
                "raw_message": raw_message
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"SMS 파싱 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

def parse_bank_sms_format(raw_message: str) -> Dict[str, Any]:
    """은행 SMS 파싱 함수 (다중 형식 지원)"""
    
    try:
        # 우리은행 SMS 형식 먼저 시도
        woori_result = parse_woori_bank_sms(raw_message)
        if woori_result["success"]:
            return woori_result
        
        # 기존 형식 시도: "07/18 16:50 *420576 입금 8원 떼껄룩스"
        pattern = r"(\d{2}/\d{2})\s+(\d{2}:\d{2})\s+\*?\d+\s+입금\s+(\d+)원\s+(.+)"
        
        match = re.search(pattern, raw_message.strip())
        
        if not match:
            return {
                "success": False,
                "error": "지원되지 않는 SMS 형식입니다"
            }
        
        date_part = match.group(1)  # 07/18
        time_part = match.group(2)  # 16:50
        amount_str = match.group(3)  # 8
        deposit_name = match.group(4).strip()  # 떼껄룩스
        
        # 금액 변환
        try:
            amount = int(amount_str)
        except ValueError:
            return {
                "success": False,
                "error": "금액 파싱에 실패했습니다"
            }
        
        # 날짜/시간 파싱 (현재 연도 기준)
        current_year = datetime.now().year
        try:
            # 07/18 16:50 -> 2024-07-18 16:50:00
            datetime_str = f"{current_year}-{date_part.replace('/', '-')} {time_part}:00"
            transaction_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            transaction_time = transaction_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return {
                "success": False,
                "error": "날짜/시간 파싱에 실패했습니다"
            }
        
        return {
            "success": True,
            "amount": amount,
            "deposit_name": deposit_name,
            "transaction_time": transaction_time,
            "date_part": date_part,
            "time_part": time_part
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"파싱 중 서버 오류: {str(e)}"
        }

def parse_woori_bank_sms(raw_message: str) -> Dict[str, Any]:
    """우리은행 SMS 파싱 함수"""
    
    try:
        # 우리은행 SMS 정규식 패턴
        # [Web발신]\n우리 07/21 02:27\n*420576\n입금 1000원\n주노9013
        pattern = r"\[Web발신\]\s*\n우리\s+(\d{2}/\d{2})\s+(\d{2}:\d{2})\s*\n\*\d+\s*\n입금\s+(\d+)원\s*\n(.+)"
        
        match = re.search(pattern, raw_message.strip(), re.MULTILINE)
        
        if not match:
            return {
                "success": False,
                "error": "우리은행 SMS 형식이 일치하지 않습니다"
            }
        
        date_part = match.group(1)  # 07/21
        time_part = match.group(2)  # 02:27  
        amount_str = match.group(3)  # 1000
        deposit_name = match.group(4).strip()  # 주노9013
        
        # 금액 변환
        try:
            amount = int(amount_str)
        except ValueError:
            return {
                "success": False,
                "error": "금액 파싱에 실패했습니다"
            }
        
        # 날짜/시간 파싱 (한국시간으로 처리)
        current_year = datetime.now().year
        try:
            datetime_str = f"{current_year}-{date_part.replace('/', '-')} {time_part}:00"
            # 한국시간으로 파싱 후 UTC로 변환
            from datetime import timezone, timedelta
            kst = timezone(timedelta(hours=9))
            transaction_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            transaction_time = transaction_time.replace(tzinfo=kst)
            # UTC로 변환
            transaction_time = transaction_time.astimezone(timezone.utc)
        except ValueError:
            return {
                "success": False,
                "error": "날짜/시간 파싱에 실패했습니다"
            }
        
        return {
            "success": True,
            "amount": amount,
            "deposit_name": deposit_name,
            "transaction_time": transaction_time,
            "date_part": date_part,
            "time_part": time_part
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"우리은행 SMS 파싱 중 오류: {str(e)}"
        }

# 6.2.2 match_deposit 함수 - 완벽 일치만 사용
async def match_deposit(
    db: AsyncSession,
    parsed_amount: int,
    parsed_name: str,
    parsed_time: datetime
) -> Dict[str, Any]:
    """입금 매칭 비즈니스 로직 - 완벽 일치만"""
    
    try:
        # 완벽 일치하는 입금 요청 찾기 (입금자명이 정확히 일치해야 함)
        deposit_request = await find_matching_deposit_request(
            db, parsed_name, parsed_amount, 24  # 24시간 내 요청
        )
        
        if deposit_request:
            return {
                "success": True,
                "matched": True,
                "message": "완벽히 일치하는 입금 요청을 찾았습니다",
                "data": {
                    "deposit_request_id": deposit_request.deposit_request_id,
                    "user_id": deposit_request.user_id,
                    "deposit_name": deposit_request.deposit_name,
                    "amount": deposit_request.amount,
                    "created_at": deposit_request.created_at,
                    "expires_at": deposit_request.expires_at
                }
            }
        else:
            # 완벽 일치하는 요청이 없으면 미매칭으로 처리
            return {
                "success": True,
                "matched": False,
                "message": "완벽히 일치하는 입금 요청을 찾을 수 없습니다",
                "data": {
                    "parsed_amount": parsed_amount,
                    "parsed_name": parsed_name,
                    "parsed_time": parsed_time,
                    "requires_manual_matching": True
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"입금 매칭 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.2.3 process_matched_deposit 함수
async def process_matched_deposit(
    db: AsyncSession,
    sms_log_id: int,
    deposit_request_id: int
) -> Dict[str, Any]:
    """매칭된 입금 처리 비즈니스 로직"""
    
    try:
        from crud.crud_sms import update_sms_log_status
        from controllers.payments_controller import process_payment
        from crud.crud_deposit import get_deposit_request
        
        # SMS 로그 조회
        from crud.crud_sms import get_sms_logs
        sms_logs = await get_sms_logs(db, skip=0, limit=1)
        sms_log = next((log for log in sms_logs if log.sms_log_id == sms_log_id), None)
        
        if not sms_log:
            return {
                "success": False,
                "message": "SMS 로그를 찾을 수 없습니다",
                "error_code": "SMS_LOG_NOT_FOUND"
            }
        
        # 입금 요청 조회
        deposit_request = await get_deposit_request(db, deposit_request_id)
        if not deposit_request:
            return {
                "success": False,
                "message": "입금 요청을 찾을 수 없습니다",
                "error_code": "DEPOSIT_REQUEST_NOT_FOUND"
            }
        
        # 결제 처리 - 실제 입금된 금액으로 충전
        payment_result = await process_payment(
            db,
            deposit_request.user_id,
            deposit_request_id,
            sms_log.parsed_amount  # 실제 입금된 금액
        )
        
        if payment_result["success"]:
            # SMS 로그 상태 업데이트
            await update_sms_log_status(db, sms_log_id, "processed")
            
            return {
                "success": True,
                "message": "매칭된 입금이 성공적으로 처리되었습니다",
                "data": {
                    "sms_log_id": sms_log_id,
                    "deposit_request_id": deposit_request_id,
                    "user_id": deposit_request.user_id,
                    "processed_amount": sms_log.parsed_amount,
                    "payment_result": payment_result["data"]
                }
            }
        else:
            # 결제 처리 실패
            await update_sms_log_status(
                db, sms_log_id, "failed", 
                f"결제 처리 실패: {payment_result['message']}"
            )
            
            return {
                "success": False,
                "message": f"결제 처리에 실패했습니다: {payment_result['message']}",
                "error_code": "PAYMENT_FAILED",
                "payment_error": payment_result
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"매칭된 입금 처리 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.2.4 handle_unmatched_deposit 함수
async def handle_unmatched_deposit(
    db: AsyncSession,
    sms_log_id: int,
    parsed_amount: int,
    parsed_name: str,
    parsed_time: datetime
) -> Dict[str, Any]:
    """미매칭 입금 처리 비즈니스 로직"""
    
    try:
        from crud.crud_sms import update_sms_log_status, get_sms_logs
        
        # SMS 로그 조회
        sms_logs = await get_sms_logs(db, skip=0, limit=1)
        sms_log = next((log for log in sms_logs if log.sms_log_id == sms_log_id), None)
        
        if not sms_log:
            return {
                "success": False,
                "message": "SMS 로그를 찾을 수 없습니다",
                "error_code": "SMS_LOG_NOT_FOUND"
            }
        
        # 미매칭 입금 데이터 생성
        unmatched_deposit = await create_unmatched_deposit(db, sms_log)
        
        # SMS 로그 상태 업데이트
        await update_sms_log_status(db, sms_log_id, "processed")
        
        return {
            "success": True,
            "message": "미매칭 입금이 저장되었습니다",
            "data": {
                "unmatched_deposit_id": unmatched_deposit.unmatched_deposit_id,
                "sms_log_id": sms_log_id,
                "parsed_amount": parsed_amount,
                "parsed_name": parsed_name,
                "parsed_time": parsed_time,
                "expires_at": unmatched_deposit.expires_at,
                "requires_manual_matching": True
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"미매칭 입금 처리 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 6.2.5 SMS 전체 로직 - 완전 자동화
async def process_sms_end_to_end(
    db: AsyncSession,
    raw_message: str
) -> Dict[str, Any]:
    """SMS 수신부터 처리까지 전체 자동화"""
    
    try:
        # 1. SMS 파싱
        parse_result = await parse_sms_message(db, raw_message)
        if not parse_result["success"]:
            return parse_result
        
        sms_log_id = parse_result["data"]["sms_log_id"]
        parsed_amount = parse_result["data"]["parsed_amount"]
        parsed_name = parse_result["data"]["parsed_name"]
        parsed_time = parse_result["data"]["parsed_time"]
        
        # 2. 입금 매칭 (완벽 일치만)
        match_result = await match_deposit(db, parsed_amount, parsed_name, parsed_time)
        if not match_result["success"]:
            return match_result
        
        if match_result["matched"]:
            # 3-A. 매칭된 입금 처리
            deposit_request_id = match_result["data"]["deposit_request_id"]
            process_result = await process_matched_deposit(db, sms_log_id, deposit_request_id)
            
            return {
                "success": process_result["success"],
                "message": process_result["message"],
                "flow": "matched_and_processed",
                "data": {
                    "sms_parse": parse_result["data"],
                    "match_result": match_result["data"],
                    "process_result": process_result.get("data", {})
                }
            }
        else:
            # 3-B. 미매칭 입금 처리
            unmatched_result = await handle_unmatched_deposit(
                db, sms_log_id, parsed_amount, parsed_name, parsed_time
            )
            
            return {
                "success": unmatched_result["success"],
                "message": unmatched_result["message"],
                "flow": "unmatched_stored",
                "data": {
                    "sms_parse": parse_result["data"],
                    "match_result": match_result["data"],
                    "unmatched_result": unmatched_result.get("data", {})
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"SMS 처리 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }

# 수동 매칭용 함수 - 완벽 일치 기반
async def get_manual_match_candidates(
    db: AsyncSession,
    unmatched_deposit_id: int
) -> Dict[str, Any]:
    """미매칭 입금에 대한 수동 매칭 후보 조회 (완벽 일치 기반)"""
    
    try:
        from crud.crud_sms import get_unmatched_deposit
        
        # 미매칭 입금 조회
        unmatched_deposit = await get_unmatched_deposit(db, unmatched_deposit_id)
        if not unmatched_deposit:
            return {
                "success": False,
                "message": "미매칭 입금을 찾을 수 없습니다",
                "error_code": "UNMATCHED_DEPOSIT_NOT_FOUND"
            }
        
        # 같은 금액의 입금 요청들 조회 (완벽 일치만)
        exact_amount_deposits = await get_pending_deposits_by_amount(
            db, unmatched_deposit.parsed_amount, 180  # 3시간 범위
        )
        
        return {
            "success": True,
            "data": {
                "unmatched_deposit": {
                    "unmatched_deposit_id": unmatched_deposit.unmatched_deposit_id,
                    "parsed_amount": unmatched_deposit.parsed_amount,
                    "parsed_name": unmatched_deposit.parsed_name,
                    "parsed_time": unmatched_deposit.parsed_time
                },
                "exact_amount_matches": [
                    {
                        "deposit_request_id": d.deposit_request_id,
                        "deposit_name": d.deposit_name,
                        "user_id": d.user_id,
                        "amount": d.amount,
                        "created_at": d.created_at
                    } for d in exact_amount_deposits
                ],
                "total_candidates": len(exact_amount_deposits),
                "manual_matching_required": True
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"수동 매칭 후보 조회 중 서버 오류가 발생했습니다: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }