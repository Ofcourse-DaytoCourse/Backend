-- 장소 테이블에 새 컬럼들 추가
-- 2025-07-27: 새 데이터 구조 지원을 위한 컬럼 추가

-- 새 컬럼들 추가 (IF NOT EXISTS 사용)
ALTER TABLE places ADD COLUMN IF NOT EXISTS business_hours JSONB DEFAULT '{}';
ALTER TABLE places ADD COLUMN IF NOT EXISTS menu_info JSONB DEFAULT '[]';
ALTER TABLE places ADD COLUMN IF NOT EXISTS homepage_url VARCHAR(500);
ALTER TABLE places ADD COLUMN IF NOT EXISTS kakao_category VARCHAR(100);
ALTER TABLE places ADD COLUMN IF NOT EXISTS major_category VARCHAR(50);
ALTER TABLE places ADD COLUMN IF NOT EXISTS middle_category VARCHAR(50);
ALTER TABLE places ADD COLUMN IF NOT EXISTS minor_category VARCHAR(50);

-- 인덱스 추가 (카테고리별 조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_places_major_category ON places(major_category);
CREATE INDEX IF NOT EXISTS idx_places_middle_category ON places(middle_category);
CREATE INDEX IF NOT EXISTS idx_places_minor_category ON places(minor_category);
CREATE INDEX IF NOT EXISTS idx_places_category_combo ON places(major_category, middle_category, minor_category);
CREATE INDEX IF NOT EXISTS idx_places_kakao_category ON places(kakao_category);

-- 기존 데이터 정리용 (옵션)
-- UPDATE places SET major_category = '카페' WHERE category_id = 8;
-- UPDATE places SET major_category = '음식점' WHERE category_id = 7;
-- UPDATE places SET major_category = '문화시설' WHERE category_id = 2;

COMMIT;