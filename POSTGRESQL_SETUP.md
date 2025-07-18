# PostgreSQL 전환 가이드

## 🚀 실행 순서

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. Docker로 PostgreSQL 실행
```bash
# PostgreSQL 컨테이너 시작
docker-compose up -d postgres

# 컨테이너 상태 확인
docker-compose ps
```

### 3. 데이터베이스 스키마 생성
```bash
# 기존 SQLite 데이터 백업 (선택사항)
cp dev.db dev.db.backup

# PostgreSQL 스키마 생성 (자동으로 실행됨)
# docker-compose.yml에서 create_database_postgresql.sql이 자동 실행

# 또는 수동으로 실행
docker exec -i daytocourse-postgres psql -U app -d daytocourse < create_database_postgresql.sql
```

### 4. FastAPI 서버 재시작
```bash
# 기존 서버 종료 후 재시작
uvicorn main:app --reload
```

## ✅ 확인 방법

### PostgreSQL 연결 테스트
```bash
# PostgreSQL 컨테이너 접속
docker exec -it daytocourse-postgres psql -U app -d daytocourse

# 테이블 확인
\dt

# 종료
\q
```

### 로그 확인
```
# 성공한 로그 패턴
INFO sqlalchemy.engine.Engine BEGIN (implicit)
INFO sqlalchemy.engine.Engine SELECT users...
INFO sqlalchemy.engine.Engine COMMIT  # ← ROLLBACK이 COMMIT으로 변경됨!
```

## 🔄 롤백 방법 (문제 발생 시)

### SQLite로 되돌리기
```bash
# config.py 수정
"database_url": "sqlite+aiosqlite:///./dev.db"

# 서버 재시작
uvicorn main:app --reload
```

## 🎯 예상 결과

### BEFORE (SQLite 문제)
- ROLLBACK 반복 발생
- 커넥션 풀 에러
- 마이페이지 업데이트 실패

### AFTER (PostgreSQL 해결)
- COMMIT 정상 처리
- 동시 트랜잭션 지원
- 모든 기능 정상 작동

## 🚨 주의사항

1. **Docker 필수**: PostgreSQL이 Docker로 실행되어야 함
2. **포트 확인**: 5432 포트가 사용 가능해야 함
3. **데이터 마이그레이션**: 기존 SQLite 데이터는 별도 마이그레이션 필요

## 📞 문제 해결

### 포트 충돌 해결
```bash
# 기존 PostgreSQL 프로세스 종료
sudo lsof -ti:5432 | xargs kill -9

# Docker 컨테이너 재시작
docker-compose restart postgres
```

### 권한 문제 해결
```bash
# PostgreSQL 재설정
docker-compose down -v
docker-compose up -d postgres
```