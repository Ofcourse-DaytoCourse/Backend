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
            # 10분마다 캐시 갱신 작업 등록
            self.scheduler.add_job(
                func=self._refresh_popular_places_cache,
                trigger=IntervalTrigger(minutes=10),
                id='refresh_places_cache',
                name='장소 목록 캐시 갱신',
                replace_existing=True,
                max_instances=1  # 동시 실행 방지
            )
            
            self.scheduler.start()
            self.is_running = True
            print("✅ 캐시 스케줄러 시작 - 10분마다 캐시 갱신")
            
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
        # 모든 shared_courses 관련 캐시를 먼저 삭제
        print("🗑️ 모든 shared_courses 캐시 삭제 중...")
        redis_client.delete(pattern="shared_courses_list:*")
        
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
                # 직접 DB에서 데이터 조회하여 캐시 강제 갱신
                from sqlalchemy import text
                
                # 기본 쿼리 (get_shared_courses_stats와 동일)
                query = """
                    SELECT shared_course_id as id, shared_course_id, title, shared_by_user_id, 
                           view_count, purchase_count, save_count, price, shared_at,
                           creator_rating, creator_review_text, buyer_review_count, 
                           avg_buyer_rating, overall_rating
                    FROM shared_course_stats 
                    WHERE 1=1
                """
                
                # 정렬 조건
                sort_by = params.get('sort_by', 'purchase_count_desc')
                if sort_by == "latest":
                    query += " ORDER BY shared_at DESC"
                elif sort_by == "popular":
                    query += " ORDER BY view_count DESC"
                elif sort_by == "rating":
                    query += " ORDER BY overall_rating DESC"
                elif sort_by == "purchases" or sort_by == "purchase_count_desc":
                    query += " ORDER BY purchase_count DESC"
                else:
                    query += " ORDER BY purchase_count DESC"
                
                # 페이징
                skip = params.get('skip', 0)
                limit = params.get('limit', 20)
                query += f" LIMIT {limit} OFFSET {skip}"
                
                # 데이터 조회
                result = await db.execute(text(query))
                raw_courses = result.fetchall()
                
                # 총 개수 조회
                count_result = await db.execute(text("SELECT COUNT(*) as total FROM shared_course_stats"))
                total_count = count_result.scalar()
                
                # 데이터 변환
                from crud.crud_shared_course import _convert_raw_to_dict
                courses = [_convert_raw_to_dict(row) for row in raw_courses]
                
                # 캐시 키 생성 및 저장
                cache_key = _generate_shared_courses_cache_key(
                    skip=skip,
                    limit=limit,
                    sort_by=sort_by,
                    category=params.get('category'),
                    min_rating=params.get('min_rating')
                )
                
                cache_data = {
                    'courses': courses,
                    'total_count': total_count
                }
                redis_client.set(cache_key, cache_data)
                print(f"💾 강제 캐시 갱신: {cache_key} ({len(courses)}개 코스)")
                
                refreshed_count += 1
                
            except Exception as e:
                print(f"❌ 커뮤니티 코스 캐시 갱신 실패 (조합: {params}): {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"🔄 커뮤니티 코스 캐시 {refreshed_count}개 조합 갱신 완료")
    
    async def _initial_cache_warmup(self):
        """서버 시작 시 초기 캐시 생성"""
        try:
            print("🔥 서버 시작 - 초기 캐시 생성 중...")
            
            # 서버 시작시 모든 shared_courses 캐시 삭제
            await self._clear_shared_courses_cache()
            
            await asyncio.sleep(3)  # 서버 완전 시작 대기
            await self._async_refresh_all_cache()
            print("🔥 초기 캐시 생성 완료!")
            
        except Exception as e:
            print(f"❌ 초기 캐시 생성 실패: {e}")
    
    async def _clear_shared_courses_cache(self):
        """서버 시작시 모든 shared_courses 캐시 삭제"""
        try:
            # Redis에서 shared_courses 관련 모든 캐시 키 조회
            import subprocess
            result = subprocess.run(['redis-cli', 'KEYS', '*shared*'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                cache_keys = result.stdout.strip().split('\n')
                
                # 각 캐시 키 삭제
                for key in cache_keys:
                    if key.strip():  # 빈 키 제외
                        redis_client.delete(key=key.strip())
                        print(f"🗑️ Redis 캐시 삭제: {key.strip()}")
                
                print(f"🗑️ 총 {len([k for k in cache_keys if k.strip()])}개 shared_courses 캐시 삭제 완료")
            else:
                print("🔍 삭제할 shared_courses 캐시가 없습니다")
                
        except Exception as e:
            print(f"❌ shared_courses 캐시 삭제 실패: {e}")
            # 실패해도 계속 진행

# 전역 스케줄러 인스턴스
cache_scheduler = CacheScheduler()