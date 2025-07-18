import asyncio
from db.session import SessionLocal
from crud import crud_couple_request, crud_couple
from schemas.couple_request import CoupleRequestCreate

async def quick_test():
    async with SessionLocal() as db:
        print("🎮 빠른 테스트 메뉴")
        print("1. 테스터 → 주노 신청")
        print("2. 주노가 받은 신청 보기")
        print("3. 신청 수락하기")
        print("4. 연인 관계 해제")
        
        choice = input("선택: ")
        
        if choice == "1":
            req = CoupleRequestCreate(requester_id="226cca2c-7d69-4406-a4c7-24bec96bd8d4", partner_nickname="주노")
            result = await crud_couple_request.create_couple_request(db, req)
            print(f"✅ 신청 완료! ID: {result.request_id}")
            
        elif choice == "2":
            reqs = await crud_couple_request.get_received_requests(db, "주노")
            for req in reqs:
                nick = await crud_couple_request.get_nickname_by_user_id(db, req.requester_id)
                print(f"📩 {nick}님의 신청 (ID: {req.request_id})")
                
        elif choice == "3":
            req_id = int(input("요청 ID: "))
            await crud_couple_request.respond_to_request(db, req_id, "accept", "주노")
            print("✅ 수락 완료!")
            
        elif choice == "4":
            couples = await crud_couple.get_couple_by_user_id(db, "7fdbfe27-01b8-438e-b3aa-9108913551d5")
            if couples:
                await crud_couple.delete_couple(db, couples.couple_id, "7fdbfe27-01b8-438e-b3aa-9108913551d5")
                print("💔 해제 완료!")

if __name__ == "__main__":
    asyncio.run(quick_test())