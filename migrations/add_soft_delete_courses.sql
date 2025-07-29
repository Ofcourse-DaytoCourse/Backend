-- 코스 soft delete 시스템 추가
-- 작성일: 2025-07-27
-- 목적: courses 테이블에 is_deleted 컬럼 추가하여 soft delete 구현

-- ================================================================
-- 1. courses 테이블에 is_deleted 컬럼 추가
-- ================================================================

ALTER TABLE courses 
ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;

-- 인덱스 추가 (삭제되지 않은 코스 조회 성능 향상)
CREATE INDEX idx_courses_is_deleted ON courses(is_deleted);

-- 복합 인덱스 추가 (사용자별 삭제되지 않은 코스 조회)
CREATE INDEX idx_courses_user_id_is_deleted ON courses(user_id, is_deleted);

-- 완료 확인
SELECT '✅ courses soft delete 시스템 추가 완료' AS status;