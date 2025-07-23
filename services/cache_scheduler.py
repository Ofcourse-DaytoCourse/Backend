import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from crud.crud_place import CRUDPlace
from crud.crud_shared_course import _generate_shared_courses_cache_key, get_shared_courses_stats
from db.session import SessionLocal
from typing import List
from utils.redis_client import redis_client

class CacheScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.crud_place = CRUDPlace()
        self.is_running = False
        
    def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return
            
        try:
            # 20분마다 캐시 갱신 작업 등록
            self.scheduler.add_job(
                func=self._refresh_popular_places_cache,
                trigger=IntervalTrigger(minutes=20),
                id='refresh_places_cache',
                name='장소 목록 캐시 갱신',
                replace_existing=True,
                max_instances=1  # 동시 실행 방지
            )
            
            self.scheduler.start()
            self.is_running = True
            print("✅ 캐시 스케줄러 시작 - 20분마다 캐시 갱신")
            
            # 서버 시작 시 초기 캐시 생성
            asyncio.create_task(self._initial_cache_warmup())
            
        except Exception as e:
            print(f"❌ 캐시 스케줄러 시작 실패: {e}")
    
    def stop(self):
        """스케줄러 정지"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print("🛑 캐시 스케줄러 정지")
    
    def _refresh_popular_places_cache(self):
        """인기 장소 + 커뮤니티 코스 캐시 갱신 (동기 함수 - 스케줄러용)"""
        try:
            print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 캐시 갱신 시작...")
            
            # 비동기 함수를 동기적으로 실행
            asyncio.run(self._async_refresh_all_cache())
            
            print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모든 캐시 갱신 완료")
            
        except Exception as e:
            print(f"❌ 캐시 갱신 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _async_refresh_all_cache(self):
        """비동기 캐시 갱신 로직 (장소 + 커뮤니티 코스)"""
        async with SessionLocal() as db:
            # 인기 장소 목록들 (주요 조합들)
            cache_combinations = [
                # 기본 인기 장소 (후기 많은 순)
                {'skip': 0, 'limit': 20, 'sort_by': 'review_count_desc'},
                {'skip': 0, 'limit': 50, 'sort_by': 'review_count_desc'},
                
                # 평점 높은 순
                {'skip': 0, 'limit': 20, 'sort_by': 'rating_desc'},
                
                # 최신순
                {'skip': 0, 'limit': 20, 'sort_by': 'latest'},
                
                # 이름순 (기본)
                {'skip': 0, 'limit': 20, 'sort_by': 'name'},
            ]
            
            refreshed_count = 0
            
            for params in cache_combinations:
                try:
                    # 기존 캐시 키 생성
                    cache_key = self.crud_place._generate_cache_key(
                        skip=params.get('skip', 0),
                        limit=params.get('limit', 20),
                        category_id=params.get('category_id'),
                        search=params.get('search'),
                        region=params.get('region'),
                        sort_by=params.get('sort_by', 'review_count_desc'),
                        min_rating=params.get('min_rating'),
                        has_parking=params.get('has_parking'),
                        has_phone=params.get('has_phone')
                    )
                    
                    # 기존 캐시 삭제
                    redis_client.delete(key=cache_key)
                    
                    # 새로운 데이터 조회 및 캐시 저장
                    places, total_count = await self.crud_place.get_places_with_filters(
                        db=db,
                        **params
                    )
                    
                    refreshed_count += 1
                    
                except Exception as e:
                    print(f"❌ 캐시 갱신 실패 (조합: {params}): {e}")
                    continue
            
            print(f"🔄 장소 캐시 {refreshed_count}개 조합 갱신 완료")
            
            # 커뮤니티 코스 캐시 갱신
            await self._refresh_shared_courses_cache(db)
            
            print("🔄 모든 캐시(장소 + 커뮤니티 코스) 갱신 완료")
    
    async def _refresh_shared_courses_cache(self, db):
        """커뮤니티 코스 캐시 갱신"""
        # 커뮤니티 코스 주요 조합들
        shared_course_combinations = [
            # 기본 구매 많은 순
            {'skip': 0, 'limit': 20, 'sort_by': 'purchase_count_desc'},
            {'skip': 0, 'limit': 50, 'sort_by': 'purchase_count_desc'},
            
            # 평점 높은 순
            {'skip': 0, 'limit': 20, 'sort_by': 'rating'},
            
            # 조회 많은 순
            {'skip': 0, 'limit': 20, 'sort_by': 'popular'},
            
            # 최신순
            {'skip': 0, 'limit': 20, 'sort_by': 'latest'},
        ]
        
        refreshed_count = 0
        
        for params in shared_course_combinations:
            try:
                # 기존 캐시 키 생성
                cache_key = _generate_shared_courses_cache_key(
                    skip=params.get('skip', 0),
                    limit=params.get('limit', 20),
                    sort_by=params.get('sort_by', 'purchase_count_desc'),
                    category=params.get('category'),
                    min_rating=params.get('min_rating')
                )
                
                # 기존 캐시 삭제
                redis_client.delete(key=cache_key)
                
                # 새로운 데이터 조회 및 캐시 저장
                courses, total_count = await get_shared_courses_stats(
                    db=db,
                    **params
                )
                
                refreshed_count += 1
                
            except Exception as e:
                print(f"❌ 커뮤니티 코스 캐시 갱신 실패 (조합: {params}): {e}")
                continue
        
        print(f"🔄 커뮤니티 코스 캐시 {refreshed_count}개 조합 갱신 완료")
    
    async def _initial_cache_warmup(self):
        """서버 시작 시 초기 캐시 생성"""
        try:
            print("🔥 서버 시작 - 초기 캐시 생성 중...")
            await asyncio.sleep(3)  # 서버 완전 시작 대기
            await self._async_refresh_all_cache()
            print("🔥 초기 캐시 생성 완료!")
            
        except Exception as e:
            print(f"❌ 초기 캐시 생성 실패: {e}")

# 전역 스케줄러 인스턴스
cache_scheduler = CacheScheduler()