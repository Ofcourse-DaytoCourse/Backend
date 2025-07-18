import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.session import SessionLocal
from models.user import User
from crud import crud_couple_request, crud_couple

async def test_accept_request():
    """연인 신청 수락 테스트"""
    async with SessionLocal() as db:
        print("🧪 연인 신청 수락 테스트 시작!")
        
        # 1. 기존 신청 확인
        received_requests = await crud_couple_request.get_received_requests(db, "주노")
        if not received_requests:
            print("❌ 주노가 받은 연인 신청이 없습니다. 먼저 신청을 보내주세요.")
            return
        
        first_request = received_requests[0]
        print(f"📩 받은 신청: 요청 ID {first_request.request_id}, 요청자 ID: {first_request.requester_id}")
        
        # 2. 요청자 닉네임 조회
        requester_nickname = await crud_couple_request.get_nickname_by_user_id(db, first_request.requester_id)
        print(f"👤 요청자 닉네임: {requester_nickname}")
        
        # 3. 신청 수락 시도
        try:
            updated_req = await crud_couple_request.respond_to_request(
                db, first_request.request_id, "accept", "주노"
            )
            print(f"✅ 신청 수락 성공! 상태: {updated_req.status}")
            
            # 4. 연인 관계 생성 시도
            partner_id = await crud_couple_request.get_user_id_by_nickname(db, "주노")
            print(f"💕 주노 ID: {partner_id}")
            
            if partner_id and requester_nickname:
                from schemas.couple import CoupleCreate
                
                couple_data = CoupleCreate(
                    user1_id=first_request.requester_id,
                    user2_id=partner_id,
                    user1_nickname=requester_nickname,
                    user2_nickname="주노"
                )
                
                couple = await crud_couple.create_couple(db, couple_data)
                print(f"💑 연인 관계 생성 성공! 커플 ID: {couple.couple_id}")
                
                # 5. 연인 상태 확인
                juno_couple = await crud_couple.get_couple_by_user_id(db, partner_id)
                tester_couple = await crud_couple.get_couple_by_user_id(db, first_request.requester_id)
                
                print(f"👫 주노 연인 상태: {juno_couple.couple_id if juno_couple else 'None'}")
                print(f"👫 테스터 연인 상태: {tester_couple.couple_id if tester_couple else 'None'}")
                
        except Exception as e:
            print(f"❌ 수락 과정에서 오류 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_accept_request())