-- 환불 시스템 재설계 마이그레이션
-- 작성일: 2025-07-20
-- 목적: charge_history_id 의존성 제거, 단순한 환불 가능 금액 기반 시스템으로 변경

-- ================================================================
-- 1. refund_requests 테이블 수정
-- ================================================================

-- charge_history_id 외래키 제약조건 제거
ALTER TABLE refund_requests 
DROP CONSTRAINT IF EXISTS fk_refund_requests_charge_history_id;

-- charge_history_id 컬럼 제거
ALTER TABLE refund_requests 
DROP COLUMN IF EXISTS charge_history_id;

-- 사용자당 하나의 대기중인 환불 요청만 허용하는 제약조건 추가
DROP INDEX IF EXISTS idx_refund_requests_charge_history_id;

-- 사용자당 pending 상태 환불 요청 1개 제한
CREATE UNIQUE INDEX idx_refund_requests_user_pending 
ON refund_requests(user_id) 
WHERE status = 'pending';

-- 완료 확인
SELECT '✅ refund_requests 테이블 수정 완료' AS status;