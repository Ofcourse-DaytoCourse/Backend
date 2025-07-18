-- SQLite용 완전한 DDL 스크립트
-- 데이트 앱 데이터베이스 생성 스크립트
-- 작성일: 2025-07-07

-- SQLite 설정
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 1000000;
PRAGMA temp_store = MEMORY;

-- 1. users 테이블 (사용자 정보)
CREATE TABLE users (
    user_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    email TEXT,
    user_status TEXT,
    profile_detail TEXT, -- JSON 데이터를 TEXT로 저장
    couple_info TEXT, -- JSON 데이터를 TEXT로 저장
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    updated_at TEXT,
    
    PRIMARY KEY (user_id),
    UNIQUE (nickname),
    CHECK (email IS NULL OR email LIKE '%@%.%'),
    CHECK (user_status IS NULL OR user_status IN ('active', 'inactive', 'suspended', 'deleted'))
);

-- 2. user_oauth 테이블 (OAuth 인증 정보)
CREATE TABLE user_oauth (
    oauth_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    updated_at TEXT,
    
    PRIMARY KEY (oauth_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    CHECK (provider_type IN ('kakao', 'google', 'naver', 'apple'))
);

-- 3. place_category 테이블 (장소 카테고리)
CREATE TABLE place_category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    
    UNIQUE (category_name)
);

-- 4. places 테이블 (장소 정보)
CREATE TABLE places (
    place_id TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    kakao_url TEXT,
    phone TEXT,
    is_parking INTEGER DEFAULT 0 NOT NULL,
    is_open INTEGER DEFAULT 1 NOT NULL,
    open_hours TEXT,
    latitude REAL,
    longitude REAL,
    price TEXT DEFAULT '[]', -- JSON 데이터를 TEXT로 저장
    description TEXT,
    summary TEXT,
    info_urls TEXT DEFAULT '[]', -- JSON 데이터를 TEXT로 저장
    category_id INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    updated_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    
    PRIMARY KEY (place_id),
    FOREIGN KEY (category_id) REFERENCES place_category(category_id),
    CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
    CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),
    CHECK (is_parking IN (0, 1)),
    CHECK (is_open IN (0, 1))
);

-- 5. place_category_relations 테이블 (장소-카테고리 다대다 관계)
CREATE TABLE place_category_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES place_category(category_id) ON DELETE CASCADE,
    CHECK (priority >= 1 AND priority <= 10)
);

-- 6. couples 테이블 (커플 정보)
CREATE TABLE couples (
    couple_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id TEXT NOT NULL,
    user2_id TEXT NOT NULL,
    user1_nickname TEXT NOT NULL,
    user2_nickname TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 7. couple_requests 테이블 (커플 요청)
CREATE TABLE couple_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id TEXT NOT NULL,
    partner_nickname TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    requested_at TEXT DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (requester_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (status IN ('pending', 'accepted', 'rejected', 'cancelled'))
);

-- 8. courses 테이블 (데이트 코스)
CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    total_duration INTEGER,
    estimated_cost INTEGER,
    is_shared_with_couple INTEGER DEFAULT 0 NOT NULL,
    comments TEXT DEFAULT '[]', -- JSON 데이터를 TEXT로 저장
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    updated_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (total_duration IS NULL OR total_duration >= 0),
    CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    CHECK (is_shared_with_couple IN (0, 1))
);

-- 9. course_places 테이블 (코스-장소 연결)
CREATE TABLE course_places (
    course_place_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    place_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    estimated_duration INTEGER,
    estimated_cost INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    UNIQUE (course_id, sequence_order),
    CHECK (sequence_order >= 1),
    CHECK (estimated_duration IS NULL OR estimated_duration >= 0),
    CHECK (estimated_cost IS NULL OR estimated_cost >= 0)
);

-- 10. comments 테이블 (댓글)
CREATE TABLE comments (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    comment TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 11. chat_sessions 테이블 (채팅 세션)
CREATE TABLE chat_sessions (
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_title TEXT,
    session_status TEXT DEFAULT 'ACTIVE' NOT NULL,
    is_active INTEGER DEFAULT 1 NOT NULL,
    messages TEXT DEFAULT '[]', -- JSON 데이터를 TEXT로 저장
    started_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    last_activity_at TEXT DEFAULT (datetime('now', 'localtime')) NOT NULL,
    expires_at TEXT,
    
    PRIMARY KEY (session_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    CHECK (session_status IN ('ACTIVE', 'INACTIVE', 'EXPIRED', 'DELETED')),
    CHECK (is_active IN (0, 1))
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

-- updated_at 트리거 생성
CREATE TRIGGER update_users_updated_at 
    AFTER UPDATE ON users
    FOR EACH ROW
    WHEN NEW.updated_at IS OLD.updated_at
    BEGIN
        UPDATE users SET updated_at = datetime('now', 'localtime') WHERE user_id = NEW.user_id;
    END;

CREATE TRIGGER update_user_oauth_updated_at 
    AFTER UPDATE ON user_oauth
    FOR EACH ROW
    WHEN NEW.updated_at IS OLD.updated_at
    BEGIN
        UPDATE user_oauth SET updated_at = datetime('now', 'localtime') WHERE oauth_id = NEW.oauth_id;
    END;

CREATE TRIGGER update_places_updated_at 
    AFTER UPDATE ON places
    FOR EACH ROW
    WHEN NEW.updated_at IS OLD.updated_at
    BEGIN
        UPDATE places SET updated_at = datetime('now', 'localtime') WHERE place_id = NEW.place_id;
    END;

CREATE TRIGGER update_courses_updated_at 
    AFTER UPDATE ON courses
    FOR EACH ROW
    WHEN NEW.updated_at IS OLD.updated_at
    BEGIN
        UPDATE courses SET updated_at = datetime('now', 'localtime') WHERE course_id = NEW.course_id;
    END;

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

-- 데이터베이스 최적화
PRAGMA optimize;
VACUUM;

-- 스크립트 실행 완료 메시지
SELECT 'SQLite 데이터베이스 스키마 생성 완료' AS status;