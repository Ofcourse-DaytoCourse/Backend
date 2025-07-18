#!/bin/bash

echo "🚀 DaytoCourse 백엔드 서버 시작 스크립트"
echo ""

# 1. PostgreSQL 컨테이너 확인 및 시작
echo "📦 PostgreSQL 컨테이너 상태 확인..."
if ! docker compose ps postgres | grep -q "Up"; then
    echo "🔄 PostgreSQL 컨테이너 시작 중..."
    docker compose up -d postgres
    echo "⏳ PostgreSQL 초기화 대기 중... (10초)"
    sleep 10
else
    echo "✅ PostgreSQL 이미 실행 중"
fi

# 2. 데이터베이스 연결 테스트
echo ""
echo "🔗 데이터베이스 연결 테스트..."
if docker compose exec postgres psql -U daytocourse_user -d daytocourse -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ 데이터베이스 연결 성공"
else
    echo "❌ 데이터베이스 연결 실패"
    echo "💡 해결방법: docker compose down && docker compose up -d postgres"
    exit 1
fi

# 3. FastAPI 서버 시작
echo ""
echo "🌟 FastAPI 서버 시작..."
echo "📍 서버 주소: http://localhost:8000"
echo "📖 API 문서: http://localhost:8000/docs"
echo ""
echo "🛑 서버 중지: Ctrl+C"
echo ""

python main.py