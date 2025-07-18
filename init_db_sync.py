from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from models.base import Base
from config import DATABASE_URL

# 동기 엔진 생성 (sqlite)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev.db")
sync_database_url = f"sqlite:///{db_path}"
engine = create_engine(sync_database_url, echo=True)

# 모든 모델 import
import models.user
import models.user_oauth  
import models.place
import models.place_category
import models.place_category_relation  # ✅ 새로 추가된 모델
import models.course
import models.course_place
import models.chat_session
import models.couple_request
import models.comment
import models.couple

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ 모든 DB 테이블 생성 완료!")

if __name__ == "__main__":
    init_db()