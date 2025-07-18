import json
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import desc, and_

from models.chat_session import ChatSession
from models.user import User
from schemas.chat import (
    ChatSessionCreate, 
    ChatMessageCreate, 
    UserProfile,
    ChatResponse,
    SessionInfo
)

# 에이전트 API 설정
AGENT_BASE_URL = "http://localhost:8001"
AGENT_TIMEOUT = 120  # 120초 타임아웃 (코스 추천은 시간이 오래 걸림)

class ChatCRUD:
    
    async def create_chat_session(
        self, 
        db: AsyncSession, 
        chat_data: ChatSessionCreate
    ) -> Optional[Dict[str, Any]]:
        """새 채팅 세션 생성 및 에이전트 API 호출"""
        try:
            # 에이전트 API 호출
            agent_response = await self._call_agent_new_session(chat_data)
            
            if not agent_response.get('success'):
                return None
            
            # DB에 세션 저장
            session_id = agent_response['session_id']
            initial_messages = [
                {
                    "message_id": 1,
                    "message_type": "USER",
                    "message_content": chat_data.initial_message,
                    "sent_at": datetime.now().isoformat()
                },
                {
                    "message_id": 2,
                    "message_type": "ASSISTANT",
                    "message_content": agent_response['response']['message'],
                    "sent_at": datetime.now().isoformat()
                }
            ]
            
            print(f"[DEBUG] 새 세션 생성 - 세션 ID: {session_id}")
            print(f"[DEBUG] 초기 메시지 개수: {len(initial_messages)}")
            print(f"[DEBUG] 초기 메시지: {initial_messages}")
            
            chat_session = ChatSession(
                session_id=session_id,
                user_id=chat_data.user_id,
                session_title=agent_response['session_info']['session_title'],
                session_status=agent_response['session_info']['session_status'],
                is_active=True,
                messages=initial_messages,
                started_at=datetime.now(),
                last_activity_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
            
            # JSON 필드 변경 감지를 위한 플래그
            from sqlalchemy.orm.attributes import flag_modified
            
            db.add(chat_session)
            await db.flush()  # 먼저 flush로 ID 할당
            flag_modified(chat_session, "messages")  # JSON 필드 변경 감지
            await db.commit()
            await db.refresh(chat_session)
            print(f"[DEBUG] 새 세션 저장 완료")
            print(f"[DEBUG] 저장 후 메시지 개수 확인: {len(chat_session.messages) if chat_session.messages else 0}")
            
            return agent_response
            
        except Exception as e:
            await db.rollback()
            print(f"채팅 세션 생성 오류: {e}")
            return None
    
    async def send_message(
        self, 
        db: AsyncSession, 
        message_data: ChatMessageCreate
    ) -> Optional[Dict[str, Any]]:
        """메시지 전송 및 에이전트 응답"""
        try:
            # 기존 세션 조회
            result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == message_data.session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return None
            
            # 에이전트 API 호출
            agent_response = await self._call_agent_send_message(message_data)
            
            if not agent_response.get('success'):
                return None
            
            # 메시지 추가
            messages = session.messages or []
            new_message_id = len(messages) + 1
            
            def safe_message_for_db(message):
                """DB 저장용 메시지 변환 - 버튼은 요약 텍스트로"""
                if isinstance(message, dict) and message.get('message_type') == 'buttons':
                    return message.get('question', '선택 옵션')
                return message
            
            messages.extend([
                {
                    "message_id": new_message_id,
                    "message_type": "USER",
                    "message_content": message_data.message,
                    "sent_at": datetime.now().isoformat()
                },
                {
                    "message_id": new_message_id + 1,
                    "message_type": "ASSISTANT",
                    "message_content": safe_message_for_db(agent_response['response']['message']),
                    "sent_at": datetime.now().isoformat()
                }
            ])
            
            # DB 업데이트
            print(f"[DEBUG] 메시지 저장 전 - 세션 ID: {session.session_id}")
            print(f"[DEBUG] 저장할 메시지 개수: {len(messages)}")
            print(f"[DEBUG] 저장할 메시지: {messages}")
            
            # JSON 필드 업데이트를 SQLAlchemy에 명시적으로 알리기
            from sqlalchemy.orm.attributes import flag_modified
            
            session.messages = messages
            flag_modified(session, "messages")  # JSON 필드 변경 감지
            session.last_activity_at = datetime.now()
            session.session_status = agent_response['session_info']['session_status']
            
            await db.commit()
            await db.refresh(session)  # 세션 새로고침
            print(f"[DEBUG] 메시지 저장 완료")
            print(f"[DEBUG] 저장 후 메시지 개수 확인: {len(session.messages) if session.messages else 0}")
            
            # 저장 여부 확인 및 자동 저장
            await self._handle_profile_save(db, agent_response, message_data.user_id)
            
            return agent_response
            
        except Exception as e:
            await db.rollback()
            print(f"메시지 전송 오류: {e}")
            return None
    
    async def start_recommendation(
        self, 
        db: AsyncSession, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """코스 추천 시작"""
        try:
            # 기존 세션 조회
            result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return None
            
            # 에이전트 API 호출
            agent_response = await self._call_agent_start_recommendation(session_id)
            print(f"[DEBUG] 추천 시작 - 에이전트 응답: {agent_response}")
            
            if not agent_response.get('success'):
                return agent_response
            
            # 세션 업데이트
            session.session_status = "COMPLETED"
            session.last_activity_at = datetime.now()
            
            # 추천 완료 메시지 추가
            messages = session.messages or []
            new_message_id = len(messages) + 1
            
            # 메시지 필드 확인 및 처리
            def safe_message_for_db(message):
                """DB 저장용 메시지 변환 - 버튼은 요약 텍스트로"""
                if isinstance(message, dict) and message.get('message_type') == 'buttons':
                    return message.get('question', '선택 옵션')
                return message
            
            message_content = agent_response.get('message') or agent_response.get('response', {}).get('message') or "코스 추천이 완료되었습니다!"
            
            messages.append({
                "message_id": new_message_id,
                "message_type": "ASSISTANT",
                "message_content": safe_message_for_db(message_content),
                "sent_at": datetime.now().isoformat(),
                "course_data": agent_response.get('course_data')
            })
            
            # JSON 필드 업데이트를 SQLAlchemy에 명시적으로 알리기
            from sqlalchemy.orm.attributes import flag_modified
            
            session.messages = messages
            flag_modified(session, "messages")  # JSON 필드 변경 감지
            
            await db.commit()
            
            # 저장 여부 확인 및 자동 저장 (user_id는 세션에서 추출)
            user_id = getattr(session, 'user_id', None)
            if user_id:
                await self._handle_profile_save(db, agent_response, user_id)
            
            return agent_response
            
        except Exception as e:
            await db.rollback()
            print(f"코스 추천 오류: {e}")
            return None
    
    async def get_user_sessions(
        self, 
        db: AsyncSession, 
        user_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """사용자 채팅 세션 목록 조회"""
        try:
            query = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.last_activity_at))
            
            if limit is not None:
                query = query.limit(limit)
            if offset > 0:
                query = query.offset(offset)
                
            result = await db.execute(query)
            sessions = result.scalars().all()
            
            session_list = []
            for session in sessions:
                messages = session.messages or []
                last_message = messages[-1] if messages else None
                
                session_list.append({
                    "session_id": session.session_id,
                    "session_title": session.session_title,
                    "session_status": session.session_status,
                    "created_at": session.started_at.isoformat(),
                    "last_activity_at": session.last_activity_at.isoformat(),
                    "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                    "message_count": len(messages),
                    "has_course": any(msg.get('course_data') for msg in messages),
                    "preview_message": str(last_message.get('message_content', ''))[:100] if last_message else ""
                })
            
            return session_list
            
        except Exception as e:
            print(f"세션 목록 조회 오류: {e}")
            return []
    
    async def get_session_detail(
        self, 
        db: AsyncSession, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """특정 세션 상세 조회"""
        try:
            print(f"[DEBUG] 세션 상세 조회 시작: {session_id}")
            
            # 세션 캐시 문제 해결을 위해 트랜잭션 강제 종료 후 새로운 조회
            try:
                await db.rollback()  # 기존 트랜잭션 롤백
            except:
                pass
            
            # 완전히 새로운 쿼리로 최신 데이터 조회
            result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                print(f"[DEBUG] 세션을 찾을 수 없음: {session_id}")
                return None
            
            print(f"[DEBUG] 세션 찾음: {session.session_id}")
            print(f"[DEBUG] 메시지 개수: {len(session.messages) if session.messages else 0}")
            print(f"[DEBUG] 메시지 내용: {session.messages}")
            
            return {
                "session": {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "session_title": session.session_title,
                    "session_status": session.session_status,
                    "started_at": session.started_at.isoformat(),
                    "last_activity_at": session.last_activity_at.isoformat(),
                    "expires_at": session.expires_at.isoformat() if session.expires_at else None
                },
                "messages": session.messages or []
            }
            
        except Exception as e:
            print(f"세션 상세 조회 오류: {e}")
            return None
    
    async def delete_session(
        self, 
        db: AsyncSession, 
        session_id: str
    ) -> bool:
        """채팅 세션 삭제"""
        try:
            result = await db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            await db.delete(session)
            await db.commit()
            
            return True
            
        except Exception as e:
            await db.rollback()
            print(f"세션 삭제 오류: {e}")
            return False
    
    # 에이전트 API 호출 메서드들
    async def _call_agent_new_session(self, chat_data: ChatSessionCreate) -> Dict[str, Any]:
        """에이전트 새 세션 API 호출"""
        # user_profile에서 빈값들을 필터링하고 필드명 매핑
        user_profile = {}
        if chat_data.user_profile:
            profile_dict = chat_data.user_profile.dict()
            print(f"[DEBUG] 받은 chat_data.user_profile: {profile_dict}")
            user_profile = self._filter_and_map_profile(profile_dict)
            print(f"[DEBUG] 필터링 후 user_profile: {user_profile}")
        
        payload = {
            "user_id": chat_data.user_id,  # UUID string 그대로 사용
            "initial_message": chat_data.initial_message,
            "user_profile": user_profile
        }
        
        return await self._make_agent_request("POST", "/chat/new-session", payload)
    
    async def _call_agent_send_message(self, message_data: ChatMessageCreate) -> Dict[str, Any]:
        """에이전트 메시지 전송 API 호출"""
        # user_profile에서 빈값들을 필터링하고 필드명 매핑
        user_profile = {}
        if message_data.user_profile:
            profile_dict = message_data.user_profile.dict()
            user_profile = self._filter_and_map_profile(profile_dict)
        
        payload = {
            "session_id": message_data.session_id,
            "message": message_data.message,
            "user_id": message_data.user_id,  # UUID string 그대로 사용
            "user_profile": user_profile
        }
        
        return await self._make_agent_request("POST", "/chat/send-message", payload)
    
    async def _call_agent_start_recommendation(self, session_id: str) -> Dict[str, Any]:
        """에이전트 추천 시작 API 호출"""
        payload = {"session_id": session_id}
        
        return await self._make_agent_request("POST", "/chat/start-recommendation", payload)
    
    async def _make_agent_request(self, method: str, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트 API 공통 요청 메서드"""
        try:
            timeout = aiohttp.ClientTimeout(total=AGENT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{AGENT_BASE_URL}{endpoint}"
                
                async with session.request(method, url, json=payload) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"에이전트 API 오류: {response.status} - {error_text}")
                        return {"success": False, "error": error_text}
                        
        except asyncio.TimeoutError:
            print(f"에이전트 API 타임아웃: {endpoint}")
            return {"success": False, "error": "API 타임아웃"}
        except Exception as e:
            print(f"에이전트 API 호출 오류: {e}")
            return {"success": False, "error": str(e)}
    
    def _filter_and_map_profile(self, profile_dict: Dict[str, Any]) -> Dict[str, Any]:
        """유저 프로필 빈값 필터링 및 필드명 매핑"""
        # 프론트엔드 필드명 -> 메인 에이전트 필드명 매핑 (기존 시스템 호환)
        field_mapping = {
            "age": "age",
            "gender": "gender", 
            "mbti": "mbti",
            "address": "address",
            "description": "description",
            "car_owned": "car_owned",
            "general_preferences": "general_preferences"
        }
        
        filtered_profile = {}
        for key, value in profile_dict.items():
            # 빈값 필터링: None, 빈 문자열, 빈 리스트 제외
            if self._is_valid_value(value):
                # 필드명 매핑 적용
                mapped_key = field_mapping.get(key, key)
                filtered_profile[mapped_key] = value
        
        return filtered_profile
    
    def _is_valid_value(self, value: Any) -> bool:
        """값이 유효한지 검사 (빈값이 아닌지)"""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        if isinstance(value, list) and len(value) == 0:
            return False
        if isinstance(value, dict) and len(value) == 0:
            return False
        return True
    
    async def get_session_profile_data(self, session_id: str) -> Dict[str, Any]:
        """메인 에이전트에서 세션의 프로필 데이터 가져오기"""
        try:
            # 메인 에이전트 API 호출
            response = await self._make_agent_request("GET", f"/chat/session-profile/{session_id}")
            if response.get("success"):
                return response.get("profile_data", {})
            return {}
        except Exception as e:
            print(f"프로필 데이터 가져오기 오류: {e}")
            return {}
    
    async def _handle_profile_save(self, db: AsyncSession, agent_response: Dict[str, Any], user_id: str):
        """에이전트 응답에서 저장 여부를 확인하고 자동으로 프로필 저장"""
        try:
            # 에이전트 응답에서 save_profile 확인
            save_profile = agent_response.get('save_profile', False)
            session_id = agent_response.get('session_id')
            
            if save_profile and session_id:
                print(f"[DEBUG] 자동 프로필 저장 시작: user_id={user_id}, session_id={session_id}")
                
                # 세션 프로필 데이터 가져오기
                profile_data = await self.get_session_profile_data(session_id)
                
                if profile_data:
                    # 메인 에이전트 필드명 -> 기존 필드명으로 변환 (마이페이지와 동일)
                    db_profile_data = {
                        "age": profile_data.get("age"),
                        "gender": profile_data.get("gender"),
                        "mbti": profile_data.get("mbti"),
                        "car_owned": profile_data.get("car_owned"),
                        "general_preferences": ",".join(profile_data.get("general_preferences", []))
                    }
                    
                    # 유저 프로필 업데이트
                    from crud.crud_user import user_crud
                    updated_user = await user_crud.update_profile_detail(db, user_id, db_profile_data)
                    
                    if updated_user:
                        print(f"[DEBUG] 프로필 자동 저장 성공: {db_profile_data}")
                    else:
                        print(f"[DEBUG] 프로필 자동 저장 실패")
                else:
                    print(f"[DEBUG] 저장할 프로필 데이터 없음")
            else:
                if not save_profile:
                    print(f"[DEBUG] 사용자가 프로필 저장을 거부함")
                    
        except Exception as e:
            print(f"[ERROR] 자동 프로필 저장 중 오류: {e}")

# 싱글톤 인스턴스
chat_crud = ChatCRUD()