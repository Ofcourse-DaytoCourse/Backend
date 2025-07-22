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
    places = relationship("Place", back_populates="category")
    place_relations = relationship("PlaceCategoryRelation", back_populates="category")
    
    @property
    def name(self):
        """category_name을 name으로 접근할 수 있도록 하는 프로퍼티"""
        return self.category_name
