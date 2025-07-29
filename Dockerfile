FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 환경변수 체크 스크립트 실행 후 서버 시작
CMD ["sh", "-c", "python -c 'import os; print(\"DATABASE_URL:\", os.getenv(\"DATABASE_URL\", \"NOT SET\"))' && python main.py"]