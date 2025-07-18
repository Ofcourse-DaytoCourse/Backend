# 데이트 앱 데이터베이스 ERD 문서

## 개요
이 문서는 데이트 앱 데이터베이스의 완전한 ERD(Entity Relationship Diagram) 구조를 설명합니다.

## 테이블 구조

### 1. users (사용자 정보)
- **Primary Key**: user_id (VARCHAR(36))
- **Fields**:
  - user_id: 사용자 고유 ID (UUID)
  - nickname: 사용자 닉네임 (UNIQUE)
  - email: 이메일 주소 (NULLABLE)
  - user_status: 사용자 상태 (active, inactive, suspended, deleted)
  - profile_detail: 프로필 상세 정보 (JSON)
  - couple_info: 커플 정보 (JSON)
  - created_at: 생성일시
  - updated_at: 수정일시

### 2. user_oauth (OAuth 인증 정보)
- **Primary Key**: oauth_id (VARCHAR(36))
- **Foreign Keys**: user_id → users.user_id
- **Fields**:
  - oauth_id: OAuth 고유 ID (UUID)
  - user_id: 사용자 ID 참조
  - provider_type: 인증 제공자 (kakao, google, naver, apple)
  - provider_user_id: 제공자별 사용자 ID
  - access_token: 액세스 토큰
  - refresh_token: 리프레시 토큰
  - token_expires_at: 토큰 만료 시간
  - created_at: 생성일시
  - updated_at: 수정일시

### 3. place_category (장소 카테고리)
- **Primary Key**: category_id (SERIAL/INTEGER)
- **Fields**:
  - category_id: 카테고리 고유 ID
  - category_name: 카테고리 명 (UNIQUE)
  - created_at: 생성일시

### 4. places (장소 정보)
- **Primary Key**: place_id (VARCHAR(50))
- **Foreign Keys**: category_id → place_category.category_id
- **Fields**:
  - place_id: 장소 고유 ID
  - name: 장소명
  - address: 주소
  - kakao_url: 카카오 URL
  - phone: 전화번호
  - is_parking: 주차 가능 여부
  - is_open: 영업 중 여부
  - open_hours: 영업 시간
  - latitude: 위도
  - longitude: 경도
  - price: 가격 정보 (JSON)
  - description: 설명
  - summary: 요약
  - info_urls: 정보 URL 목록 (JSON)
  - category_id: 카테고리 ID 참조
  - created_at: 생성일시
  - updated_at: 수정일시

### 5. place_category_relations (장소-카테고리 다대다 관계)
- **Primary Key**: id (SERIAL/INTEGER)
- **Foreign Keys**: 
  - place_id → places.place_id
  - category_id → place_category.category_id
- **Fields**:
  - id: 관계 고유 ID
  - place_id: 장소 ID 참조
  - category_id: 카테고리 ID 참조
  - priority: 우선순위 (1=1차 카테고리, 2=2차 카테고리)
  - created_at: 생성일시

### 6. couples (커플 정보)
- **Primary Key**: couple_id (SERIAL/INTEGER)
- **Foreign Keys**: 
  - user1_id → users.user_id
  - user2_id → users.user_id
- **Fields**:
  - couple_id: 커플 고유 ID
  - user1_id: 사용자1 ID 참조
  - user2_id: 사용자2 ID 참조
  - user1_nickname: 사용자1 닉네임
  - user2_nickname: 사용자2 닉네임
  - created_at: 생성일시

### 7. couple_requests (커플 요청)
- **Primary Key**: request_id (SERIAL/INTEGER)
- **Foreign Keys**: requester_id → users.user_id
- **Fields**:
  - request_id: 요청 고유 ID
  - requester_id: 요청자 ID 참조
  - partner_nickname: 파트너 닉네임
  - status: 요청 상태 (pending, accepted, rejected, cancelled)
  - requested_at: 요청일시

### 8. courses (데이트 코스)
- **Primary Key**: course_id (SERIAL/INTEGER)
- **Foreign Keys**: user_id → users.user_id
- **Fields**:
  - course_id: 코스 고유 ID
  - user_id: 사용자 ID 참조
  - title: 코스 제목
  - description: 코스 설명
  - total_duration: 총 소요 시간
  - estimated_cost: 예상 비용
  - is_shared_with_couple: 커플 공유 여부
  - comments: 댓글 목록 (JSON)
  - created_at: 생성일시
  - updated_at: 수정일시

### 9. course_places (코스-장소 연결)
- **Primary Key**: course_place_id (SERIAL/INTEGER)
- **Foreign Keys**: 
  - course_id → courses.course_id
  - place_id → places.place_id
- **Fields**:
  - course_place_id: 코스-장소 고유 ID
  - course_id: 코스 ID 참조
  - place_id: 장소 ID 참조
  - sequence_order: 순서
  - estimated_duration: 예상 소요 시간
  - estimated_cost: 예상 비용
  - created_at: 생성일시
- **Unique Constraint**: (course_id, sequence_order)

### 10. comments (댓글)
- **Primary Key**: comment_id (SERIAL/INTEGER)
- **Foreign Keys**: 
  - course_id → courses.course_id
  - user_id → users.user_id
- **Fields**:
  - comment_id: 댓글 고유 ID
  - course_id: 코스 ID 참조
  - user_id: 사용자 ID 참조
  - nickname: 사용자 닉네임
  - comment: 댓글 내용
  - timestamp: 댓글 작성일시

### 11. chat_sessions (채팅 세션)
- **Primary Key**: session_id (VARCHAR(100))
- **Foreign Keys**: user_id → users.user_id
- **Fields**:
  - session_id: 세션 고유 ID
  - user_id: 사용자 ID 참조
  - session_title: 세션 제목
  - session_status: 세션 상태 (ACTIVE, INACTIVE, EXPIRED, DELETED)
  - is_active: 활성 상태
  - messages: 메시지 목록 (JSON)
  - started_at: 시작일시
  - last_activity_at: 마지막 활동일시
  - expires_at: 만료일시

## 테이블 관계 (Relationships)

### 1:1 관계
- users ↔ user_oauth (사용자 - OAuth 정보)

### 1:N 관계
- users → couple_requests (사용자 - 커플 요청)
- users → courses (사용자 - 데이트 코스)
- users → comments (사용자 - 댓글)
- users → chat_sessions (사용자 - 채팅 세션)
- place_category → places (카테고리 - 장소)
- courses → course_places (코스 - 코스 장소)
- places → course_places (장소 - 코스 장소)
- courses → comments (코스 - 댓글)

### N:M 관계
- users ↔ users (couples를 통한 커플 관계)
- places ↔ place_category (place_category_relations를 통한 다중 카테고리 관계)

## 인덱스 전략

### 기본 인덱스
- 모든 Primary Key에 자동 인덱스 생성
- 모든 Foreign Key에 인덱스 생성

### 검색 성능 최적화 인덱스
- users: nickname, email
- places: name, location (latitude, longitude)
- courses: title, created_at
- comments: timestamp
- chat_sessions: last_activity_at

### 복합 인덱스
- place_category_relations: (place_id, category_id), (place_id, priority), (category_id, priority)
- course_places: (course_id, sequence_order)
- user_oauth: (provider_type, provider_user_id)

## 데이터 무결성 제약조건

### CHECK 제약조건
- users.email: 이메일 형식 검증
- users.user_status: 허용된 상태 값만 입력
- user_oauth.provider_type: 허용된 제공자만 입력
- places.latitude: -90 ~ 90 범위
- places.longitude: -180 ~ 180 범위
- place_category_relations.priority: 1 ~ 10 범위
- couple_requests.status: 허용된 상태 값만 입력
- courses.total_duration, estimated_cost: 0 이상
- course_places.sequence_order: 1 이상
- chat_sessions.session_status: 허용된 상태 값만 입력

### 참조 무결성
- CASCADE 삭제: 사용자 삭제 시 관련 데이터 연쇄 삭제
- RESTRICT 삭제: OAuth 정보, 채팅 세션은 사용자 삭제 시 제한

## 트리거

### 자동 타임스탬프 업데이트
- users, user_oauth, places, courses 테이블의 updated_at 컬럼 자동 갱신

## 성능 최적화

### PostgreSQL 최적화
- JSONB 타입 사용으로 JSON 데이터 효율적 저장
- 통계 정보 자동 업데이트 (ANALYZE)
- 적절한 인덱스 전략

### SQLite 최적화
- WAL 모드 사용으로 동시성 향상
- 메모리 캐시 크기 최적화
- 외래 키 제약조건 활성화

## 사용 방법

### PostgreSQL 데이터베이스 생성
```sql
-- create_database_postgresql.sql 파일 실행
psql -U username -d database_name -f create_database_postgresql.sql
```

### SQLite 데이터베이스 생성
```sql
-- create_database_sqlite.sql 파일 실행
sqlite3 database_name.db < create_database_sqlite.sql
```

## 주요 특징

1. **확장성**: 다양한 장소 카테고리와 사용자 프로필 지원
2. **유연성**: JSON 필드를 통한 동적 데이터 구조
3. **성능**: 적절한 인덱스와 제약조건으로 성능 최적화
4. **무결성**: 참조 무결성과 데이터 검증 제약조건
5. **호환성**: PostgreSQL과 SQLite 양쪽 모두 지원

이 ERD 구조는 데이트 앱의 모든 핵심 기능을 지원하며, 향후 확장에도 유연하게 대응할 수 있도록 설계되었습니다.