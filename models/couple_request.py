from sqlalchemy import Column, Integer, String, TIMESTAMP, func, ForeignKey
from models.base import Base

class CoupleRequest(Base):
    __tablename__ = "couple_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # BigInteger → Integer 변경
    requester_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)  # UUID와 일치
    partner_nickname = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    requested_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
