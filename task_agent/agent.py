"""
Task Agent 핵심 에이전트 v5
리팩토링된 업무지원 에이전트
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../unified_agent_system"))

from models import UserQuery, AutomationRequest, PersonaType, AutomationTaskType
try:
    from core.models import UnifiedResponse, AgentType, RoutingDecision, Priority
except ImportError:
    # 공통 모듈이 없는 경우 더미 클래스들
    class AgentType:
        TASK_AUTOMATION = "task_automation"
    
    class Priority:
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
    
    class RoutingDecision:
        def __init__(self, agent_type, confidence, reasoning, keywords, priority):
            self.agent_type = agent_type
            self.confidence = confidence
            self.reasoning = reasoning
            self.keywords = keywords
            self.priority = priority
    
    class UnifiedResponse:
        def __init__(self, conversation_id, agent_type, response, confidence, 
                     routing_decision, sources, metadata, processing_time, timestamp, alternatives):
            self.conversation_id = conversation_id
            self.agent_type = agent_type
            self.response = response
            self.confidence = confidence
            self.routing_decision = routing_decision
            self.sources = sources
            self.metadata = metadata
            self.processing_time = processing_time
            self.timestamp = timestamp
            self.alternatives = alternatives

from utils import TaskAgentLogger

# 공통 모듈 import
try:
    from utils import create_success_response, create_error_response
    from utils import get_or_create_conversation_session
except ImportError:
    def create_success_response(data, message="Success"):
        return {"success": True, "data": data, "message": message}
    
    def create_error_response(message, error_code="ERROR"):
        return {"success": False, "error": message, "error_code": error_code}
        
    def get_or_create_conversation_session(user_id, conversation_id):
        return {"conversation_id": conversation_id or 1}

# 서비스 레이어 import
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.automation_service import AutomationService
from services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

class TaskAgent:
    """Task Agent 핵심 클래스 (리팩토링됨)"""
    
    def __init__(self, llm_service: LLMService, rag_service: RAGService, 
                 automation_service: AutomationService, conversation_service: ConversationService):
        """에이전트 초기화 - 의존성 주입"""
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.automation_service = automation_service
        self.conversation_service = conversation_service
        
        logger.info("Task Agent v5 초기화 완료 (의존성 주입)")

    async def process_query(self, query: UserQuery) -> UnifiedResponse:
        """사용자 쿼리 처리 - 단순화된 워크플로우"""
        try:
            TaskAgentLogger.log_user_interaction(
                user_id=query.user_id,
                action="query_processing_start",
                details=f"persona: {query.persona}, message_length: {len(query.message)}"
            )
            
            # 1. 대화 세션 처리
            session_info = await self._ensure_conversation_session(query)
            query.conversation_id = session_info["conversation_id"]
            
            # 2. 대화 히스토리 조회
            conversation_history = await self.conversation_service.get_history(query.conversation_id)
            
            # 3. 사용자 메시지 저장
            await self.conversation_service.save_message(
                query.conversation_id, query.message, "user"
            )
            
            # 4. 의도 분석
            intent_analysis = await self.llm_service.analyze_intent(
                query.message, query.persona, conversation_history
            )
            
            # 5. 워크플로우 결정 및 처리
            response = await self._route_and_process(query, intent_analysis, conversation_history)
            
            # 6. 에이전트 응답 저장
            await self.conversation_service.save_message(
                query.conversation_id, response.response, "agent", "task_agent"
            )
            
            TaskAgentLogger.log_user_interaction(
                user_id=query.user_id,
                action="query_processing_completed",
                details=f"intent: {response.metadata.get('intent', 'unknown')}"
            )
            
            return response
                
        except Exception as e:
            logger.error(f"쿼리 처리 실패: {e}")
            return self._create_error_response(query, str(e))

    async def _ensure_conversation_session(self, query: UserQuery) -> Dict[str, Any]:
        """대화 세션 확보"""
        try:
            user_id_int = int(query.user_id)
            session_info = get_or_create_conversation_session(
                user_id_int, query.conversation_id
            )
            return session_info
        except Exception as e:
            logger.error(f"대화 세션 처리 실패: {e}")
            raise Exception("대화 세션 생성에 실패했습니다")

    async def _route_and_process(self, query: UserQuery, intent_analysis: Dict, 
                                conversation_history: List[Dict] = None) -> UnifiedResponse:
        """워크플로우 라우팅 및 처리"""
        try:
            # 자동화 의도 확인
            automation_intent = await self.llm_service.analyze_automation_intent(
                query.message, conversation_history
            )
            
            if automation_intent["is_automation"]:
                # 자동화 워크플로우
                return await self._handle_automation_workflow(
                    query, automation_intent, intent_analysis, conversation_history
                )
            else:
                # 일반 상담 워크플로우
                return await self._handle_consultation_workflow(
                    query, intent_analysis, conversation_history
                )
                
        except Exception as e:
            logger.error(f"워크플로우 라우팅 실패: {e}")
            return self._create_error_response(query, str(e))

    async def _handle_automation_workflow(self, query: UserQuery, automation_intent: Dict,
                                    intent_analysis: Dict, conversation_history: List[Dict] = None) -> UnifiedResponse:
        """자동화 워크플로우 처리"""
        try:
            automation_type = automation_intent["automation_type"]
            
            # 현재 메시지에서 자동화 정보 추출
            extracted_info = await self.llm_service.extract_automation_info(
                query.message, automation_type, conversation_history
            )
            
            # extracted_info가 None인 경우 처리
            if extracted_info is None:
                extracted_info = {}
                logger.warning(f"자동화 정보 추출 실패, 빈 딕셔너리로 초기화: {automation_type}")
            
            # 필수 정보 체크
            missing_fields = self._check_missing_fields(extracted_info, automation_type)
            
            if not missing_fields:
                if automation_type == "todo_list":
                    # Google Tasks API로 작업 목록 및 작업 생성
                    return await self._handle_todo_list_creation(query, extracted_info, intent_analysis)
                # 모든 정보가 있으면 자동화 작업 등록
                return await self._register_automation_task(
                    query, automation_type, extracted_info, intent_analysis
                )
            else:
                # 부족한 정보 요청
                return self._request_missing_info(
                    query, automation_type, extracted_info, missing_fields, intent_analysis
                )
            
        except Exception as e:
            logger.error(f"자동화 워크플로우 처리 실패: {e}")
            return self._create_error_response(query, str(e))

    async def _handle_consultation_workflow(self, query: UserQuery, intent_analysis: Dict,
                                          conversation_history: List[Dict] = None) -> UnifiedResponse:
        """일반 상담 워크플로우 처리"""
        try:
            # # 지식 검색
            # search_result = await self.rag_service.search_knowledge(
            #     query.message, query.persona, intent_analysis.get("intent")
            # )
            
            # 응답 생성
            response_text = await self.llm_service.generate_response(
                query.message, query.persona, intent_analysis["intent"], 
                "", conversation_history
            )
            
            # 응답 생성
            return self._create_consultation_response(
                query, response_text, intent_analysis, ""
            )
            
        except Exception as e:
            logger.error(f"상담 워크플로우 처리 실패: {e}")
            return self._create_error_response(query, str(e))

    async def _handle_todo_list_creation(self, query: UserQuery, extracted_info: Dict[str, Any], 
                                       intent_analysis: Dict) -> UnifiedResponse:
        """TODO 리스트 생성 처리"""
        try:
            user_id = int(query.user_id)
            
            # 1. 작업 목록(tasklist) 생성
            tasklist_title = extracted_info.get('title', '새 작업 목록')
            tasklist_id = await self._create_google_tasklist(user_id, tasklist_title)
            
            if not tasklist_id:
                return self._create_error_response(query, "작업 목록 생성에 실패했습니다.")
            
            # 2. 세부 작업들 생성
            tasks = extracted_info.get('tasks', [])
            if not tasks and extracted_info.get('task_items'):
                # task_items가 있는 경우 tasks로 변환
                tasks = extracted_info['task_items']
            
            created_tasks = []
            for task in tasks:
                task_title = task.get('title', task.get('name', '제목 없음'))
                task_notes = task.get('notes', task.get('description', ''))
                task_due = task.get('due', task.get('due_date', None))
                
                task_result = await self._create_google_task(
                    user_id, tasklist_id, task_title, task_notes, task_due
                )
                if task_result:
                    created_tasks.append(task_result)
            
            # 3. 성공 응답 생성
            success_message = self._create_todo_success_message(
                tasklist_title, len(created_tasks), created_tasks[:3]  # 최대 3개만 표시
            )
            
            return self._create_automation_response(
                query, success_message, intent_analysis, 
                None, "todo_list", True
            )
            
        except Exception as e:
            logger.error(f"TODO 리스트 생성 실패: {e}")
            return self._create_error_response(query, f"TODO 리스트 생성 중 오류가 발생했습니다: {str(e)}")
        
    async def _create_google_tasklist(self, user_id: int, title: str) -> Optional[str]:
        """Google Tasks 작업 목록 생성"""
        try:
            api_base_url = os.getenv("TASK_AGENT_API_URL", "https://localhost:8005")
            url = f"{api_base_url}/google/tasks/lists"
            
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    url,
                    params={
                        "user_id": user_id,
                        "title": title
                    },  # title과 user_id 모두 쿼리 파라미터로
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("id")
                else:
                    logger.error(f"작업 목록 생성 실패: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Google Tasks 목록 생성 API 호출 실패: {e}")
            return None
    
    async def _create_google_task(self, user_id: int, tasklist_id: str, title: str, 
                                 notes: Optional[str] = None, due: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Google Tasks 작업 생성"""
        try:
            api_base_url = os.getenv("TASK_AGENT_API_URL", "https://localhost:8005")
            url = f"{api_base_url}/google/tasks"
            
            params = {
                "tasklist_id": tasklist_id,
                "title": title,
                "user_id": user_id
            }
            
            if notes:
                params["notes"] = notes
            if due:
                params["due"] = due
            
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    url,
                    params=params,  # 모든 파라미터를 쿼리로 전송
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result
                elif response.status_code == 401:
                    logger.error(f"인증 오류: 사용자 {user_id}의 Google 토큰이 만료되었거나 유효하지 않습니다.")
                    return None
                else:
                    logger.error(f"작업 생성 실패: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Google Tasks 작업 생성 API 호출 실패: {e}")
            return None
    
    def _create_todo_success_message(self, tasklist_title: str, task_count: int, 
                                   sample_tasks: List[Dict[str, Any]]) -> str:
        """TODO 리스트 생성 성공 메시지 생성"""
        message = f"✅ '{tasklist_title}' 작업 목록이 성공적으로 생성되었습니다!\n\n"
        message += f"📝 총 {task_count}개의 작업이 등록되었습니다.\n\n"
        
        if sample_tasks:
            message += "등록된 작업 (일부):\n"
            for i, task in enumerate(sample_tasks, 1):
                task_title = task.get('title', '제목 없음')
                message += f"{i}. {task_title}\n"
            
            if task_count > len(sample_tasks):
                message += f"... 외 {task_count - len(sample_tasks)}개\n"
        
        message += "\n🔗 Google Tasks에서 확인하실 수 있습니다."
        return message
    
    # ===== 일정 기반 자동화 처리 =====
    
    async def _is_schedule_based_request(self, message: str) -> bool:
        """일정 기반 자동 등록 요청인지 판단"""
        try:
            schedule_keywords = [
                "지금 짜준 일정", "위에서 말한 일정", "방금 짜준 일정",
                "아까 이야기한 일정", "대화에서 언급한 일정",
                "기반으로 캘린더", "기반으로 일정", "기반으로 등록",
                "짜준 일정 캘린더", "짜준 일정 등록",
                "위 일정을 캘린더", "위 일정을 등록"
            ]
            
            message_lower = message.lower()
            for keyword in schedule_keywords:
                if keyword in message_lower:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"일정 기반 요청 판단 실패: {e}")
            return False
    
    def _check_missing_fields(self, extracted_info: Dict[str, Any], automation_type: str) -> List[str]:
        """필수 필드 체크 - 단건/다건 통합 처리"""
        required_fields = {
            "calendar_sync": ["title", "start_time"],
            "send_email": ["to_emails", "subject", "body"]
        }
        
        required = required_fields.get(automation_type, [])
        
        # 단건/다건 통합 처리
        if automation_type == "calendar_sync":
            schedules = extracted_info.get('schedules', [])
            # 단건인 경우: schedules 키가 없어서 모든 필드가 누락으로 처리되는 문제가 있네요. 이를 해결하기 위해 단건 데이터를 배열로 정규화하는 로직을 추가하겠습니다.
            if not schedules and any(field in extracted_info for field in required):
                schedules = [extracted_info]
            # schedules 키가 없고 필수 필드도 없으면 빈 배열로 처리
            elif not schedules:
                return required  # 스케줄이 없으면 모든 필드가 누락
            
            # 모든 스케줄에서 누락된 필드 확인
            missing = set()
            for schedule in schedules:
                for field in required:
                    if not schedule.get(field):
                        missing.add(field)
            return list(missing)
        
        elif automation_type == "send_email":
            emails = extracted_info.get('emails', [])
            # 단건인 경우 배열로 변환
            if not emails and any(field in extracted_info for field in required):
                emails = [extracted_info]
            elif not emails:
                return required
            
            missing = set()
            for email in emails:
                for field in required:
                    if not email.get(field):
                        missing.add(field)
            return list(missing)
        
        elif automation_type == "todo_list":
            # 새로운 JSON 구조: {"title": "작업 목록 제목", "tasks": [...]}
            missing = []
            
            # 1. 작업 목록 제목 체크 (필수)
            if not extracted_info.get('title'):
                missing.append('title')
            
            # 2. 작업 배열 체크
            tasks = extracted_info.get('tasks', [])
            if not tasks:
                missing.append('tasks')  # 작업이 없으면 tasks 필드가 누락
            else:
                # 각 작업에서 title 필드 체크 (작업의 필수 필드)
                task_missing = False
                for task in tasks:
                    if not task.get('title'):
                        task_missing = True
                        break
                if task_missing:
                    missing.append('task_title')  # 작업 제목이 누락된 경우
            
            return missing
        
        # 기타 타입의 경우 단일 항목 처리
        missing = []
        for field in required:
            if not extracted_info.get(field):
                missing.append(field)
        
        return missing

    def _generate_automation_title(self, automation_type: str, extracted_info: Dict[str, Any]) -> str:
        """자동화 작업 제목 생성 - 다중 항목 지원"""
        if automation_type == "calendar_sync":
            schedules = extracted_info.get('schedules', [])
            if schedules:
                if len(schedules) == 1:
                    return schedules[0].get("title", "일정 등록")
                else:
                    return f"일정 {len(schedules)}개 등록"
            return extracted_info.get("title", "일정 등록")
        
        elif automation_type == "send_email":
            emails = extracted_info.get('emails', [])
            if emails:
                if len(emails) == 1:
                    return f"이메일: {emails[0].get('subject', '제목 없음')}"
                else:
                    return f"이메일 {len(emails)}개 발송"
            return f"이메일: {extracted_info.get('subject', '제목 없음')}"
        
        elif automation_type == "send_message":
            posts = extracted_info.get('posts', [])
            if posts:
                if len(posts) == 1:
                    platform = posts[0].get('platform', '메시지')
                    return f"{platform} 발송"
                else:
                    return f"메시지 {len(posts)}개 발송"
            return f"{extracted_info.get('platform', '메시지')} 발송"
        
        elif automation_type == "todo_list":
            if isinstance(extracted_info, list):
                if len(extracted_info) == 1:
                    return f"할일: {extracted_info[0].get('title', '작업')}"
                else:
                    return f"할일 {len(extracted_info)}개 등록"
            return f"할일: {extracted_info.get('title', '작업')}"
        
        elif automation_type == "send_reminder":
            return f"리마인더: {extracted_info.get('message', '알림')}"
        
        return "자동화 작업"

    def _create_automation_success_message(self, automation_type: str, 
                                         automation_response, extracted_info: Dict[str, Any]) -> str:
        """자동화 성공 메시지 생성 - 단건/다건 통합 처리"""
        type_names = {
            "calendar_sync": "일정 등록",
            "send_email": "이메일 발송",
            "send_reminder": "리마인더",
            "send_message": "메시지 발송",
            "todo_list": "할일 등록"
        }
        
        type_name = type_names.get(automation_type, "자동화 작업")
        
        # 다중 항목 개수 확인
        item_count = self._get_item_count(extracted_info, automation_type)
        
        if item_count > 1:
            message = f"✅ {type_name} {item_count}개가 성공적으로 등록되었습니다!\n\n"
        else:
            message = f"✅ {type_name} 자동화가 성공적으로 등록되었습니다!\n\n"
        
        # message += f"📋 **작업 정보:**\n"
        # message += f"• 작업 ID: {automation_response.task_id}\n"
        # message += f"• 상태: {automation_response.status.value}\n"
        
        # 단건/다건 통합 상세 정보 추가
        if automation_type == "calendar_sync":
            schedules = extracted_info.get('schedules', [])
            # 단건인 경우 배열로 변환
            if not schedules and extracted_info.get("title"):
                schedules = [extracted_info]
            
            if schedules:
                message += f"\n📅 **등록될 일정:**\n"
                for i, schedule in enumerate(schedules[:3], 1):  # 최대 3개만 표시
                    message += f"{i}. {schedule.get('title', '제목 없음')} - {schedule.get('start_time', '시간 미정')}\n"
                if len(schedules) > 3:
                    message += f"... 외 {len(schedules) - 3}개\n"
        
        elif automation_type == "send_email":
            emails = extracted_info.get('emails', [])
            # 단건인 경우 배열로 변환
            if not emails and extracted_info.get("subject"):
                emails = [extracted_info]
            
            if emails:
                message += f"\n📧 **발송될 이메일:**\n"
                for i, email in enumerate(emails[:3], 1):
                    to_emails = email.get('to_emails', [])
                    if isinstance(to_emails, str):
                        to_emails = [to_emails]
                    message += f"{i}. {email.get('subject', '제목 없음')} → {', '.join(to_emails)}\n"
                if len(emails) > 3:
                    message += f"... 외 {len(emails) - 3}개\n"
        
        elif automation_type == "send_message":
            posts = extracted_info.get('posts', [])
            # 단건인 경우 배열로 변환
            if not posts and extracted_info.get("platform"):
                posts = [extracted_info]
            
            if posts:
                message += f"\n📱 **발송될 메시지:**\n"
                for i, post in enumerate(posts[:3], 1):
                    content = post.get('content', '내용')
                    if len(content) > 50:
                        content = content[:50] + "..."
                    message += f"{i}. {post.get('platform', '플랫폼')} - {content}\n"
                if len(posts) > 3:
                    message += f"... 외 {len(posts) - 3}개\n"
        
        elif automation_type == "todo_list":
            tasks = extracted_info.get('tasks', [])
            # 단건인 경우 배열로 변환
            if not tasks and extracted_info.get("title"):
                tasks = [extracted_info]
            
            if tasks:
                message += f"\n✅ **등록될 할일:**\n"
                for i, todo in enumerate(tasks[:3], 1):
                    message += f"{i}. {todo.get('title', '제목 없음')}\n"
                if len(tasks) > 3:
                    message += f"... 외 {len(tasks) - 3}개\n"
            
            # 기존 로직 호환성 유지
            elif isinstance(extracted_info, list):
                message += f"\n✅ **등록될 할일:**\n"
                for i, todo in enumerate(extracted_info[:3], 1):
                    message += f"{i}. {todo.get('title', '제목 없음')}\n"
                if len(extracted_info) > 3:
                    message += f"... 외 {len(extracted_info) - 3}개\n"
        
        if hasattr(automation_response, 'scheduled_at') and automation_response.scheduled_at:
            message += f"\n⏰ **실행 예정:** {automation_response.scheduled_at}\n"
        
        return message
    def _format_extracted_info(self, extracted_info: Dict[str, Any], automation_type: str) -> str:
        """추출된 정보 포맷팅 - prompts.py의 구조를 반영"""
        field_labels = {
            "calendar_sync": {
                "title": "📅 제목", "start_time": "⏰ 시작시간", "end_time": "⏰ 종료시간",
                "description": "📝 설명", "location": "📍 장소", "timezone": "🌍 시간대",
                "all_day": "📆 종일 이벤트", "reminders": "🔔 알림", "recurrence": "🔄 반복"
            },
            "send_email": {
                "to_emails": "📧 받는사람", "subject": "📋 제목", "body": "📝 내용",
                "html_body": "🌐 HTML 내용", "attachments": "📎 첨부파일", 
                "cc_emails": "📧 참조", "bcc_emails": "📧 숨은참조",
                "from_email": "📤 발신자 이메일", "from_name": "👤 발신자 이름", "service": "🔧 이메일 서비스"
            }
        }
        
        labels = field_labels.get(automation_type, {})
        formatted = ""
        
        # 다중 항목 처리
        if automation_type == "calendar_sync":
            schedules = extracted_info["schedules"]
            for i, schedule in enumerate(schedules, 1):
                formatted += f"\n**📅 일정 {i}:**\n"
                for field, value in schedule.items():
                    if value and field in labels:
                        label = labels[field]
                        formatted += f"  {label}: {self._format_field_value(field, value)}\n"
        elif automation_type == "send_email":
            emails = extracted_info["emails"]
            for i, email in enumerate(emails, 1):
                formatted += f"\n**📧 이메일 {i}:**\n"
                for field, value in email.items():
                    if value and field in labels:
                        label = labels[field]
                        formatted += f"  {label}: {self._format_field_value(field, value)}\n"
        elif automation_type == "todo_list":
            # 작업 목록 제목 표시
            if "title" in extracted_info and extracted_info["title"]:
                formatted += f"\n**📋 작업 목록:** {extracted_info['title']}\n"
            
            # 각 작업 표시
            tasks = extracted_info.get("tasks", [])
            for i, task in enumerate(tasks, 1):
                formatted += f"\n**✅ 작업 {i}:**\n"
                # title은 필수 필드
                if "title" in task:
                    formatted += f"  📝 제목: {task['title']}\n"
                # 선택적 필드들
                if task.get("notes"):
                    formatted += f"  📝 상세 설명: {task['notes']}\n"
                if task.get("due"):
                    formatted += f"  ⏰ 마감일: {self._format_field_value('due', task['due'])}\n"
        else:
            # 단일 항목 처리
            for field, value in extracted_info.items():
                if value and field in labels:
                    label = labels[field]
                    formatted += f"• {label}: {self._format_field_value(field, value)}\n"
        
        return formatted

    def _format_field_value(self, field: str, value: Any) -> str:
        """필드 값 포맷팅 헬퍼 메서드"""
        if isinstance(value, list):
            if field == "reminders":
                return ", ".join([f"{r.get('minutes', 0)}분 전 {r.get('method', 'popup')}" for r in value])
            elif field == "recurrence":
                return ", ".join(value)
            else:
                return ", ".join(str(v) for v in value)
        elif isinstance(value, bool):
            return "예" if value else "아니오"
        else:
            return str(value)

    def _get_item_count(self, extracted_info: Dict[str, Any], automation_type: str) -> int:
        """추출된 정보의 항목 개수 반환 - 단건/다건 통합 처리"""
        if automation_type == "calendar_sync":
            schedules = extracted_info.get('schedules', [])
            # 단건인 경우 1개로 처리
            if not schedules and extracted_info.get("title"):
                return 1
            return len(schedules)
        
        elif automation_type == "send_email":
            emails = extracted_info.get('emails', [])
            # 단건인 경우 1개로 처리
            if not emails and extracted_info.get("subject"):
                return 1
            return len(emails)
        
        elif automation_type == "todo_list":
            tasks = extracted_info.get('tasks', [])
            # 단건인 경우 1개로 처리
            if not tasks and extracted_info.get("title"):
                return 1
            return len(tasks)
        
        return 1

    async def _register_automation_task(self, query: UserQuery, automation_type: str,
                                     extracted_info: Dict[str, Any], intent_analysis: Dict) -> UnifiedResponse:
        """자동화 작업 등록 - 다중 항목 지원"""
        try:
            # if automation_type == "todo_list":
            #     extracted_info = extracted_info.get('tasks', [])
            # 다중 항목인 경우 각각 개별 작업으로 등록
            item_count = self._get_item_count(extracted_info, automation_type)
            
            if item_count > 1:
                return await self._register_multiple_automation_tasks(
                    query, automation_type, extracted_info, intent_analysis
                )
            else:
                # 단일 항목 처리 (기존 로직)
                # 577번째 줄 수정
                automation_request = AutomationRequest(
                    user_id=int(query.user_id),
                    task_type=AutomationTaskType(automation_type),  # enum으로 변환
                    title=self._generate_automation_title(automation_type, extracted_info),
                    task_data=extracted_info,
                    scheduled_at=extracted_info.get("scheduled_at")
                )
                
                automation_response = await self.automation_service.create_task(automation_request)
                
                success_message = self._create_automation_success_message(
                    automation_type, automation_response, extracted_info
                )
                
                return self._create_automation_response(
                    query, success_message, intent_analysis, 
                    automation_response.task_id, automation_type, True
                )
                
        except Exception as e:
            logger.error(f"자동화 작업 등록 실패: {e}")
            return self._create_error_response(query, f"자동화 작업 등록 실패: {str(e)}")

    async def _register_multiple_automation_tasks(self, query: UserQuery, automation_type: str,
                                               extracted_info: Dict[str, Any], intent_analysis: Dict) -> UnifiedResponse:
        """다중 자동화 작업 등록"""
        try:
            task_ids = []
            
            # 각 항목별로 개별 작업 생성
            if automation_type == "calendar_sync":
                schedules = extracted_info.get('schedules', [])
                for schedule in schedules:
                    automation_request = AutomationRequest(
                        user_id=int(query.user_id),
                        task_type=AutomationTaskType(automation_type),
                        title=schedule.get('title', '일정 등록'),
                        task_data=schedule,
                        scheduled_at=schedule.get("scheduled_at")
                    )
                    response = await self.automation_service.create_task(automation_request)
                    task_ids.append(response.task_id)
            
            elif automation_type == "send_email":
                emails = extracted_info.get('emails', [])
                for email in emails:
                    automation_request = AutomationRequest(
                        user_id=int(query.user_id),
                        task_type=AutomationTaskType(automation_type),
                        title=f"이메일: {email.get('subject', '제목 없음')}",
                        task_data=email,
                        scheduled_at=email.get("scheduled_at")
                    )
                    response = await self.automation_service.create_task(automation_request)
                    task_ids.append(response.task_id)
            
            elif automation_type == "todo_list":
                tasks = extracted_info.get('tasks', [])
                for todo in tasks:
                    automation_request = AutomationRequest(
                        user_id=int(query.user_id),
                        task_type=AutomationTaskType(automation_type),
                        title=f"할일: {todo.get('title', '작업')}",
                        task_data=todo,
                        scheduled_at=todo.get("scheduled_at")
                    )
                    response = await self.automation_service.create_task(automation_request)
                    task_ids.append(response.task_id)
            
            # 마지막 응답을 기준으로 성공 메시지 생성
            success_message = self._create_automation_success_message(
                automation_type, response, extracted_info
            )
            
            return self._create_automation_response(
                query, success_message, intent_analysis, 
                task_ids, automation_type, True
            )
            
        except Exception as e:
            logger.error(f"다중 자동화 작업 등록 실패: {e}")
            return self._create_error_response(query, f"다중 자동화 작업 등록 실패: {str(e)}")

    def _request_missing_info(self, query: UserQuery, automation_type: str,
                            extracted_info: Dict[str, Any], missing_fields: List[str],
                            intent_analysis: Dict) -> UnifiedResponse:
        """부족한 정보 요청"""
        type_names = {
            "calendar_sync": "일정 등록",
            "send_email": "이메일 발송", 
            "todo_list": "할일 등록"
        }
        
        type_name = type_names.get(automation_type, "자동화")
        
        message = f"📝 {type_name} 설정을 도와드리겠습니다.\n\n"
        
        # 이미 입력된 정보가 있으면 표시
        if extracted_info:
            message += "✅ **확인된 정보:**\n"
            message += self._format_extracted_info(extracted_info, automation_type)
            message += "\n"
        
        # 부족한 정보 요청
        message += "❓ **추가로 필요한 정보:**\n"
        message += self._get_missing_fields_template(automation_type, missing_fields)
        
        return self._create_automation_response(
            query, message, intent_analysis, None, automation_type, False
        )

    def _get_missing_fields_template(self, automation_type: str, missing_fields: List[str]) -> str:
        """부족한 필드 템플릿 - prompts.py의 API 스펙을 반영"""
        templates = {
            "calendar_sync": {
                "title": "• 📅 **일정 제목**을 알려주세요\n  예: '팀 미팅', '프로젝트 회의'",
                "start_time": "• ⏰ **시작 시간**을 알려주세요\n  예: '내일 오후 2시', '2024-03-15 14:00', '다음주 월요일 9시'",
                "end_time": "• ⏰ **종료 시간**을 알려주세요 (선택사항)\n  예: '오후 3시', '1시간 후'",
                "description": "• 📝 **상세 설명**을 알려주세요 (선택사항)\n  예: '프로젝트 진행상황 논의', '준비사항: 노트북 지참'",
                "location": "• 📍 **장소**를 알려주세요 (선택사항)\n  예: '회의실 A', '강남역 스타벅스', 'https://zoom.us/j/123456789'",
                "timezone": "• 🌍 **시간대**를 알려주세요 (기본값: Asia/Seoul)",
                "all_day": "• 📆 **종일 이벤트** 여부를 알려주세요 (예/아니오)",
                "reminders": "• 🔔 **알림 설정**을 알려주세요 (선택사항)\n  예: '15분 전 알림', '1시간 전 팝업'",
                "recurrence": "• 🔄 **반복 설정**을 알려주세요 (선택사항)\n  예: '매주 월요일', '매월 첫째주'"
            },
            "send_email": {
                "to_emails": "• 📧 **받는 사람 이메일**을 알려주세요\n  예: 'user@example.com', '여러 명인 경우 쉼표로 구분'",
                "subject": "• 📋 **이메일 제목**을 알려주세요\n  예: '회의 안내', '프로젝트 업데이트'",
                "body": "• 📝 **이메일 내용**을 알려주세요\n  예: '안녕하세요. 다음 회의 일정을 안내드립니다.'",
                "html_body": "• 🌐 **HTML 형태 내용**을 알려주세요 (선택사항)",
                "attachments": "• 📎 **첨부파일 경로**를 알려주세요 (선택사항)\n  예: '/path/to/file.pdf'",
                "cc_emails": "• 📧 **참조 이메일**을 알려주세요 (선택사항)",
                "bcc_emails": "• 📧 **숨은참조 이메일**을 알려주세요 (선택사항)",
                "from_email": "• 📤 **발신자 이메일**을 알려주세요 (선택사항)",
                "from_name": "• 👤 **발신자 이름**을 알려주세요 (선택사항)",
                "service": "• 🔧 **이메일 서비스**를 알려주세요 (선택사항)\n  예: 'gmail', 'outlook'"
            },
            "todo_list": {
                "title": "• ✅ **작업 제목**을 알려주세요\n  예: '보고서 작성', '회의 준비'",
                "tasklist_id": "• 📋 **작업 목록 ID**를 알려주세요 (기본값: @default)",
                "notes": "• 📝 **작업 상세 설명**을 알려주세요 (선택사항)\n  예: '분기별 실적 보고서 작성', '참석자 명단 확인'",
                "due": "• ⏰ **마감일**을 알려주세요 (선택사항)\n  예: '내일까지', '2024-03-20', '다음주 금요일'"
            }
        }
        
        type_templates = templates.get(automation_type, {})
        
        result = ""
        for field in missing_fields:
            if field in type_templates:
                result += type_templates[field] + "\n\n"
        
        result += "💡 **자연스럽게 말씀해주시면 자동으로 인식합니다!**\n"
        result += "예: '내일 오후 2시에 팀 미팅 일정 잡아줘. 회의실 A에서 1시간 동안 할 예정이야.'"
        return result

    # ===== 응답 생성 메서드들 =====

    def _create_marketing_redirect_response(self, query: UserQuery, intent_analysis: Dict) -> UnifiedResponse:
        """마케팅 페이지 리다이렉션 응답"""
        routing_decision = RoutingDecision(
            agent_type=AgentType.TASK_AUTOMATION,
            confidence=1.0,
            reasoning="SNS 마케팅 페이지로 리다이렉션",
            keywords=["marketing", "sns"],
            priority=Priority.HIGH
        )
        
        return UnifiedResponse(
            conversation_id=int(query.conversation_id) if query.conversation_id else 0,
            agent_type=AgentType.TASK_AUTOMATION,
            response="SNS 마케팅 기능을 이용하시려면 마케팅 페이지로 이동해주세요.\n\n[마케팅 페이지로 이동하기](/marketing)",
            confidence=1.0,
            routing_decision=routing_decision,
            sources=None,
            metadata={
                "redirect": "/marketing",
                "automation_type": "publish_sns",
                "intent": intent_analysis["intent"],
                "automation_created": False
            },
            processing_time=0.0,
            timestamp=datetime.now(),
            alternatives=[]
        )

    def _create_consultation_response(self, query: UserQuery, response_text: str,
                                    intent_analysis: Dict, search_result: Dict) -> UnifiedResponse:
        """일반 상담 응답"""
        routing_decision = RoutingDecision(
            agent_type=AgentType.TASK_AUTOMATION,
            confidence=intent_analysis.get("confidence", 0.8),
            reasoning=f"일반 상담: {intent_analysis['intent']}",
            keywords=intent_analysis.get("keywords", []),
            priority=Priority.MEDIUM
        )
        
        return UnifiedResponse(
            conversation_id=int(query.conversation_id) if query.conversation_id else 0,
            agent_type=AgentType.TASK_AUTOMATION,
            response=response_text,
            confidence=intent_analysis.get("confidence", 0.8),
            routing_decision=routing_decision,
            sources="",
            metadata={
                "intent": intent_analysis["intent"],
                "persona": query.persona.value if hasattr(query.persona, 'value') else str(query.persona),
                "automation_created": False
            },
            processing_time=0.0,
            timestamp=datetime.now(),
            alternatives=[]
        )

    def _create_automation_response(self, query: UserQuery, message: str, intent_analysis: Dict,
                                  task_id: Optional[int], automation_type: str, 
                                  automation_created: bool) -> UnifiedResponse:
        """자동화 관련 응답"""
        routing_decision = RoutingDecision(
            agent_type=AgentType.TASK_AUTOMATION,
            confidence=intent_analysis.get("confidence", 0.9),
            reasoning=f"자동화 처리: {automation_type}",
            keywords=[automation_type],
            priority=Priority.HIGH if automation_created else Priority.MEDIUM
        )
        
        metadata = {
            "intent": intent_analysis["intent"],
            "automation_type": automation_type,
            "automation_created": automation_created
        }
        
        if task_id:
            metadata["task_id"] = task_id
        
        return UnifiedResponse(
            conversation_id=int(query.conversation_id) if query.conversation_id else 0,
            agent_type=AgentType.TASK_AUTOMATION,
            response=message,
            confidence=intent_analysis.get("confidence", 0.9),
            routing_decision=routing_decision,
            sources=None,
            metadata=metadata,
            processing_time=0.0,
            timestamp=datetime.now(),
            alternatives=[]
        )

    def _create_error_response(self, query: UserQuery, error_message: str) -> UnifiedResponse:
        """에러 응답"""
        routing_decision = RoutingDecision(
            agent_type=AgentType.TASK_AUTOMATION,
            confidence=0.0,
            reasoning="처리 중 오류 발생",
            keywords=[],
            priority=Priority.MEDIUM
        )
        
        return UnifiedResponse(
            conversation_id=int(query.conversation_id) if query.conversation_id else 0,
            agent_type=AgentType.TASK_AUTOMATION,
            response="죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            confidence=0.0,
            routing_decision=routing_decision,
            sources=None,
            metadata={"error": error_message, "automation_created": False},
            processing_time=0.0,
            timestamp=datetime.now(),
            alternatives=[]
        )

    # ===== 시스템 관리 =====

    async def get_status(self) -> Dict[str, Any]:
        """에이전트 상태 조회"""
        try:
            return {
                "agent_version": "5.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "llm_service": await self.llm_service.get_status(),
                    "rag_service": await self.rag_service.get_status(),
                    "automation_service": await self.automation_service.get_status(),
                    "conversation_service": await self.conversation_service.get_status()
                }
            }
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return {
                "agent_version": "5.0.0",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def cleanup_resources(self):
        """리소스 정리"""
        try:
            await self.automation_service.cleanup()
            await self.rag_service.cleanup()
            await self.llm_service.cleanup()
            logger.info("Task Agent 리소스 정리 완료")
        except Exception as e:
            logger.error(f"리소스 정리 실패: {e}")
