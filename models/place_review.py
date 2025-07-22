from sqlalchemy import (
    Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, CheckConstraint, ARRAY
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

class PlaceReview(Base):
    __tablename__ = "place_reviews"
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        CheckConstraint('user_id IS NOT NULL', name='check_user_id_not_null'),
        CheckConstraint('place_id IS NOT NULL', name='check_place_id_not_null'),
        CheckConstraint('course_id IS NOT NULL', name='check_course_id_not_null'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    place_id = Column(String(50), ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=True)
    tags = Column(ARRAY(String(255)), nullable=True, server_default='{}')
    photo_urls = Column(ARRAY(Text), nullable=True, server_default='{}')
    is_deleted = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 관계 설정 (나중에 필요하면 추가)
    # user = relationship("User", back_populates="place_reviews")
    # place = relationship("Place", back_populates="reviews")
    # course = relationship("Course", back_populates="reviews")