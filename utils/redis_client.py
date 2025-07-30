import redis
import json
import os
from typing import Optional, Any
from datetime import timedelta

class RedisClient:
    def __init__(self):
        # Redis 연결 설정 (환경변수에서 읽거나 기본값 사용)
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))
        redis_password = os.getenv('REDIS_PASSWORD')
        
        try:
            self.client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 연결 테스트
            self.client.ping()
            print(f"✅ Redis 연결 성공: {redis_host}:{redis_port}")
        except Exception as e:
            print(f"❌ Redis 연결 실패: {e}")
            print("⚠️ Redis 없이 동작 - 캐싱 비활성화")
            self.client = None
    
    def is_available(self) -> bool:
        """Redis 사용 가능 여부 확인"""
        return self.client is not None
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        if not self.is_available():
            return None
            
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Redis GET 오류: {e}")
            return None
    
    def set(self, key: str, value: Any, expire_minutes: int = None) -> bool:
        """캐시에 데이터 저장"""
        if not self.is_available():
            return False
            
        try:
            serialized_data = json.dumps(value, default=str, ensure_ascii=False)
            
            if expire_minutes:
                expire_seconds = expire_minutes * 60
                self.client.setex(key, expire_seconds, serialized_data)
                print(f"📝 Redis 캐시 저장: {key} (만료: {expire_minutes}분)")
            else:
                # 만료 시간 없음 (무제한 저장)
                self.client.set(key, serialized_data)
                print(f"📝 Redis 캐시 저장: {key} (무제한)")
            
            return True
        except Exception as e:
            print(f"Redis SET 오류: {e}")
            return False
    
    def delete(self, pattern: str = None, key: str = None) -> int:
        """캐시 삭제 (패턴 또는 특정 키)"""
        if not self.is_available():
            return 0
            
        try:
            if pattern:
                # 패턴 매칭으로 여러 키 삭제
                keys = self.client.keys(pattern)
                if keys:
                    deleted_count = self.client.delete(*keys)
                    print(f"🗑️ Redis 캐시 삭제: {deleted_count}개 키")
                    return deleted_count
                return 0
            elif key:
                # 특정 키 삭제
                deleted_count = self.client.delete(key)
                if deleted_count:
                    print(f"🗑️ Redis 캐시 삭제: {key}")
                return deleted_count
            return 0
        except Exception as e:
            print(f"Redis DELETE 오류: {e}")
            return 0
    
    def flush_all(self) -> bool:
        """모든 캐시 삭제"""
        if not self.is_available():
            return False
            
        try:
            self.client.flushdb()
            print("🧹 Redis 전체 캐시 삭제")
            return True
        except Exception as e:
            print(f"Redis FLUSH 오류: {e}")
            return False

# 전역 Redis 클라이언트 인스턴스
redis_client = RedisClient()