-- 연인 관련 테이블 CASCADE 제약 조건 추가 마이그레이션
-- 회원 탈퇴 시 연인 데이터 자동 삭제를 위한 외래키 제약 조건 설정

-- 1. 기존 제약 조건 삭제 (있다면)
ALTER TABLE couples DROP CONSTRAINT IF EXISTS fk_couples_user1_id;
ALTER TABLE couples DROP CONSTRAINT IF EXISTS fk_couples_user2_id;
ALTER TABLE couple_requests DROP CONSTRAINT IF EXISTS fk_couple_requests_requester_id;
ALTER TABLE comments DROP CONSTRAINT IF EXISTS fk_comments_user_id;
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS fk_chat_sessions_user_id;

-- 2. 새로운 CASCADE 제약 조건 추가
-- couples 테이블 - 연인 관계 정보
ALTER TABLE couples 
ADD CONSTRAINT fk_couples_user1_id 
FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE couples 
ADD CONSTRAINT fk_couples_user2_id 
FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- couple_requests 테이블 - 연인 신청 정보
ALTER TABLE couple_requests 
ADD CONSTRAINT fk_couple_requests_requester_id 
FOREIGN KEY (requester_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- comments 테이블 - 댓글 정보
ALTER TABLE comments 
ADD CONSTRAINT fk_comments_user_id 
FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- chat_sessions 테이블 - 채팅 세션 정보
ALTER TABLE chat_sessions 
DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
ALTER TABLE chat_sessions 
ADD CONSTRAINT fk_chat_sessions_user_id 
FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- 3. 제약 조건 확인
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    tc.constraint_type,
    rc.delete_rule
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.table_name IN ('couples', 'couple_requests', 'comments', 'chat_sessions')
    AND tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, tc.constraint_name;