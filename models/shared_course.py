from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base


class SharedCourse(Base):
    __tablename__ = "shared_courses"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, unique=True)
    shared_by_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    preview_image_url = Column(Text)
    price = Column(Integer, default=300)
    reward_per_save = Column(Integer, default=100)
    view_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    shared_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    course = relationship("Course")
    shared_by_user = relationship("User")
    reviews = relationship("SharedCourseReview", back_populates="shared_course")
    purchases = relationship("CoursePurchase", back_populates="shared_course")
    buyer_reviews = relationship("CourseBuyerReview", back_populates="shared_course")


class SharedCourseReview(Base):
    __tablename__ = "shared_course_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    shared_course_id = Column(Integer, ForeignKey("shared_courses.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=False)
    tags = Column(ARRAY(String(255)), default=[])
    photo_urls = Column(ARRAY(Text), default=[])
    is_deleted = Column(Boolean, default=False)
    credit_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")
    shared_course = relationship("SharedCourse", back_populates="reviews")


class CoursePurchase(Base):
    __tablename__ = "course_purchases"

    id = Column(Integer, primary_key=True, index=True)
    buyer_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    shared_course_id = Column(Integer, ForeignKey("shared_courses.id"), nullable=False)
    copied_course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    purchase_amount = Column(Integer, nullable=False, default=300)
    is_saved = Column(Boolean, default=False)
    creator_reward_given = Column(Boolean, default=False)
    purchased_at = Column(DateTime, default=func.now())
    saved_at = Column(DateTime)

    # Relationships
    buyer_user = relationship("User")
    shared_course = relationship("SharedCourse", back_populates="purchases")
    copied_course = relationship("Course")
    buyer_reviews = relationship("CourseBuyerReview", back_populates="purchase")


class CourseBuyerReview(Base):
    __tablename__ = "course_buyer_reviews"

    id = Column(Integer, primary_key=True, index=True)
    buyer_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    shared_course_id = Column(Integer, ForeignKey("shared_courses.id", ondelete="CASCADE"), nullable=False)
    purchase_id = Column(Integer, ForeignKey("course_purchases.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=False)
    tags = Column(ARRAY(String(255)), default=[])
    photo_urls = Column(ARRAY(Text), default=[])
    is_deleted = Column(Boolean, default=False)
    credit_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    buyer_user = relationship("User")
    shared_course = relationship("SharedCourse", back_populates="buyer_reviews")
    purchase = relationship("CoursePurchase", back_populates="buyer_reviews")