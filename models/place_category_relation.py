from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class PlaceCategoryRelation(Base):
    __tablename__ = "place_category_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String, ForeignKey("places.place_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("place_category.category_id"), nullable=False)  # 이제 타입 일치
    priority = Column(Integer, nullable=False, default=1)  # 1=1차 카테고리, 2=2차 카테고리
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    place = relationship("Place", back_populates="category_relations")
    category = relationship("PlaceCategory", back_populates="place_relations")
    
    # 인덱스 설정
    __table_args__ = (
        Index('idx_place_category', 'place_id', 'category_id'),
        Index('idx_place_priority', 'place_id', 'priority'),
        Index('idx_category_priority', 'category_id', 'priority'),
    )