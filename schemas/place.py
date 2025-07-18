from pydantic import BaseModel
from typing import Optional, Dict

class PlaceBase(BaseModel):
    name: str
    address: str
    phone: Optional[str]
    price_range: Optional[str]
    description: Optional[str]
    external_urls: Optional[Dict]
    category_id: int

class PlaceCreate(PlaceBase):
    pass

class PlaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class PlaceRead(PlaceBase):
    place_id: int
    category_name: Optional[str]

    class Config:
        from_attributes = True
