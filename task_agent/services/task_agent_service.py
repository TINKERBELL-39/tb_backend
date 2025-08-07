"""
Task Agent 서비스
에이전트의 비즈니스 로직을 처리하는 서비스 레이어
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from models import UserQuery
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
from agent import TaskAgent

logger = logging.getLogger(__name__)

class TaskAgentService:
    """Task Agent 서비스 - 의존성 주입 기반"""
    
    def __init__(self, llm_service, rag_service, automation_service, conversation_service):
        """서비스 초기화 - 의존성 주입"""
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.automation_service = automation_service
        self.conversation_service = conversation_service
        
        # 실제 TaskAgent 인스턴스 생성
        self.agent = TaskAgent(
            llm_service=llm_service,
            rag_service=rag_service,
            automation_service=automation_service,
            conversation_service=conversation_service
        )
        
        logger.info("TaskAgentService 초기화 완료")

    async def process_query(self, query: UserQuery) -> UnifiedResponse:
        """사용자 쿼리 처리 - 메인 비즈니스 로직"""
        try:
            # TaskAgent에게 위임
            return await self.agent.process_query(query)
        except Exception as e:
            logger.error(f"쿼리 처리 실패: {e}")
            raise

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        try:
            return {
                "service": "TaskAgentService",
                "version": "5.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "dependencies": {
                    "llm_service": await self.llm_service.get_status(),
                    "rag_service": await self.rag_service.get_status(),
                    "automation_service": await self.automation_service.get_status(),
                    "conversation_service": await self.conversation_service.get_status()
                }
            }
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return {
                "service": "TaskAgentService",
                "version": "5.0.0",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def cleanup(self):
        """서비스 정리"""
        try:
            # 의존성 서비스들 정리
            cleanup_tasks = [
                self.automation_service.cleanup(),
                self.rag_service.cleanup(),
                self.llm_service.cleanup(),
                self.conversation_service.cleanup()
            ]
            
            for task in cleanup_tasks:
                try:
                    await task
                except Exception as e:
                    logger.warning(f"서비스 정리 중 오류: {e}")
            
            logger.info("TaskAgentService 정리 완료")
            
        except Exception as e:
            logger.error(f"TaskAgentService 정리 실패: {e}")
