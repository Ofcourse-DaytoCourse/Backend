from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from schemas.comment import CommentCreate, CommentRead, CommentDelete
from crud import crud_comment

router = APIRouter()

# ✅ 5-1. 댓글 등록 (POST /comments/write)
@router.post("/comments/write", summary="댓글 등록")
async def write_comment(comment_in: CommentCreate, db: AsyncSession = Depends(get_db)):
    comment = await crud_comment.create_comment(db, comment_in)
    if not comment:
        raise HTTPException(status_code=400, detail="댓글 등록 실패")
    return {
        "status": "comment_added",
        "comment": {
            "comment_id": comment.comment_id,
            "course_id": comment.course_id,
            "user_id": comment.user_id,
            "nickname": comment.nickname,
            "comment": comment.comment,
            "timestamp": comment.timestamp,
        },
    }

# ✅ 5-2. 댓글 삭제 (DELETE /comments/delete)
@router.delete("/comments/delete", summary="댓글 삭제")
async def delete_comment(comment_in: CommentDelete, db: AsyncSession = Depends(get_db)):
    # CommentDelete는 course_id, user_id, comment_id 등을 포함하는 요청 body
    comment = await crud_comment.get_comment_for_delete(db, comment_in)
    if not comment:
        raise HTTPException(status_code=404, detail="삭제할 댓글을 찾을 수 없습니다.")
    deleted_comment = await crud_comment.delete_comment(db, comment)
    return {
        "status": "comment_deleted",
        "comment": {
            "comment_id": deleted_comment.comment_id,
            "course_id": deleted_comment.course_id,
            "user_id": deleted_comment.user_id,
            "nickname": deleted_comment.nickname,
            "comment": deleted_comment.comment,
            "timestamp": deleted_comment.timestamp,
        },
    }
