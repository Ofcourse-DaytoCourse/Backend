-- 환불 승인 오류 해결을 위한 마이그레이션
-- 작성일: 2025-07-20
-- 목적: usage_histories 테이블의 service_type에 'refund' 값 추가

-- ================================================================
-- usage_histories 테이블의 service_type CHECK 제약조건 수정
-- ================================================================

-- 기존 제약조건 삭제
ALTER TABLE usage_histories 
DROP CONSTRAINT IF EXISTS chk_usage_service_type_valid;

-- 새로운 제약조건 추가 ('refund' 포함)
ALTER TABLE usage_histories 
ADD CONSTRAINT chk_usage_service_type_valid 
CHECK (service_type IN ('course_generation', 'premium_feature', 'chat_service', 'other', 'refund'));

-- 수정 완료 확인
SELECT '✅ usage_histories service_type에 refund 추가 완료' AS status;