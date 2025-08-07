"""
각 에이전트를 래핑하여 통일된 인터페이스 제공
"""

import asyncio
import time
import logging
import httpx
import certifi

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

from .models import AgentType, AgentResponse, UnifiedRequest
from .config import get_system_config
from shared_modules.database import DatabaseManager
from shared_modules.queries import get_user_by_id

logger = logging.getLogger(__name__)


class BaseAgentWrapper(ABC):
    """에이전트 래퍼 기본 클래스"""
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.config = get_system_config().agents[agent_type]
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            verify=False
        )
        self.db_manager = DatabaseManager()
    
    def _get_user_persona(self, user_id: int) -> str:
        """사용자 ID로부터 persona(business_type) 가져오기"""
        try:
            with self.db_manager.get_session() as db:
                user = get_user_by_id(db, user_id)
                if user and user.business_type:
                    return user.business_type
                return "common"  # 기본값
        except Exception as e:
            logger.warning(f"사용자 persona 조회 실패 (user_id: {user_id}): {e}")
            return "common"  # 에러 시 기본값
    
    @abstractmethod
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        """요청 처리 (각 에이전트별로 구현)"""
        pass
    
    async def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP 요청 실행"""
        try:
            response = await self.client.post(
                self.config.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # create_success_response로 래핑된 응답인 경우 data 부분만 추출
            if isinstance(result, dict) and "success" in result and "data" in result:
                if result.get("success"):
                    return result["data"]
                else:
                    # 에러 응답인 경우
                    error_msg = result.get("error", "알 수 없는 오류")
                    raise Exception(f"Agent error: {error_msg}")
            
            # 직접 응답인 경우 그대로 반환
            return result
            
        except httpx.TimeoutException:
            logger.error(f"{self.agent_type} 타임아웃")
            raise Exception(f"{self.agent_type} 응답 시간 초과")
        except httpx.HTTPStatusError as e:
            logger.error(f"{self.agent_type} HTTP 오류: {e.response.status_code}")
            raise Exception(f"{self.agent_type} 서비스 오류: {e.response.status_code}")
        except Exception as e:
            logger.error(f"{self.agent_type} 요청 실패: {e}")
            raise Exception(f"{self.agent_type} 서비스 연결 실패")
    
    async def health_check(self) -> bool:
        """에이전트 상태 확인"""
        try:
            # 다양한 health endpoint 패턴 지원
            health_url = self.config.endpoint
            if "/agent/query" in health_url:
                health_url = health_url.replace("/agent/query", "/health")
            elif "/query" in health_url:
                health_url = health_url.replace("/query", "/health")
            else:
                # 기본 health endpoint 추가
                health_url = health_url.rstrip('/') + "/health"
            
            response = await self.client.get(health_url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """리소스 정리"""
        await self.client.aclose()


class BusinessPlanningAgentWrapper(BaseAgentWrapper):
    """비즈니스 플래닝 에이전트 래퍼"""
    
    def __init__(self):
        super().__init__(AgentType.BUSINESS_PLANNING)
    
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        start_time = time.time()
        
        try:
            # 사용자별 persona 가져오기
            user_persona = self._get_user_persona(request.user_id)
            
            # 비즈니스 플래닝 에이전트 API 형식에 맞게 변환
            payload = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "message": request.message,
                "persona": user_persona  # DB에서 가져온 persona 사용
            }
            
            result = await self._make_request(payload)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=result.get("response") or result.get("answer", "응답을 받지 못했습니다."),
                confidence=0.85,  # 기본값
                sources=result.get("sources", ""),
                metadata={
                    "topics": result.get("topics", []),
                    "type": result.get("type", "general"),
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "persona": user_persona  # 사용된 persona 정보 추가
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"비즈니스 플래닝 에이전트 처리 실패: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"비즈니스 플래닝 서비스에 일시적인 문제가 발생했습니다: {str(e)}",
                confidence=0.0,
                processing_time=time.time() - start_time
            )


class CustomerServiceAgentWrapper(BaseAgentWrapper):
    """고객 서비스 에이전트 래퍼"""
    
    def __init__(self):
        super().__init__(AgentType.CUSTOMER_SERVICE)
    
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        start_time = time.time()
        
        try:
            # 사용자별 persona 가져오기
            user_persona = self._get_user_persona(request.user_id)
            
            # 고객 서비스 에이전트 API 형식에 맞게 변환
            payload = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "message": request.message,
                "persona": user_persona  # DB에서 가져온 persona 사용
            }
            
            result = await self._make_request(payload)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=result.get("answer") or result.get("response", "응답을 받지 못했습니다."),
                confidence=0.85,
                sources="",  # 고객 서비스 에이전트는 sources를 따로 반환하지 않음
                metadata={
                    "topics": result.get("topics", []),
                    "history": result.get("history", [])
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"고객 서비스 에이전트 처리 실패: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"고객 서비스에 일시적인 문제가 발생했습니다: {str(e)}",
                confidence=0.0,
                processing_time=time.time() - start_time
            )


class MarketingAgentWrapper(BaseAgentWrapper):
    """마케팅 에이전트 래퍼"""
    
    def __init__(self):
        super().__init__(AgentType.MARKETING)
    
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        start_time = time.time()
        
        try:
            # 사용자별 persona 가져오기
            user_persona = self._get_user_persona(request.user_id)
            
            # 마케팅 에이전트 API 형식에 맞게 변환
            payload = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "message": request.message,
                "persona": user_persona
            }
            
            result = await self._make_request(payload)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=result.get("answer") or result.get("response", "응답을 받지 못했습니다."),
                confidence=0.85,
                sources=result.get("sources", ""),
                metadata={
                    "topics": result.get("topics", []),
                    "conversation_id": result.get("conversation_id"),
                    "templates": result.get("templates", []),
                    "debug_info": result.get("debug_info", {}),
                    "show_posting_modal": result.get("metadata", {}).get("show_posting_modal", False)
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"마케팅 에이전트 처리 실패: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"마케팅 서비스에 일시적인 문제가 발생했습니다: {str(e)}",
                confidence=0.0,
                processing_time=time.time() - start_time
            )


class MentalHealthAgentWrapper(BaseAgentWrapper):
    """멘탈 헬스 에이전트 래퍼"""
    
    def __init__(self):
        super().__init__(AgentType.MENTAL_HEALTH)
    
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        start_time = time.time()
        
        try:
            # 사용자별 persona 가져오기
            user_persona = self._get_user_persona(request.user_id)
            
            # 멘탈 헬스 에이전트 API 형식에 맞게 변환
            payload = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "message": request.message,
                "persona": user_persona  # DB에서 가져온 persona 사용
            }
            
            result = await self._make_request(payload)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=result.get("response") or result.get("answer", "응답을 받지 못했습니다."),
                confidence=0.9,  # 멘탈 헬스는 높은 신뢰도
                sources="",
                metadata={
                    "emotion": result.get("emotion", "중립"),
                    "phq9_score": result.get("phq9_score"),
                    "phq9_level": result.get("phq9_level"),
                    "suggestions": result.get("suggestions", [])
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"멘탈 헬스 에이전트 처리 실패: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"멘탈 헬스 서비스에 일시적인 문제가 발생했습니다: {str(e)}",
                confidence=0.0,
                processing_time=time.time() - start_time
            )


class TaskAutomationAgentWrapper(BaseAgentWrapper):
    """업무 자동화 에이전트 래퍼"""
    
    def __init__(self):
        super().__init__(AgentType.TASK_AUTOMATION)
    
    async def process_request(self, request: UnifiedRequest) -> AgentResponse:
        start_time = time.time()
        
        try:
            # 사용자별 persona 가져오기
            user_persona = self._get_user_persona(request.user_id)
            
            # 업무 자동화 에이전트 API 형식에 맞게 변환
            payload = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "message": request.message,
                "persona": user_persona  # DB에서 가져온 persona 사용
            }
            
            result = await self._make_request(payload)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=result.get("response") or result.get("answer", "응답을 받지 못했습니다."),
                confidence=0.85,
                sources="",
                metadata={
                    "status": result.get("status", "success"),
                    "intent": result.get("intent", "general_inquiry"),
                    "urgency": result.get("urgency", "medium"),
                    "actions": result.get("actions", []),
                    "automation_created": result.get("automation_created", False)
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"업무 자동화 에이전트 처리 실패: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"업무 자동화 서비스에 일시적인 문제가 발생했습니다: {str(e)}",
                confidence=0.0,
                processing_time=time.time() - start_time
            )


class AgentManager:
    """에이전트들을 관리하는 매니저 클래스"""
    
    def __init__(self):
        self.agents = {
            AgentType.BUSINESS_PLANNING: BusinessPlanningAgentWrapper(),
            AgentType.CUSTOMER_SERVICE: CustomerServiceAgentWrapper(),
            AgentType.MARKETING: MarketingAgentWrapper(),
            AgentType.MENTAL_HEALTH: MentalHealthAgentWrapper(),
            AgentType.TASK_AUTOMATION: TaskAutomationAgentWrapper()
        }
    
    async def process_request(self, agent_type: AgentType, request: UnifiedRequest) -> AgentResponse:
        """지정된 에이전트로 요청 처리"""
        if agent_type not in self.agents:
            raise ValueError(f"지원하지 않는 에이전트 타입: {agent_type}")
        
        agent = self.agents[agent_type]
        
        if not agent.config.enabled:
            raise Exception(f"{agent_type} 에이전트가 비활성화 상태입니다")
        
        return await agent.process_request(request)
    
    async def process_multiple_requests(self, agent_types: list, request: UnifiedRequest) -> Dict[AgentType, AgentResponse]:
        """여러 에이전트로 동시 요청 처리"""
        tasks = []
        valid_agents = []
        
        for agent_type in agent_types:
            if agent_type in self.agents and self.agents[agent_type].config.enabled:
                tasks.append(self.process_request(agent_type, request))
                valid_agents.append(agent_type)
        
        if not tasks:
            raise Exception("활성화된 에이전트가 없습니다")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        response_dict = {}
        for i, result in enumerate(results):
            agent_type = valid_agents[i]
            if isinstance(result, Exception):
                logger.error(f"{agent_type} 처리 실패: {result}")
                response_dict[agent_type] = AgentResponse(
                    agent_type=agent_type,
                    response=f"서비스 오류: {str(result)}",
                    confidence=0.0,
                    processing_time=0.0
                )
            else:
                response_dict[agent_type] = result
        
        return response_dict
    
    async def health_check_all(self) -> Dict[AgentType, bool]:
        """모든 에이전트 상태 확인"""
        tasks = []
        agent_types = []
        
        for agent_type, agent in self.agents.items():
            tasks.append(agent.health_check())
            agent_types.append(agent_type)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_status = {}
        for i, result in enumerate(results):
            agent_type = agent_types[i]
            health_status[agent_type] = result if isinstance(result, bool) else False
        
        return health_status
    
    async def close_all(self):
        """모든 에이전트 리소스 정리"""
        tasks = [agent.close() for agent in self.agents.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
