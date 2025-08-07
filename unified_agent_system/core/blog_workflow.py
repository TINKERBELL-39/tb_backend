"""블로그 마케팅 워크플로우 구현"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from .models import WorkflowState, UnifiedRequest, UnifiedResponse, AgentType
from .agent_wrappers import AgentManager

logger = logging.getLogger(__name__)

class BlogWorkflowState(BaseModel):
    """블로그 워크플로우 상태"""
    base_keyword: str
    recommended_keywords: List[str] = []
    content: Optional[Dict[str, Any]] = None
    scheduled_date: Optional[datetime] = None
    error: Optional[str] = None
    step: str = "start"

class BlogMarketingWorkflow:
    """블로그 마케팅 워크플로우"""
    
    def __init__(self):
        self.agent_manager = AgentManager()
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> CompiledStateGraph:
        """LangGraph 워크플로우 생성"""
        workflow = StateGraph(BlogWorkflowState)
        
        # 노드 추가
        workflow.add_node("get_keyword_recommendations", self._get_keyword_recommendations_node)
        workflow.add_node("generate_content", self._generate_content_node)
        workflow.add_node("schedule_content", self._schedule_content_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # 엣지 추가
        workflow.set_entry_point("get_keyword_recommendations")
        
        workflow.add_edge("get_keyword_recommendations", "generate_content")
        workflow.add_edge("generate_content", "schedule_content")
        workflow.add_edge("schedule_content", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def execute_workflow(self, base_keyword: str) -> Dict[str, Any]:
        """워크플로우 실행"""
        try:
            initial_state = BlogWorkflowState(
                base_keyword=base_keyword,
                step="start"
            )
            
            final_state = await self.workflow.ainvoke(initial_state)
            return self._create_success_response(final_state)
            
        except Exception as e:
            logger.error(f"블로그 워크플로우 실행 실패: {e}")
            return self._create_error_response(str(e))
    
    async def _get_keyword_recommendations_node(self, state: BlogWorkflowState) -> Dict[str, Any]:
        """키워드 추천 노드"""
        try:
            state.step = "getting_keywords"
            
            # Task Agent에 키워드 추천 요청
            request = UnifiedRequest(
                user_id=1,  # 시스템 사용자 ID
                message=f"키워드 추천: {state.base_keyword}",
                preferred_agent=AgentType.TASK_AUTOMATION
            )
            
            response = await self.agent_manager.process_request(AgentType.TASK_AUTOMATION, request)
            
            # 추천 키워드 추출
            if response and response.metadata.get('keywords'):
                state.recommended_keywords = response.metadata['keywords']
            else:
                state.recommended_keywords = [state.base_keyword]
            
            return {"step": "keywords_complete"}
            
        except Exception as e:
            logger.error(f"키워드 추천 실패: {e}")
            state.error = f"키워드 추천 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _generate_content_node(self, state: BlogWorkflowState) -> Dict[str, Any]:
        """컨텐츠 생성 노드"""
        try:
            state.step = "generating_content"
            
            # Marketing Agent에 컨텐츠 생성 요청
            request = UnifiedRequest(
                user_id=1,  # 시스템 사용자 ID
                message=f"블로그 컨텐츠 생성: {state.base_keyword}, 추천 키워드: {', '.join(state.recommended_keywords)}",
                preferred_agent=AgentType.MARKETING
            )
            
            response = await self.agent_manager.process_request(AgentType.MARKETING, request)
            
            # 생성된 컨텐츠 저장
            if response and response.metadata.get('content'):
                state.content = response.metadata['content']
            else:
                raise Exception("컨텐츠 생성 실패")
            
            return {"step": "content_complete"}
            
        except Exception as e:
            logger.error(f"컨텐츠 생성 실패: {e}")
            state.error = f"컨텐츠 생성 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _schedule_content_node(self, state: BlogWorkflowState) -> Dict[str, Any]:
        """컨텐츠 스케줄링 노드"""
        try:
            state.step = "scheduling_content"
            
            # Task Agent에 스케줄링 요청
            request = UnifiedRequest(
                user_id=1,  # 시스템 사용자 ID
                message="컨텐츠 스케줄링",
                preferred_agent=AgentType.TASK_AUTOMATION,
                context={
                    "content": state.content,
                    "keywords": state.recommended_keywords
                }
            )
            
            response = await self.agent_manager.process_request(AgentType.TASK_AUTOMATION, request)
            
            # 스케줄링 정보 저장
            if response and response.metadata.get('scheduled_date'):
                state.scheduled_date = response.metadata['scheduled_date']
            
            return {"step": "scheduling_complete"}
            
        except Exception as e:
            logger.error(f"컨텐츠 스케줄링 실패: {e}")
            state.error = f"컨텐츠 스케줄링 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _handle_error_node(self, state: BlogWorkflowState) -> Dict[str, Any]:
        """에러 처리 노드"""
        logger.error(f"워크플로우 에러 발생: {state.error}")
        return {"error": state.error, "step": "error"}
    
    def _create_success_response(self, state: BlogWorkflowState) -> Dict[str, Any]:
        """성공 응답 생성"""
        return {
            "success": True,
            "data": {
                "base_keyword": state.base_keyword,
                "recommended_keywords": state.recommended_keywords,
                "content": state.content,
                "scheduled_date": state.scheduled_date.isoformat() if state.scheduled_date else None,
                "step": state.step
            }
        }
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "success": False,
            "error": error_message
        }