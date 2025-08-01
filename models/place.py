from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, Boolean, Float, JSON, TIMESTAMP, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

class Place(Base):
    __tablename__ = "places"

    place_id = Column(String(50), primary_key=True, index=True)  # BigInteger → String으로 변경
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)  # nullable=True로 변경
    kakao_url = Column(String(500), nullable=True)  # 카카오 URL 추가
    phone = Column(String(30), nullable=True)
    is_parking = Column(Boolean, nullable=False, server_default="false")
    is_open = Column(Boolean, nullable=False, server_default="true")
    open_hours = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    price = Column(JSON, nullable=True, server_default="[]")  # price_range → price (JSON)
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    info_urls = Column(JSON, nullable=True, server_default="[]")
    category_id = Column(BigInteger, ForeignKey("place_category.category_id"), nullable=True)  # nullable=True로 변경
    
    # 새로 추가할 필드들
    business_hours = Column(JSON, nullable=True, server_default="{}")
    menu_info = Column(JSON, nullable=True, server_default="[]") 
    homepage_url = Column(String(500), nullable=True)
    kakao_category = Column(String(100), nullable=True)
    major_category = Column(String(50), nullable=True)    # 대분류
    middle_category = Column(String(50), nullable=True)   # 중분류  
    minor_category = Column(String(50), nullable=True)    # 소분류
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 관계 설정
    category = relationship("PlaceCategory", back_populates="places")
    category_relations = relationship("PlaceCategoryRelation", back_populates="place")
