"""
의존성 주입 컨테이너
전체 시스템의 서비스들을 관리하고 의존성을 주입
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))

# 서비스 레이어 import
from services.task_agent_service import TaskAgentService
from services.automation_service import AutomationService
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.conversation_service import ConversationService
from automation_task.email_service import EmailService
from automation_task.instagram_service import InstagramPostingService
from automation_task.google_calendar_service import GoogleCalendarService

# 매니저 import
from automation import AutomationManager
from llm_handler import TaskAgentLLMHandler
from rag import TaskAgentRAGManager

# Add these imports at the top with other imports
from automation_task.common import get_oauth_http_client
from automation_task.common.utils import AutomationDateTimeUtils

logger = logging.getLogger(__name__)

@dataclass
class ServiceContainer:
    """서비스 컨테이너"""
    # 핵심 서비스들
    task_agent_service: TaskAgentService
    automation_service: AutomationService
    llm_service: LLMService
    rag_service: RAGService
    conversation_service: ConversationService
    
    # 외부 서비스들
    email_service: EmailService
    calendar_service: GoogleCalendarService
    instagram_service: InstagramPostingService  
    
    # 매니저들 (백워드 호환성)
    automation_manager: AutomationManager
    llm_handler: TaskAgentLLMHandler
    rag_manager: TaskAgentRAGManager

    async def get_health_status(self) -> Dict[str, Any]:
        """전체 서비스 헬스 상태"""
        try:
            health_status = {
                "overall_status": "healthy",
                "services": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # 각 서비스 상태 확인
            services = [
                ("task_agent", self.task_agent_service),
                ("automation", self.automation_service),
                ("llm", self.llm_service),
                ("rag", self.rag_service),
                ("conversation", self.conversation_service),
                ("email", self.email_service),
                ("calendar", self.calendar_service),
                ("instagram", self.instagram_service)
            ]
            
            all_healthy = True
            
            for service_name, service in services:
                try:
                    if hasattr(service, 'get_status'):
                        status = await service.get_status()
                        health_status["services"][service_name] = status
                        
                        if isinstance(status, dict) and status.get("status") != "healthy":
                            all_healthy = False
                    else:
                        health_status["services"][service_name] = {"status": "unknown"}
                        
                except Exception as e:
                    health_status["services"][service_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                    all_healthy = False
            
            health_status["overall_status"] = "healthy" if all_healthy else "degraded"
            return health_status
            
        except Exception as e:
            logger.error(f"헬스 상태 확인 실패: {e}")
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def get_detailed_status(self) -> Dict[str, Any]:
        """상세 상태 정보"""
        try:
            detailed_status = {
                "service_versions": {
                    "task_agent": "5.0.0",
                    "automation": "5.0.0"
                },
                "component_status": {},
                "metrics": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # 자동화 매니저 상태
            if hasattr(self.automation_manager, 'get_system_stats'):
                detailed_status["metrics"]["automation"] = await self.automation_manager.get_system_stats()
            
            # LLM 핸들러 상태
            if hasattr(self.llm_handler, 'get_status'):
                detailed_status["component_status"]["llm"] = self.llm_handler.get_status()
            
            # RAG 매니저 상태
            if hasattr(self.rag_manager, 'get_status'):
                detailed_status["component_status"]["rag"] = self.rag_manager.get_status()
            
            return detailed_status
            
        except Exception as e:
            logger.error(f"상세 상태 조회 실패: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """모든 서비스 정리"""
        try:
            cleanup_tasks = [
                ("automation_manager", self.automation_manager),
                ("task_agent_service", self.task_agent_service),
                ("automation_service", self.automation_service),
                ("llm_service", self.llm_service),
                ("rag_service", self.rag_service),
                ("conversation_service", self.conversation_service),
                ("email_service", self.email_service),
                ("calendar_service", self.calendar_service),
                ("instagram_service", self.instagram_service)
            ]
            
            for service_name, service in cleanup_tasks:
                try:
                    if hasattr(service, 'cleanup'):
                        await service.cleanup()
                        logger.info(f"{service_name} 정리 완료")
                except Exception as e:
                    logger.warning(f"{service_name} 정리 실패: {e}")
            
            logger.info("모든 서비스 정리 완료")
            
        except Exception as e:
            logger.error(f"서비스 정리 실패: {e}")


async def get_services() -> ServiceContainer:
    """서비스 컨테이너 팩토리"""
    try:
        logger.info("서비스 컨테이너 초기화 시작")
        
        # 1. 기본 매니저들 초기화 (기존 호환성)
        automation_manager = AutomationManager()
        llm_handler = TaskAgentLLMHandler()
        rag_manager = TaskAgentRAGManager()
        
        # 2. 서비스 레이어 초기화
        llm_service = LLMService(llm_handler)
        rag_service = RAGService(rag_manager)
        conversation_service = ConversationService()
        automation_service = AutomationService(automation_manager)
        
        # 3. Task Agent 서비스 초기화 (의존성 주입)
        task_agent_service = TaskAgentService(
            llm_service=llm_service,
            rag_service=rag_service,
            automation_service=automation_service,
            conversation_service=conversation_service
        )
        
        # 4. 외부 서비스들 초기화
        email_service = EmailService()
        
        # Fix: Initialize GoogleCalendarService with required parameters
        oauth_client = get_oauth_http_client()
        time_utils = AutomationDateTimeUtils()
        calendar_service = GoogleCalendarService(api=oauth_client, time_utils=time_utils)
        
        instagram_service = InstagramPostingService()
        
        # 5. 서비스 컨테이너 생성
        container = ServiceContainer(
            task_agent_service=task_agent_service,
            automation_service=automation_service,
            llm_service=llm_service,
            rag_service=rag_service,
            conversation_service=conversation_service,
            email_service=email_service,
            calendar_service=calendar_service,
            instagram_service=instagram_service,
            automation_manager=automation_manager,
            llm_handler=llm_handler,
            rag_manager=rag_manager
        )
        
        logger.info("서비스 컨테이너 초기화 완료")
        return container
        
    except Exception as e:
        logger.error(f"서비스 컨테이너 초기화 실패: {e}")
        raise
