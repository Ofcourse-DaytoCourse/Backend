-- PostgreSQL용 완전한 DDL 스크립트
-- 데이트 앱 데이터베이스 생성 스크립트
-- 작성일: 2025-07-07

-- 1. users 테이블 (사용자 정보)
CREATE TABLE users (
    user_id VARCHAR(36) NOT NULL,
    nickname VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    user_status VARCHAR(20),
    profile_detail JSONB,
    couple_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT uq_users_nickname UNIQUE (nickname)
);

-- 2. user_oauth 테이블 (OAuth 인증 정보)
CREATE TABLE user_oauth (
    oauth_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    provider_type VARCHAR(20) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT pk_user_oauth PRIMARY KEY (oauth_id),
    CONSTRAINT fk_user_oauth_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT
);

-- 3. place_category 테이블 (장소 카테고리)
CREATE TABLE place_category (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT uq_place_category_name UNIQUE (category_name)
);

-- 4. places 테이블 (장소 정보)
CREATE TABLE places (
    place_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255),
    kakao_url VARCHAR(500),
    phone VARCHAR(30),
    is_parking BOOLEAN DEFAULT FALSE NOT NULL,
    is_open BOOLEAN DEFAULT TRUE NOT NULL,
    open_hours VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    price JSONB DEFAULT '[]',
    description TEXT,
    summary TEXT,
    info_urls JSONB DEFAULT '[]',
    category_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT pk_places PRIMARY KEY (place_id),
    CONSTRAINT fk_places_category_id FOREIGN KEY (category_id) REFERENCES place_category(category_id)
);

-- 5. place_category_relations 테이블 (장소-카테고리 다대다 관계)
CREATE TABLE place_category_relations (
    id SERIAL PRIMARY KEY,
    place_id VARCHAR(50) NOT NULL,
    category_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_place_category_relations_place_id FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    CONSTRAINT fk_place_category_relations_category_id FOREIGN KEY (category_id) REFERENCES place_category(category_id) ON DELETE CASCADE
);

-- 6. couples 테이블 (커플 정보)
CREATE TABLE couples (
    couple_id SERIAL PRIMARY KEY,
    user1_id VARCHAR(36) NOT NULL,
    user2_id VARCHAR(36) NOT NULL,
    user1_nickname VARCHAR(50) NOT NULL,
    user2_nickname VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_couples_user1_id FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_couples_user2_id FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 7. couple_requests 테이블 (커플 요청)
CREATE TABLE couple_requests (
    request_id SERIAL PRIMARY KEY,
    requester_id VARCHAR(36) NOT NULL,
    partner_nickname VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_couple_requests_requester_id FOREIGN KEY (requester_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 8. courses 테이블 (데이트 코스)
CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    total_duration INTEGER,
    estimated_cost INTEGER,
    is_shared_with_couple BOOLEAN DEFAULT FALSE NOT NULL,
    comments JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_courses_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 9. course_places 테이블 (코스-장소 연결)
CREATE TABLE course_places (
    course_place_id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    place_id VARCHAR(50) NOT NULL,
    sequence_order INTEGER NOT NULL,
    estimated_duration INTEGER,
    estimated_cost INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT uq_course_sequence_order UNIQUE (course_id, sequence_order),
    CONSTRAINT fk_course_places_course_id FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_places_place_id FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE
);

-- 10. comments 테이블 (댓글)
CREATE TABLE comments (
    comment_id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    nickname VARCHAR(50) NOT NULL,
    comment TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_comments_course_id FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 11. chat_sessions 테이블 (채팅 세션)
CREATE TABLE chat_sessions (
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    session_title VARCHAR(200),
    session_status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    messages JSONB DEFAULT '[]',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT pk_chat_sessions PRIMARY KEY (session_id),
    CONSTRAINT fk_chat_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT
);

-- 인덱스 생성
CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_nickname ON users(nickname);
CREATE INDEX idx_users_email ON users(email);

CREATE INDEX idx_user_oauth_oauth_id ON user_oauth(oauth_id);
CREATE INDEX idx_user_oauth_user_id ON user_oauth(user_id);
CREATE INDEX idx_user_oauth_provider ON user_oauth(provider_type, provider_user_id);

CREATE INDEX idx_place_category_category_id ON place_category(category_id);
CREATE INDEX idx_place_category_name ON place_category(category_name);

CREATE INDEX idx_places_place_id ON places(place_id);
CREATE INDEX idx_places_name ON places(name);
CREATE INDEX idx_places_category_id ON places(category_id);
CREATE INDEX idx_places_location ON places(latitude, longitude);

CREATE INDEX idx_place_category_relations_id ON place_category_relations(id);
CREATE INDEX idx_place_category_relations_place_category ON place_category_relations(place_id, category_id);
CREATE INDEX idx_place_category_relations_place_priority ON place_category_relations(place_id, priority);
CREATE INDEX idx_place_category_relations_category_priority ON place_category_relations(category_id, priority);

CREATE INDEX idx_couples_couple_id ON couples(couple_id);
CREATE INDEX idx_couples_user1_id ON couples(user1_id);
CREATE INDEX idx_couples_user2_id ON couples(user2_id);

CREATE INDEX idx_couple_requests_request_id ON couple_requests(request_id);
CREATE INDEX idx_couple_requests_requester_id ON couple_requests(requester_id);
CREATE INDEX idx_couple_requests_partner_nickname ON couple_requests(partner_nickname);
CREATE INDEX idx_couple_requests_status ON couple_requests(status);

CREATE INDEX idx_courses_course_id ON courses(course_id);
CREATE INDEX idx_courses_user_id ON courses(user_id);
CREATE INDEX idx_courses_title ON courses(title);
CREATE INDEX idx_courses_created_at ON courses(created_at);

CREATE INDEX idx_course_places_course_place_id ON course_places(course_place_id);
CREATE INDEX idx_course_places_course_id ON course_places(course_id);
CREATE INDEX idx_course_places_place_id ON course_places(place_id);
CREATE INDEX idx_course_places_sequence_order ON course_places(course_id, sequence_order);

CREATE INDEX idx_comments_comment_id ON comments(comment_id);
CREATE INDEX idx_comments_course_id ON comments(course_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_timestamp ON comments(timestamp);

CREATE INDEX idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_status ON chat_sessions(session_status);
CREATE INDEX idx_chat_sessions_last_activity ON chat_sessions(last_activity_at);

-- 데이터 무결성을 위한 추가 제약조건
ALTER TABLE users ADD CONSTRAINT chk_users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' OR email IS NULL OR email = '');
ALTER TABLE users ADD CONSTRAINT chk_users_user_status CHECK (user_status IN ('active', 'inactive', 'suspended', 'deleted') OR user_status IS NULL);

ALTER TABLE user_oauth ADD CONSTRAINT chk_user_oauth_provider_type CHECK (provider_type IN ('kakao', 'google', 'naver', 'apple'));

ALTER TABLE places ADD CONSTRAINT chk_places_latitude CHECK (latitude >= -90 AND latitude <= 90);
ALTER TABLE places ADD CONSTRAINT chk_places_longitude CHECK (longitude >= -180 AND longitude <= 180);

ALTER TABLE place_category_relations ADD CONSTRAINT chk_place_category_relations_priority CHECK (priority >= 1 AND priority <= 10);

ALTER TABLE couple_requests ADD CONSTRAINT chk_couple_requests_status CHECK (status IN ('pending', 'accepted', 'rejected', 'cancelled'));

ALTER TABLE courses ADD CONSTRAINT chk_courses_total_duration CHECK (total_duration >= 0);
ALTER TABLE courses ADD CONSTRAINT chk_courses_estimated_cost CHECK (estimated_cost >= 0);

ALTER TABLE course_places ADD CONSTRAINT chk_course_places_sequence_order CHECK (sequence_order >= 1);
ALTER TABLE course_places ADD CONSTRAINT chk_course_places_estimated_duration CHECK (estimated_duration >= 0);
ALTER TABLE course_places ADD CONSTRAINT chk_course_places_estimated_cost CHECK (estimated_cost >= 0);

ALTER TABLE chat_sessions ADD CONSTRAINT chk_chat_sessions_session_status CHECK (session_status IN ('ACTIVE', 'INACTIVE', 'EXPIRED', 'DELETED'));

-- 트리거 함수 생성 (updated_at 자동 갱신)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_oauth_updated_at 
    BEFORE UPDATE ON user_oauth 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_places_updated_at 
    BEFORE UPDATE ON places 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_courses_updated_at 
    BEFORE UPDATE ON courses 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 초기 카테고리 데이터 삽입
INSERT INTO place_category (category_name) VALUES 
('음식점'),
('카페'),
('엔터테인먼트'),
('문화시설'),
('쇼핑'),
('술집'),
('야외활동'),
('휴식시설'),
('주차장'),
('기타');

-- 데이터베이스 통계 업데이트
ANALYZE;

-- 스크립트 실행 완료 메시지
SELECT 'PostgreSQL 데이터베이스 스키마 생성 완료' AS status;