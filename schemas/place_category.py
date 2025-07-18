from pydantic import BaseModel

class PlaceCategoryBase(BaseModel):
    category_name: str

class PlaceCategoryCreate(PlaceCategoryBase):
    pass

class PlaceCategoryRead(PlaceCategoryBase):
    category_id: int

    class Config:
        from_attributes = True
