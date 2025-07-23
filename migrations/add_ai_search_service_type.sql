-- 마이그레이션: AI 검색 서비스 타입 추가
-- 생성일: 2025-07-23
-- 목적: usage_histories 테이블의 service_type 제약 조건에 'ai_search' 추가

-- 기존 제약 조건 삭제
ALTER TABLE usage_histories DROP CONSTRAINT IF EXISTS usage_histories_service_type_check;
ALTER TABLE usage_histories DROP CONSTRAINT IF EXISTS chk_usage_service_type_valid;

-- 새로운 제약 조건 추가 (ai_search 포함)
ALTER TABLE usage_histories ADD CONSTRAINT chk_usage_service_type_valid 
CHECK (service_type IN ('course_generation', 'premium_feature', 'chat_service', 'ai_search', 'other', 'refund'));

-- 확인 쿼리 (선택사항)
-- SELECT conname, consrc FROM pg_constraint WHERE conname = 'chk_usage_service_type_valid';