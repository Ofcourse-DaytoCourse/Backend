from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.place import Place
from schemas.place import PlaceCreate

# Create
async def create_place(db: AsyncSession, place_in: PlaceCreate):
    db_place = Place(**place_in.dict())
    db.add(db_place)
    await db.commit()
    await db.refresh(db_place)
    return db_place

# Read
async def get_place(db: AsyncSession, place_id: int):
    result = await db.execute(select(Place).where(Place.place_id == place_id))
    return result.scalar_one_or_none()

# Update
async def update_place(db: AsyncSession, place_id: int, place_in: PlaceCreate):
    db_place = await get_place(db, place_id)
    if not db_place:
        return None
    for key, value in place_in.dict(exclude_unset=True).items():
        setattr(db_place, key, value)
    await db.commit()
    await db.refresh(db_place)
    return db_place

# Delete
async def delete_place(db: AsyncSession, place_id: int):
    db_place = await get_place(db, place_id)
    if not db_place:
        return None
    await db.delete(db_place)
    await db.commit()
    return db_place