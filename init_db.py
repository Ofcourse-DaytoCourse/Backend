import asyncio
from db.session import engine
from models.base import Base  # 공통 Base

# 모든 모델 import 필요
import models.user
import models.user_oauth
import models.place
import models.place_category
import models.place_category_relation  # ✅ 새로 추가된 모델
import models.course
import models.course_place
import models.chat_session
import models.couple_request
import models.couple
import models.comment

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 모든 DB 테이블 생성 완료!")

if __name__ == "__main__":
    asyncio.run(init_models())
