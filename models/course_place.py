from sqlalchemy import Column, BigInteger, Integer, String, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from models.base import Base

class CoursePlace(Base):
    __tablename__ = "course_places"
    __table_args__ = (
        UniqueConstraint('course_id', 'sequence_order', name='uq_course_sequence_order'),
    )

    course_place_id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # BigInteger → Integer + autoincrement 추가
    course_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False)  # BigInteger → Integer
    place_id = Column(String(50), ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False)  # BigInteger → String
    sequence_order = Column(Integer, nullable=False)
    estimated_duration = Column(Integer, nullable=True)
    estimated_cost = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
