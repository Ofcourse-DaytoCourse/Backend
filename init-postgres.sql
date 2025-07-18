-- PostgreSQL 초기화 스크립트
-- app 사용자가 이미 존재하는지 확인하고 데이터베이스에 권한 부여

-- app 사용자에게 daytocourse 데이터베이스 권한 부여
GRANT ALL PRIVILEGES ON DATABASE daytocourse TO app;

-- 스키마 권한 부여
GRANT ALL PRIVILEGES ON SCHEMA public TO app;

-- 기존 테이블들이 있다면 권한 부여
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app;

-- 미래에 생성될 테이블들에 대한 기본 권한 설정
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app;

SELECT 'PostgreSQL app 사용자 권한 설정 완료' as status;