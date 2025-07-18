# 🐳 DaytoCourse Backend Docker 사용법

## 📦 Docker Hub에서 이미지 받아서 사용하기

### 1. 이미지 다운로드
```bash
docker pull juno4247/daytocourse-backend:latest
```

### 2. PostgreSQL + Backend 함께 실행 (추천)
```bash
# docker-compose.yml 파일이 있는 디렉토리에서
docker compose up -d
```

### 3. Backend만 단독 실행
```bash
# PostgreSQL이 이미 실행 중일 때
docker run -p 8000:8000 --name daytocourse-backend \
  juno4247/daytocourse-backend:latest
```

### 4. 환경변수와 함께 실행
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e KAKAO_REST_API_KEY="your-key" \
  --name daytocourse-backend \
  juno4247/daytocourse-backend:latest
```

## 🚀 빠른 시작 (start_server.sh 사용)

가장 쉬운 방법은 제공된 스크립트를 사용하는 것입니다:

```bash
./start_server.sh
```

이 스크립트는:
- PostgreSQL 컨테이너 자동 시작
- 데이터베이스 연결 확인
- FastAPI 서버 시작

## 🔧 개발 환경 설정

### 로컬에서 이미지 빌드
```bash
# 프로젝트 루트 디렉토리에서
docker build -t daytocourse-backend .
```

### 개발 모드로 실행 (볼륨 마운트)
```bash
docker run -p 8000:8000 \
  -v $(pwd):/app \
  daytocourse-backend
```

## 📊 접속 정보

- **API 서버**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5433

## 🐛 문제 해결

### 포트 충돌 시
```bash
# 다른 포트로 실행
docker run -p 8001:8000 juno4247/daytocourse-backend:latest
```

### 로그 확인
```bash
docker logs daytocourse-backend
```

### 컨테이너 내부 접근
```bash
docker exec -it daytocourse-backend bash
```

### 전체 재시작
```bash
docker compose down
docker compose up -d
```

## 📝 주의사항

1. **환경변수**: `.env` 파일이 필요합니다
2. **데이터베이스**: PostgreSQL이 먼저 실행되어야 합니다
3. **포트**: 8000번 포트가 사용 가능해야 합니다
4. **네트워크**: 같은 Docker 네트워크에서 DB와 통신합니다

## 🤝 팀원 간 공유

팀원들은 다음 명령어로 최신 버전을 받을 수 있습니다:

```bash
docker pull juno4247/daytocourse-backend:latest
docker compose down
docker compose up -d
```