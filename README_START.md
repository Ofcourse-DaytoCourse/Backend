# 🚀 DaytoCourse 시작 가이드

## 백엔드 서버 시작

```bash
# 간단 시작 (자동으로 PostgreSQL도 시작)
./start_server.sh
```

또는

```bash
# 수동 시작
docker compose up -d postgres  # PostgreSQL 시작
python main.py                 # FastAPI 서버 시작
```

## 프론트엔드 시작

```bash
cd ../daytocourse-foretend
npm start
```

## 서버 주소
- 백엔드: http://localhost:8000
- 백엔드 API 문서: http://localhost:8000/docs  
- 프론트엔드: http://localhost:3000

## 문제 해결

### PostgreSQL 문제
```bash
docker compose down
docker compose up -d postgres
```

### 서버 중지
- FastAPI: Ctrl+C
- PostgreSQL: docker compose down

## 테스트용 사용자
- 이제 회원가입/로그인/프로필 수정이 모두 정상 작동합니다!
- SQLite → PostgreSQL 전환으로 ROLLBACK 이슈 해결 완료 ✅