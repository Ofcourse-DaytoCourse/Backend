from sqlalchemy import Column, Integer, String, TIMESTAMP, func, ForeignKey
from models.base import Base

class Couple(Base):
    __tablename__ = "couples"

    couple_id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # BigInteger → Integer 변경
    user1_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    user2_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    user1_nickname = Column(String(50), nullable=False)
    user2_nickname = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())