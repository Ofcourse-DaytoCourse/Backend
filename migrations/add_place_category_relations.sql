-- 장소-카테고리 다대다 관계 테이블 생성
-- 실행 순서: 1. 테이블 생성 -> 2. 기존 데이터 마이그레이션 -> 3. 기존 컬럼 삭제 (선택사항)

-- 1. place_category_relations 테이블 생성
CREATE TABLE IF NOT EXISTS place_category_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES place_category(category_id) ON DELETE CASCADE
);

-- 2. 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_place_category ON place_category_relations(place_id, category_id);
CREATE INDEX IF NOT EXISTS idx_place_priority ON place_category_relations(place_id, priority);
CREATE INDEX IF NOT EXISTS idx_category_priority ON place_category_relations(category_id, priority);

-- 3. 기존 places 테이블의 category_id 데이터를 새 테이블로 마이그레이션
INSERT INTO place_category_relations (place_id, category_id, priority)
SELECT place_id, category_id, 1
FROM places 
WHERE category_id IS NOT NULL;

-- 4. (선택사항) 기존 category_id 컬럼 삭제
-- 기존 시스템과의 호환성을 위해 일단 유지
-- ALTER TABLE places DROP COLUMN category_id;

-- 5. 확인 쿼리
SELECT 
    'Migration completed' as status,
    COUNT(*) as total_relations
FROM place_category_relations;