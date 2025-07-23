# -*- coding: utf-8 -*-
import openai
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config

# 모델 임포트
from models.place import Place
from models.place_category import PlaceCategory
from models.course import Course
from models.course_place import CoursePlace
from models.shared_course import SharedCourse

logger = logging.getLogger(__name__)

class ReviewFilterController:
    """GPT-3.5를 사용한 후기 진위성 검증 컨트롤러"""
    
    def __init__(self):
        self.client = None
        if config.config.get("openai_api_key"):
            from openai import OpenAI
            self.client = OpenAI(api_key=config.config["openai_api_key"])
        
        self.model = config.config.get("review_validation_model", "gpt-3.5-turbo")
        self.max_tokens = config.config.get("review_validation_max_tokens", 150)
        self.enabled = config.config.get("review_validation_enabled", True)
    
    async def validate_place_review(
        self, 
        db: AsyncSession, 
        place_id: str, 
        review_text: str
    ) -> Dict[str, Any]:
        """장소 후기 검증"""
        if not self.enabled or not self.client:
            return {"is_valid": True, "reason": "검증 시스템 비활성화"}
        
        try:
            # 장소 정보 조회
            place_info = await self._get_place_info(db, place_id)
            if not place_info:
                return {"is_valid": True, "reason": "장소 정보 없음"}
            
            # GPT 검증 요청
            prompt = self._create_place_review_prompt(place_info, review_text)
            result = self._call_gpt(prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"장소 후기 검증 오류: {str(e)}")
            print(f"🔍 장소 후기 검증 오류 상세: {str(e)}")
            return {"is_valid": True, "reason": "검증 시스템 오류"}
    
    async def validate_shared_course_review(
        self,
        db: AsyncSession,
        course_id: int,
        review_text: str
    ) -> Dict[str, Any]:
        """코스 공유 후기 검증"""
        if not self.enabled or not self.client:
            return {"is_valid": True, "reason": "검증 시스템 비활성화"}
        
        try:
            # 코스 정보 조회
            course_info = await self._get_course_info(db, course_id)
            if not course_info:
                return {"is_valid": True, "reason": "코스 정보 없음"}
            
            # GPT 검증 요청
            prompt = self._create_course_review_prompt(course_info, review_text)
            result = self._call_gpt(prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"코스 공유 후기 검증 오류: {str(e)}")
            return {"is_valid": True, "reason": "검증 시스템 오류"}
    
    async def validate_buyer_review(
        self,
        db: AsyncSession,
        shared_course_id: int,
        review_text: str
    ) -> Dict[str, Any]:
        """커뮤니티 코스 구매 후기 검증"""
        if not self.enabled or not self.client:
            return {"is_valid": True, "reason": "검증 시스템 비활성화"}
        
        try:
            # 공유 코스 정보 조회
            shared_course_info = await self._get_shared_course_info(db, shared_course_id)
            if not shared_course_info:
                return {"is_valid": True, "reason": "공유 코스 정보 없음"}
            
            # GPT 검증 요청
            prompt = self._create_buyer_review_prompt(shared_course_info, review_text)
            result = self._call_gpt(prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"구매 후기 검증 오류: {str(e)}")
            return {"is_valid": True, "reason": "검증 시스템 오류"}
    
    async def _get_place_info(self, db: AsyncSession, place_id: str) -> Optional[Dict]:
        """장소 정보 조회"""
        result = await db.execute(
            select(Place, PlaceCategory.category_name)
            .join(PlaceCategory, Place.category_id == PlaceCategory.category_id, isouter=True)
            .where(Place.place_id == place_id)
        )
        row = result.first()
        
        if not row:
            return None
        
        place, category_name = row
        return {
            "name": place.name,
            "address": place.address,
            "description": place.description,
            "summary": place.summary,
            "category_name": category_name or "기타"
        }
    
    async def _get_course_info(self, db: AsyncSession, course_id: int) -> Optional[Dict]:
        """코스 정보 조회"""
        # 코스 기본 정보
        course_result = await db.execute(
            select(Course).where(Course.course_id == course_id)
        )
        course = course_result.scalar_one_or_none()
        
        if not course:
            return None
        
        # 코스에 포함된 장소들 조회
        places_result = await db.execute(
            select(CoursePlace, Place, PlaceCategory.category_name)
            .join(Place, CoursePlace.place_id == Place.place_id)
            .join(PlaceCategory, Place.category_id == PlaceCategory.category_id, isouter=True)
            .where(CoursePlace.course_id == course_id)
            .order_by(CoursePlace.sequence_order)
        )
        
        places = []
        for row in places_result.fetchall():
            course_place, place, category_name = row
            places.append({
                "sequence": course_place.sequence_order,
                "name": place.name,
                "category": category_name or "기타",
                "estimated_duration": course_place.estimated_duration
            })
        
        return {
            "title": course.title,
            "description": course.description,
            "places": places
        }
    
    async def _get_shared_course_info(self, db: AsyncSession, shared_course_id: int) -> Optional[Dict]:
        """공유 코스 정보 조회"""
        shared_course_result = await db.execute(
            select(SharedCourse).where(SharedCourse.id == shared_course_id)
        )
        shared_course = shared_course_result.scalar_one_or_none()
        
        if not shared_course:
            return None
        
        # 연결된 코스 정보 조회
        course_info = await self._get_course_info(db, shared_course.course_id)
        
        return {
            "title": shared_course.title,
            "description": shared_course.description,
            "places": course_info["places"] if course_info else []
        }
    
    def _create_place_review_prompt(self, place_info: Dict, review_text: str) -> str:
        """장소 후기 검증용 프롬프트 생성"""
        return f"""당신은 데이트 코스 후기 진위성 검증 전문가입니다.

장소 정보:
- 이름: {place_info['name']}
- 주소: {place_info['address']}
- 카테고리: {place_info['category_name']}
- 설명: {place_info['description'] or '없음'}

사용자 후기:
"{review_text}"

이 후기가 해당 장소와 관련된 진짜 경험 후기인지 판단해주세요.

다음 기준으로 판단:
1. 후기가 해당 장소와 관련있는가?
2. 구체적인 경험이 포함되어 있는가?
3. 스팸, 광고, 의미없는 텍스트는 아닌가?
4. 욕설, 부적절한 내용은 없는가?

JSON 형태로 응답:
{{"is_valid": true/false, "reason": "판단 이유"}}"""
    
    def _create_course_review_prompt(self, course_info: Dict, review_text: str) -> str:
        """코스 후기 검증용 프롬프트 생성"""
        places_text = ", ".join([f"{p['name']}({p['category']})" for p in course_info['places']])
        
        return f"""당신은 데이트 코스 후기 진위성 검증 전문가입니다.

코스 정보:
- 제목: {course_info['title']}
- 설명: {course_info['description']}
- 포함 장소: {places_text}

사용자 후기:
"{review_text}"

이 후기가 해당 코스를 실제로 이용한 진짜 경험 후기인지 판단해주세요.

JSON 형태로 응답:
{{"is_valid": true/false, "reason": "판단 이유"}}"""
    
    def _create_buyer_review_prompt(self, shared_course_info: Dict, review_text: str) -> str:
        """구매 후기 검증용 프롬프트 생성"""
        places_text = ", ".join([f"{p['name']}({p['category']})" for p in shared_course_info['places']])
        
        return f"""당신은 데이트 코스 후기 진위성 검증 전문가입니다.

구매한 코스 정보:
- 제목: {shared_course_info['title']}
- 설명: {shared_course_info['description']}
- 포함 장소: {places_text}

구매자 후기:
"{review_text}"

이 후기가 해당 코스를 실제로 구매하고 이용한 진짜 경험 후기인지 판단해주세요.

JSON 형태로 응답:
{{"is_valid": true/false, "reason": "판단 이유"}}"""
    
    def _call_gpt(self, prompt: str) -> Dict[str, Any]:
        """GPT API 호출"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that responds only in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            
            # 기본값 설정
            if "is_valid" not in result:
                result["is_valid"] = True
            if "reason" not in result:
                result["reason"] = "응답 형식 오류"
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"GPT 응답 JSON 파싱 오류: {content}")
            print(f"🔍 GPT JSON 파싱 오류 상세: {str(e)}, 응답: {content}")
            return {"is_valid": True, "reason": "응답 파싱 오류"}
        except Exception as e:
            logger.error(f"GPT API 호출 오류: {str(e)}")
            print(f"🔍 GPT API 호출 오류 상세: {str(e)}")
            return {"is_valid": True, "reason": f"API 오류: {str(e)}"}

# 전역 인스턴스
review_filter = ReviewFilterController()