from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.course_place import CoursePlace
from schemas.course_place import CoursePlaceCreate

async def create_course_place(db: AsyncSession, course_place_in: CoursePlaceCreate):
    db_course_place = CoursePlace(**course_place_in.dict())
    db.add(db_course_place)
    await db.commit()
    await db.refresh(db_course_place)
    return db_course_place

async def get_course_place(db: AsyncSession, course_place_id: int):
    result = await db.execute(select(CoursePlace).where(CoursePlace.course_place_id == course_place_id))
    return result.scalar_one_or_none()
