from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from models.couple_request import CoupleRequest
from models.user import User
from schemas.couple_request import CoupleRequestCreate

# 연인 신청 생성 (본인 신청 방지 및 사용자 존재 확인)
async def create_couple_request(db: AsyncSession, req_in: CoupleRequestCreate):
    # 1. 상대방 닉네임으로 사용자 존재 확인
    result = await db.execute(
        select(User).where(User.nickname == req_in.partner_nickname)
    )
    partner_user = result.scalar_one_or_none()
    if not partner_user:
        raise ValueError("존재하지 않는 닉네임입니다.")
    
    # 2. 본인 신청 방지
    if partner_user.user_id == req_in.requester_id:
        raise ValueError("본인에게는 연인 신청을 할 수 없습니다.")
    
    # 3. 중복 신청 방지
    existing_request = await db.execute(
        select(CoupleRequest).where(
            CoupleRequest.requester_id == req_in.requester_id,
            CoupleRequest.partner_nickname == req_in.partner_nickname,
            CoupleRequest.status == "pending"
        )
    )
    if existing_request.scalar_one_or_none():
        raise ValueError("이미 해당 사용자에게 연인 신청을 보냈습니다.")
    
    # 4. 연인 신청 생성
    couple_req = CoupleRequest(**req_in.model_dump())
    db.add(couple_req)
    await db.commit()
    await db.refresh(couple_req)
    return couple_req

# 내가 보낸 신청 조회 (cancelled 제외)
async def get_sent_requests(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(CoupleRequest).where(
            CoupleRequest.requester_id == user_id,
            CoupleRequest.status != "cancelled"
        ).order_by(CoupleRequest.requested_at.desc())
    )
    return result.scalars().all()

# 내가 받은 신청 조회
async def get_received_requests(db: AsyncSession, user_nickname: str):
    result = await db.execute(
        select(CoupleRequest).where(
            CoupleRequest.partner_nickname == user_nickname,
            CoupleRequest.status == "pending"
        ).order_by(CoupleRequest.requested_at.desc())
    )
    return result.scalars().all()

# 특정 신청에 대한 응답 처리
async def respond_to_request(db: AsyncSession, request_id: int, action: str, responding_user_nickname: str):
    result = await db.execute(
        select(CoupleRequest).where(
            CoupleRequest.request_id == request_id,
            CoupleRequest.partner_nickname == responding_user_nickname,
            CoupleRequest.status == "pending"
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise ValueError("해당 신청을 찾을 수 없거나 이미 처리된 신청입니다.")
    
    if action == "accept":
        req.status = "accepted"
    elif action == "reject":
        req.status = "rejected"
    else:
        raise ValueError("유효하지 않은 액션입니다.")
    
    await db.commit()
    await db.refresh(req)
    return req

# 사용자 닉네임으로 사용자 ID 조회
async def get_user_id_by_nickname(db: AsyncSession, nickname: str):
    result = await db.execute(
        select(User.user_id).where(User.nickname == nickname)
    )
    return result.scalar_one_or_none()

# 사용자 ID로 닉네임 조회
async def get_nickname_by_user_id(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(User.nickname).where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()

# ✅ 연인 해제 시 accepted 요청들을 양방향 모두 cancelled로 변경
async def cancel_accepted_request(db: AsyncSession, requester_id: str, partner_nickname: str):
    # 본인 닉네임 조회
    my_nickname_result = await db.execute(
        select(User.nickname).where(User.user_id == requester_id)
    )
    my_nickname = my_nickname_result.scalar_one_or_none()

    # 상대방 ID 조회
    partner_id_result = await db.execute(
        select(User.user_id).where(User.nickname == partner_nickname)
    )
    partner_id = partner_id_result.scalar_one_or_none()

    if not my_nickname or not partner_id:
        raise ValueError("사용자 정보를 찾을 수 없습니다.")

    # 양방향으로 accepted 상태의 신청 조회
    result = await db.execute(
        select(CoupleRequest).where(
            or_(
                and_(
                    CoupleRequest.requester_id == requester_id,
                    CoupleRequest.partner_nickname == partner_nickname
                ),
                and_(
                    CoupleRequest.requester_id == partner_id,
                    CoupleRequest.partner_nickname == my_nickname
                )
            ),
            CoupleRequest.status == "accepted"
        )
    )
    requests = result.scalars().all()
    for req in requests:
        req.status = "cancelled"

    await db.commit()
