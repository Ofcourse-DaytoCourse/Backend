from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.place_category import PlaceCategory
from schemas.place_category import PlaceCategoryCreate

async def create_place_category(db: AsyncSession, category_in: PlaceCategoryCreate):
    db_category = PlaceCategory(**category_in.dict())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category

async def get_place_category(db: AsyncSession, category_id: int):
    result = await db.execute(select(PlaceCategory).where(PlaceCategory.category_id == category_id))
    return result.scalar_one_or_none()
