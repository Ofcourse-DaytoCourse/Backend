from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from schemas.couple_request import CoupleRequestCreate, CoupleRequestRead
from schemas.couple import CoupleCreate
from crud import crud_couple_request, crud_couple
from typing import List

router = APIRouter()

# 1. 연인 신청 보내기
@router.post("/couples/requests", response_model=CoupleRequestRead, summary="연인 신청 보내기")
async def send_couple_request(req: CoupleRequestCreate, db: AsyncSession = Depends(get_db)):
    try:
        couple_req = await crud_couple_request.create_couple_request(db, req)
        return couple_req
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="연인 신청 중 오류가 발생했습니다.")

# 2. 보낸 연인 신청 조회
@router.get("/couples/requests/sent", summary="보낸 연인 신청 조회")
async def get_sent_requests(user_id: str = Query(..., description="사용자 ID"), db: AsyncSession = Depends(get_db)):
    try:
        requests = await crud_couple_request.get_sent_requests(db, user_id)
        return {
            "requests": [
                {
                    "request_id": req.request_id,
                    "partner_nickname": req.partner_nickname,
                    "status": req.status,
                    "requested_at": req.requested_at.isoformat()
                } for req in requests
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="보낸 신청 조회 중 오류가 발생했습니다.")

# 3. 받은 연인 신청 조회
@router.get("/couples/requests/received", summary="받은 연인 신청 조회")
async def get_received_requests(user_nickname: str = Query(..., description="사용자 닉네임"), db: AsyncSession = Depends(get_db)):
    try:
        requests = await crud_couple_request.get_received_requests(db, user_nickname)
        
        # 각 요청에 대해 요청자의 닉네임도 가져오기
        requests_with_nicknames = []
        for req in requests:
            requester_nickname = await crud_couple_request.get_nickname_by_user_id(db, req.requester_id)
            requests_with_nicknames.append({
                "request_id": req.request_id,
                "requester_id": req.requester_id,
                "requester_nickname": requester_nickname or "알 수 없음",
                "requested_at": req.requested_at.isoformat()
            })
        
        return {
            "requests": requests_with_nicknames
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="받은 신청 조회 중 오류가 발생했습니다.")

# 4. 연인 신청 응답 처리
@router.post("/couples/requests/{request_id}/response", summary="연인 신청 응답 처리")
async def respond_to_request(
    request_id: int,
    action: str = Query(..., description="accept/reject"),
    user_nickname: str = Query(..., description="응답하는 사용자 닉네임"),
    db: AsyncSession = Depends(get_db)
):
    try:
        updated_req = await crud_couple_request.respond_to_request(db, request_id, action, user_nickname)
        
        if action == "accept":
            # 연인 관계 성립 시 Couple 테이블에 추가
            requester_id = updated_req.requester_id
            partner_id = await crud_couple_request.get_user_id_by_nickname(db, user_nickname)
            
            # 요청자의 닉네임 가져오기
            requester_nickname = await crud_couple_request.get_nickname_by_user_id(db, requester_id)
            
            if partner_id and requester_nickname:
                couple_data = CoupleCreate(
                    user1_id=requester_id,
                    user2_id=partner_id,
                    user1_nickname=requester_nickname,  # 요청자의 실제 닉네임
                    user2_nickname=user_nickname        # 수락하는 사람의 닉네임
                )
                couple = await crud_couple.create_couple(db, couple_data)
                
                return {
                    "status": "accepted",
                    "couple_id": couple.couple_id,
                    "partner_nickname": requester_nickname,  # 요청자의 닉네임 반환
                    "message": "연인 요청을 수락했습니다. 연인 관계가 성립되었습니다."
                }
            else:
                raise ValueError("연인 관계 생성 중 오류가 발생했습니다.")
        
        return {
            "status": updated_req.status,
            "message": "연인 요청을 거절했습니다." if action == "reject" else "요청이 처리되었습니다."
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="요청 처리 중 오류가 발생했습니다.")

# 5. 현재 연인 상태 조회
@router.get("/couples/status", summary="현재 연인 상태 조회")
async def get_couple_status(user_id: str = Query(..., description="사용자 ID"), db: AsyncSession = Depends(get_db)):
    try:
        couple = await crud_couple.get_couple_by_user_id(db, user_id)
        if not couple:
            return {
                "has_partner": False,
                "message": "연인 관계가 없습니다."
            }
        
        partner_id = couple.user2_id if couple.user1_id == user_id else couple.user1_id
        partner_nickname = couple.user2_nickname if couple.user1_id == user_id else couple.user1_nickname
        
        return {
            "has_partner": True,
            "couple_info": {
                "couple_id": couple.couple_id,
                "partner_id": partner_id,
                "partner_nickname": partner_nickname,
                "created_at": couple.created_at.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="연인 상태 조회 중 오류가 발생했습니다.")

# 6. 연인 관계 해제
@router.delete("/couples/{couple_id}", summary="연인 관계 해제")
async def delete_couple(
    couple_id: int,
    user_id: str = Query(..., description="사용자 ID"),
    db: AsyncSession = Depends(get_db)
):
    try:
        await crud_couple.delete_couple(db, couple_id, user_id)
        return {
            "message": "연인 관계가 해제되었습니다."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="연인 관계 해제 중 오류가 발생했습니다.")

# 7. 종합 요청 상태 조회 (보낸 신청 + 받은 신청)
@router.get("/couples/requests/all", summary="모든 연인 신청 상태 조회")
async def get_all_requests(
    user_id: str = Query(..., description="사용자 ID"),
    user_nickname: str = Query(..., description="사용자 닉네임"),
    db: AsyncSession = Depends(get_db)
):
    try:
        sent_requests = await crud_couple_request.get_sent_requests(db, user_id)
        received_requests = await crud_couple_request.get_received_requests(db, user_nickname)
        
        # 받은 요청에 요청자 닉네임 추가
        received_requests_with_nicknames = []
        for req in received_requests:
            requester_nickname = await crud_couple_request.get_nickname_by_user_id(db, req.requester_id)
            received_requests_with_nicknames.append({
                "request_id": req.request_id,
                "requester_id": req.requester_id,
                "requester_nickname": requester_nickname or "알 수 없음",
                "requested_at": req.requested_at.isoformat()
            })
        
        return {
            "sent_requests": [
                {
                    "request_id": req.request_id,
                    "partner_nickname": req.partner_nickname,
                    "status": req.status,
                    "requested_at": req.requested_at.isoformat()
                } for req in sent_requests
            ],
            "received_requests": received_requests_with_nicknames
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="요청 상태 조회 중 오류가 발생했습니다.")