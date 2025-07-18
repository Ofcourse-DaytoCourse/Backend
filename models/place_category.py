from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

class PlaceCategory(Base):
    __tablename__ = "place_category"

    category_id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # BigInteger → Integer + autoincrement 추가
    category_name = Column(String(50), nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    place_relations = relationship("PlaceCategoryRelation", back_populates="category")
