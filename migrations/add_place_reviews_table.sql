-- place_reviews 테이블 생성
-- 장소별 후기 시스템을 위한 테이블

CREATE TABLE place_reviews (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    place_id VARCHAR(50) NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    tags VARCHAR(255)[] DEFAULT '{}',
    photo_urls TEXT[] DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 사용자당 장소별 1회만 후기 작성 가능
    CONSTRAINT uq_user_place_review UNIQUE(user_id, place_id)
);

-- 성능 최적화 인덱스
CREATE INDEX idx_place_reviews_place_id ON place_reviews(place_id);
CREATE INDEX idx_place_reviews_user_id ON place_reviews(user_id);
CREATE INDEX idx_place_reviews_rating ON place_reviews(rating);
CREATE INDEX idx_place_reviews_created_at ON place_reviews(created_at DESC);

-- 후기 통계를 위한 뷰 (선택사항)
CREATE VIEW place_review_stats AS
SELECT 
    place_id,
    COUNT(*) as review_count,
    ROUND(AVG(rating), 2) as average_rating,
    COUNT(*) FILTER (WHERE rating = 5) as rating_5_count,
    COUNT(*) FILTER (WHERE rating = 4) as rating_4_count,
    COUNT(*) FILTER (WHERE rating = 3) as rating_3_count,
    COUNT(*) FILTER (WHERE rating = 2) as rating_2_count,
    COUNT(*) FILTER (WHERE rating = 1) as rating_1_count
FROM place_reviews 
WHERE is_deleted = FALSE
GROUP BY place_id;