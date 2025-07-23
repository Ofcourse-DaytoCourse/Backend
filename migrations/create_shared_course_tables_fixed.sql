-- 코스 공유 시스템 테이블 생성 마이그레이션 (수정버전)
-- 생성일: 2025-07-22
-- 설명: 전체 커뮤니티에 코스를 공유하고 수익을 얻는 생태계 구축

-- 1. 공유 코스 테이블
CREATE TABLE IF NOT EXISTS shared_courses (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    shared_by_user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    preview_image_url TEXT,
    price INTEGER DEFAULT 300,
    reward_per_save INTEGER DEFAULT 100,
    view_count INTEGER DEFAULT 0,
    purchase_count INTEGER DEFAULT 0,
    save_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 중복 공유 방지
    CONSTRAINT uq_shared_course UNIQUE(course_id)
);

-- 2. 공유자 후기 테이블 (코스 공유 시 필수 작성)
CREATE TABLE IF NOT EXISTS shared_course_reviews (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    shared_course_id INTEGER NOT NULL REFERENCES shared_courses(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT NOT NULL CHECK (LENGTH(TRIM(review_text)) >= 15),
    tags VARCHAR(255)[] DEFAULT '{}',
    photo_urls TEXT[] DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    credit_given BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 코스당 1개 후기만
    CONSTRAINT uq_course_owner_review UNIQUE(user_id, shared_course_id)
);

-- 3. 코스 구매 테이블
CREATE TABLE IF NOT EXISTS course_purchases (
    id SERIAL PRIMARY KEY,
    buyer_user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    shared_course_id INTEGER NOT NULL REFERENCES shared_courses(id),
    copied_course_id INTEGER NOT NULL REFERENCES courses(course_id),
    purchase_amount INTEGER NOT NULL DEFAULT 300,
    is_saved BOOLEAN DEFAULT FALSE,
    creator_reward_given BOOLEAN DEFAULT FALSE,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    saved_at TIMESTAMP,
    
    -- 중복 구매 방지
    CONSTRAINT uq_user_course_purchase UNIQUE(buyer_user_id, shared_course_id)
);

-- 4. 구매자 후기 테이블 (구매 후 실제 사용한 사람들의 후기)
CREATE TABLE IF NOT EXISTS course_buyer_reviews (
    id SERIAL PRIMARY KEY,
    buyer_user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    shared_course_id INTEGER NOT NULL REFERENCES shared_courses(id) ON DELETE CASCADE,
    purchase_id INTEGER NOT NULL REFERENCES course_purchases(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT NOT NULL CHECK (LENGTH(TRIM(review_text)) >= 15),
    tags VARCHAR(255)[] DEFAULT '{}',
    photo_urls TEXT[] DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    credit_given BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 구매자는 코스당 1개 후기만
    CONSTRAINT uq_buyer_course_review UNIQUE(buyer_user_id, shared_course_id)
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_shared_courses_user_id ON shared_courses(shared_by_user_id);
CREATE INDEX IF NOT EXISTS idx_shared_courses_active ON shared_courses(is_active);
CREATE INDEX IF NOT EXISTS idx_shared_courses_created_at ON shared_courses(shared_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_course_reviews_course_id ON shared_course_reviews(shared_course_id);
CREATE INDEX IF NOT EXISTS idx_shared_course_reviews_user_id ON shared_course_reviews(user_id);

CREATE INDEX IF NOT EXISTS idx_course_purchases_buyer_id ON course_purchases(buyer_user_id);
CREATE INDEX IF NOT EXISTS idx_course_purchases_course_id ON course_purchases(shared_course_id);

CREATE INDEX IF NOT EXISTS idx_course_buyer_reviews_course_id ON course_buyer_reviews(shared_course_id);
CREATE INDEX IF NOT EXISTS idx_course_buyer_reviews_buyer_id ON course_buyer_reviews(buyer_user_id);

-- 통계 뷰 생성 (성능 최적화)
CREATE OR REPLACE VIEW shared_course_stats AS
SELECT 
    sc.id as shared_course_id,
    sc.title,
    sc.shared_by_user_id,
    sc.view_count,
    sc.purchase_count,
    sc.save_count,
    sc.price,
    sc.shared_at,
    
    -- 공유자 후기
    scr.rating as creator_rating,
    scr.review_text as creator_review_text,
    
    -- 구매자 후기 통계
    COUNT(cbr.id) FILTER (WHERE cbr.is_deleted = FALSE) as buyer_review_count,
    ROUND(AVG(cbr.rating) FILTER (WHERE cbr.is_deleted = FALSE), 1) as avg_buyer_rating,
    
    -- 전체 평점 (공유자 + 구매자 평균)
    ROUND(
        CASE 
            WHEN scr.rating IS NOT NULL AND COUNT(cbr.id) FILTER (WHERE cbr.is_deleted = FALSE) > 0 
            THEN (scr.rating + AVG(cbr.rating) FILTER (WHERE cbr.is_deleted = FALSE)) / 2
            WHEN scr.rating IS NOT NULL 
            THEN scr.rating 
            WHEN COUNT(cbr.id) FILTER (WHERE cbr.is_deleted = FALSE) > 0 
            THEN AVG(cbr.rating) FILTER (WHERE cbr.is_deleted = FALSE)
            ELSE 0 
        END, 1
    ) as overall_rating
    
FROM shared_courses sc
LEFT JOIN shared_course_reviews scr ON sc.id = scr.shared_course_id AND scr.is_deleted = FALSE
LEFT JOIN course_buyer_reviews cbr ON sc.id = cbr.shared_course_id AND cbr.is_deleted = FALSE
WHERE sc.is_active = TRUE
GROUP BY sc.id, sc.title, sc.shared_by_user_id, sc.view_count, sc.purchase_count, sc.save_count, sc.price, sc.shared_at, scr.rating, scr.review_text;

-- 트리거: 통계 자동 업데이트
CREATE OR REPLACE FUNCTION update_shared_course_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- 구매 수 업데이트
    IF TG_TABLE_NAME = 'course_purchases' THEN
        UPDATE shared_courses 
        SET purchase_count = (
            SELECT COUNT(*) FROM course_purchases 
            WHERE shared_course_id = NEW.shared_course_id
        )
        WHERE id = NEW.shared_course_id;
        
        -- 저장 수 업데이트
        IF NEW.is_saved = TRUE AND (OLD IS NULL OR OLD.is_saved = FALSE) THEN
            UPDATE shared_courses 
            SET save_count = (
                SELECT COUNT(*) FROM course_purchases 
                WHERE shared_course_id = NEW.shared_course_id AND is_saved = TRUE
            )
            WHERE id = NEW.shared_course_id;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER IF NOT EXISTS trigger_update_purchase_stats
    AFTER INSERT OR UPDATE ON course_purchases
    FOR EACH ROW
    EXECUTE FUNCTION update_shared_course_stats();

COMMENT ON TABLE shared_courses IS '전체 커뮤니티에 공유된 코스들';
COMMENT ON TABLE shared_course_reviews IS '코스 공유자가 작성하는 필수 후기';
COMMENT ON TABLE course_purchases IS '코스 구매 및 저장 이력';
COMMENT ON TABLE course_buyer_reviews IS '구매자가 실제 사용 후 작성하는 후기';
COMMENT ON VIEW shared_course_stats IS '공유 코스 통계 정보 (성능 최적화용)';