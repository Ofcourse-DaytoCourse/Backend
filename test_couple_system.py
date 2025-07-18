import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.session import SessionLocal
from models.user import User
from schemas.couple_request import CoupleRequestCreate
from crud import crud_couple_request, crud_couple

async def create_test_user():
    """테스트용 사용자 '테스터' 생성"""
    async with SessionLocal() as db:
        # 기존에 '테스터' 사용자가 있는지 확인
        result = await db.execute(
            select(User).where(User.nickname == "테스터")
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"✅ 기존 테스트 사용자 발견: {existing_user.nickname} (ID: {existing_user.user_id})")
            return existing_user
        
        # 새 테스트 사용자 생성
        test_user = User(
            user_id=str(uuid.uuid4()),
            nickname="테스터",
            email="tester@test.com",
            user_status="active"
        )
        
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        
        print(f"✅ 테스트 사용자 생성 완료: {test_user.nickname} (ID: {test_user.user_id})")
        return test_user

async def find_juno_user():
    """'주노' 사용자 찾기"""
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.nickname == "주노")
        )
        juno_user = result.scalar_one_or_none()
        
        if not juno_user:
            print("❌ '주노' 사용자를 찾을 수 없습니다. 먼저 회원가입을 해주세요.")
            return None
        
        print(f"✅ '주노' 사용자 발견: {juno_user.nickname} (ID: {juno_user.user_id})")
        return juno_user

async def send_couple_request_from_tester_to_juno():
    """테스터에서 주노에게 연인 신청 보내기"""
    async with SessionLocal() as db:
        # 테스터 사용자 가져오기
        tester = await create_test_user()
        juno = await find_juno_user()
        
        if not juno:
            return False
        
        # 기존 신청이 있는지 확인
        existing_requests = await crud_couple_request.get_sent_requests(db, tester.user_id)
        for req in existing_requests:
            if req.partner_nickname == "주노" and req.status == "pending":
                print(f"⚠️ 이미 '주노'에게 보낸 대기중인 연인 신청이 있습니다 (요청 ID: {req.request_id})")
                return True
        
        try:
            # 연인 신청 생성
            request_data = CoupleRequestCreate(
                requester_id=tester.user_id,
                partner_nickname="주노"
            )
            
            couple_request = await crud_couple_request.create_couple_request(db, request_data)
            print(f"✅ 연인 신청 성공! 요청 ID: {couple_request.request_id}")
            print(f"   요청자: {tester.nickname} -> 대상: 주노")
            print(f"   상태: {couple_request.status}")
            return True
            
        except ValueError as e:
            print(f"❌ 연인 신청 실패: {e}")
            return False

async def check_all_requests():
    """모든 연인 신청 상태 확인"""
    async with SessionLocal() as db:
        juno = await find_juno_user()
        tester_result = await db.execute(select(User).where(User.nickname == "테스터"))
        tester = tester_result.scalar_one_or_none()
        
        if not juno or not tester:
            print("❌ 사용자를 찾을 수 없습니다.")
            return
        
        print("\n📋 === 연인 신청 현황 ===")
        
        # 주노가 받은 신청들
        juno_received = await crud_couple_request.get_received_requests(db, "주노")
        print(f"\n🎯 주노가 받은 신청 ({len(juno_received)}개):")
        for req in juno_received:
            print(f"  - 요청 ID: {req.request_id}, 요청자: {req.requester_id}, 날짜: {req.requested_at}")
        
        # 테스터가 보낸 신청들
        tester_sent = await crud_couple_request.get_sent_requests(db, tester.user_id)
        print(f"\n📤 테스터가 보낸 신청 ({len(tester_sent)}개):")
        for req in tester_sent:
            print(f"  - 요청 ID: {req.request_id}, 대상: {req.partner_nickname}, 상태: {req.status}, 날짜: {req.requested_at}")

async def check_couple_status():
    """연인 관계 상태 확인"""
    async with SessionLocal() as db:
        juno = await find_juno_user()
        tester_result = await db.execute(select(User).where(User.nickname == "테스터"))
        tester = tester_result.scalar_one_or_none()
        
        if not juno or not tester:
            return
        
        print("\n💕 === 연인 관계 상태 ===")
        
        # 주노의 연인 상태
        juno_couple = await crud_couple.get_couple_by_user_id(db, juno.user_id)
        if juno_couple:
            partner = juno_couple.user2_nickname if juno_couple.user1_id == juno.user_id else juno_couple.user1_nickname
            print(f"주노: {partner}과 연인 관계 (커플 ID: {juno_couple.couple_id})")
        else:
            print("주노: 연인 관계 없음")
        
        # 테스터의 연인 상태
        tester_couple = await crud_couple.get_couple_by_user_id(db, tester.user_id)
        if tester_couple:
            partner = tester_couple.user2_nickname if tester_couple.user1_id == tester.user_id else tester_couple.user1_nickname
            print(f"테스터: {partner}과 연인 관계 (커플 ID: {tester_couple.couple_id})")
        else:
            print("테스터: 연인 관계 없음")

async def main():
    print("🚀 연인 신청 시스템 테스트 시작!\n")
    
    # 1. 테스트 사용자 생성
    await create_test_user()
    
    # 2. 주노 사용자 확인
    juno = await find_juno_user()
    if not juno:
        print("먼저 '주노' 계정으로 회원가입을 해주세요.")
        return
    
    # 3. 테스터 -> 주노 연인 신청
    print(f"\n📤 테스터 -> 주노 연인 신청 보내기...")
    success = await send_couple_request_from_tester_to_juno()
    
    if success:
        # 4. 모든 신청 상태 확인
        await check_all_requests()
        
        # 5. 연인 관계 상태 확인
        await check_couple_status()
        
        print(f"\n✅ 테스트 완료!")
        print(f"📱 이제 '주노' 계정으로 로그인해서 연인 관리 페이지에서 받은 신청을 확인해보세요!")
        print(f"🎯 또한 '테스터' 닉네임으로 주노에게 신청을 보내볼 수 있습니다!")

if __name__ == "__main__":
    asyncio.run(main())