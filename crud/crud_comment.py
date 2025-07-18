from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.comment import Comment
from schemas.comment import CommentCreate, CommentDelete

async def create_comment(db: AsyncSession, comment_in: CommentCreate):
    db_comment = Comment(**comment_in.model_dump())
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)
    return db_comment

async def get_comment(db: AsyncSession, comment_id: int):
    result = await db.execute(select(Comment).where(Comment.comment_id == comment_id))
    return result.scalar_one_or_none()

async def delete_comment(db: AsyncSession, comment: Comment):
    await db.delete(comment)
    await db.commit()

async def get_comment_for_delete(db: AsyncSession, comment_in: CommentDelete):
    result = await db.execute(
        select(Comment).where(
            Comment.course_id == comment_in.course_id,
            Comment.user_id == comment_in.user_id,
            Comment.nickname == comment_in.nickname,
            Comment.comment == comment_in.comment
        )
    )
    return result.scalar_one_or_none()
