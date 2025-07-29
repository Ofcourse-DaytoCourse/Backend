-- 공유 코스 시스템에 필요한 테이블들만 생성
-- course_purchases 오류 해결을 위한 최소한의 마이그레이션

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

-- 2. 공유자 후기 테이블
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

-- 3. 코스 구매 테이블 (핵심!)
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

-- 4. 구매자 후기 테이블
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

CREATE INDEX IF NOT EXISTS idx_course_purchases_buyer_id ON course_purchases(buyer_user_id);
CREATE INDEX IF NOT EXISTS idx_course_purchases_course_id ON course_purchases(shared_course_id);

-- 생성 완료 메시지
SELECT 'shared_course 관련 테이블 생성 완료' AS status;