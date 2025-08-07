"""
LangGraph를 사용한 통합 에이전트 워크플로우
"""

import time
import logging
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from .models import (
    WorkflowState, UnifiedRequest, UnifiedResponse, 
    AgentType, RoutingDecision, AgentResponse
)
from .router import QueryRouter
from .agent_wrappers import AgentManager
from .config import get_system_config

logger = logging.getLogger(__name__)


class UnifiedAgentWorkflow:
    """통합 에이전트 워크플로우"""
    
    def __init__(self):
        self.config = get_system_config()
        self.router = QueryRouter()
        self.agent_manager = AgentManager()
        self.workflow = self._create_workflow()
        
        # 대화 히스토리 관리
        self.conversation_histories: Dict[int, List[Dict[str, Any]]] = {}
        self.enable_context_routing = True  # 컨텍스트 라우팅 활성화
    
    def _create_workflow(self) -> CompiledStateGraph:
        """LangGraph 워크플로우 생성"""
        
        # StateGraph 생성
        workflow = StateGraph(WorkflowState)
        
        # 노드 추가
        workflow.add_node("route_query", self._route_query_node)
        workflow.add_node("process_primary_agent", self._process_primary_agent_node)
        workflow.add_node("process_alternative_agents", self._process_alternative_agents_node)
        workflow.add_node("generate_final_response", self._generate_final_response_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # 엣지 추가
        workflow.set_entry_point("route_query")
        
        workflow.add_conditional_edges(
            "route_query",
            self._should_process_alternatives,
            {
                "primary_only": "process_primary_agent",
                "with_alternatives": "process_alternative_agents",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("process_primary_agent", "generate_final_response")
        workflow.add_edge("process_alternative_agents", "generate_final_response")
        workflow.add_edge("generate_final_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def process_request(self, request: UnifiedRequest) -> UnifiedResponse:
        """통합 요청 처리"""
        start_time = time.time()
        
        try:
            # 초기 상태 설정
            initial_state = WorkflowState(
                request=request,
                step="start"
            )
            
            # 워크플로우 실행
            final_state = await self.workflow.ainvoke(initial_state)
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            if final_state["final_response"]:
                final_state["final_response"].processing_time = processing_time
                return final_state["final_response"]
            else:
                # 오류 상황
                return UnifiedResponse(
                    conversation_id=request.conversation_id or 0,
                    agent_type=AgentType.UNKNOWN,
                    response=final_state.error or "알 수 없는 오류가 발생했습니다.",
                    confidence=0.0,
                    routing_decision=RoutingDecision(
                        agent_type=AgentType.UNKNOWN,
                        confidence=0.0,
                        reasoning="워크플로우 오류",
                        keywords=[],
                    ),
                    processing_time=processing_time
                )
                
        except Exception as e:
            logger.error(f"워크플로우 실행 실패: {e}")
            return UnifiedResponse(
                conversation_id=request.conversation_id or 0,
                agent_type=AgentType.UNKNOWN,
                response=f"시스템 오류가 발생했습니다: {str(e)}",
                confidence=0.0,
                routing_decision=RoutingDecision(
                    agent_type=AgentType.UNKNOWN,
                    confidence=0.0,
                    reasoning="시스템 오류",
                    keywords=[],
                ),
                processing_time=time.time() - start_time
            )
    
    async def _route_query_node(self, state: WorkflowState) -> Dict[str, Any]:
        """질의 라우팅 노드"""
        try:
            logger.info(f"라우팅 시작: {state.request.message[:50]}...")
            state.step = "routing"
            
            # 대화 히스토리 가져오기
            conversation_id = state.request.conversation_id or 0
            conversation_history = self.conversation_histories.get(conversation_id, [])
            
            # 향상된 컨텍스트 라우팅 실행
            routing_decision = await self.router.route_query(
                state.request, 
                conversation_history, 
                enable_context_routing=self.enable_context_routing
            )
            
            state.routing_decision = routing_decision
            
            logger.info(f"라우팅 완료: {routing_decision.agent_type} (신뢰도: {routing_decision.confidence})")
            logger.info(f"라우팅 이유: {routing_decision.reasoning}")
            
            return {"routing_decision": routing_decision, "step": "routing_complete"}
            
        except Exception as e:
            logger.error(f"라우팅 실패: {e}")
            state.error = f"라우팅 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    def _should_process_alternatives(self, state: WorkflowState) -> str:
        """대안 에이전트 처리 여부 결정"""
        if state.error:
            return "error"
        
        if not state.routing_decision:
            return "error"
        
        # 멀티 에이전트 모드이고 신뢰도가 임계값보다 낮으면 대안 처리
        if (self.config.enable_multi_agent and 
            state.routing_decision.confidence < self.config.routing_confidence_threshold):
            return "with_alternatives"
        else:
            return "primary_only"
    
    async def _process_primary_agent_node(self, state: WorkflowState) -> Dict[str, Any]:
        """주 에이전트 처리 노드"""
        try:
            state.step = "processing_primary"
            agent_type = state.routing_decision.agent_type
            
            logger.info(f"주 에이전트 처리 시작: {agent_type}")
            
            # 주 에이전트로 요청 처리
            response = await self.agent_manager.process_request(agent_type, state.request)
            state.primary_response = response
            
            logger.info(f"주 에이전트 처리 완료: {agent_type}")
            
            return {"primary_response": response, "step": "primary_complete"}
            
        except Exception as e:
            logger.error(f"주 에이전트 처리 실패: {e}")
            state.error = f"주 에이전트 처리 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _process_alternative_agents_node(self, state: WorkflowState) -> Dict[str, Any]:
        """대안 에이전트들 처리 노드"""
        try:
            state.step = "processing_alternatives"
            primary_agent = state.routing_decision.agent_type
            
            logger.info(f"대안 에이전트 처리 시작 (주: {primary_agent})")
            
            # 상위 추천 에이전트들 가져오기
            recommendations = self.router.get_agent_recommendations(
                state.request.message, 
                top_k=self.config.max_alternative_responses + 1
            )
            
            # 주 에이전트를 제외한 대안 에이전트들
            alternative_agents = []
            for rec in recommendations:
                if rec['agent_type'] != primary_agent and len(alternative_agents) < self.config.max_alternative_responses:
                    alternative_agents.append(rec['agent_type'])
            
            # 주 에이전트와 대안 에이전트들 동시 처리
            all_agents = [primary_agent] + alternative_agents
            responses = await self.agent_manager.process_multiple_requests(all_agents, state.request)
            
            # 주 응답과 대안 응답 분리
            state.primary_response = responses.get(primary_agent)
            state.alternative_responses = [
                responses[agent] for agent in alternative_agents 
                if agent in responses
            ]
            
            logger.info(f"대안 에이전트 처리 완료: {len(state.alternative_responses)}개")
            
            return {
                "primary_response": state.primary_response,
                "alternative_responses": state.alternative_responses,
                "step": "alternatives_complete"
            }
            
        except Exception as e:
            logger.error(f"대안 에이전트 처리 실패: {e}")
            state.error = f"대안 에이전트 처리 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _generate_final_response_node(self, state: WorkflowState) -> Dict[str, Any]:
        """최종 응답 생성 노드"""
        try:
            state.step = "generating_response"
            
            if not state.primary_response:
                raise Exception("주 에이전트 응답이 없습니다")
            
            # 대화 ID 설정
            conversation_id = state.request.conversation_id or 0
            
            # 최종 응답 생성
            final_response = UnifiedResponse(
                conversation_id=conversation_id,
                agent_type=state.routing_decision.agent_type,
                response=state.primary_response.response,
                confidence=state.primary_response.confidence,
                routing_decision=state.routing_decision,
                sources=state.primary_response.sources,
                metadata=state.primary_response.metadata,
                alternatives=state.alternative_responses or []
            )
            
            state.final_response = final_response
            
            # 대화 히스토리에 추가
            if conversation_id not in self.conversation_histories:
                self.conversation_histories[conversation_id] = []
            
            self.conversation_histories[conversation_id].append({
                "role": "user",
                "content": state.request.message,
                "timestamp": time.time()
            })
            
            self.conversation_histories[conversation_id].append({
                "role": "assistant", 
                "content": state.primary_response.response,
                "agent_type": state.routing_decision.agent_type.value,
                "confidence": state.primary_response.confidence,
                "timestamp": time.time()
            })
            
            # 라우터의 대화 흐름 업데이트
            self.router.update_conversation_flow(
                user_message=state.request.message,
                agent_type=state.routing_decision.agent_type,
                agent_response=state.primary_response.response,
                routing_reasoning=state.routing_decision.reasoning
            )
            
            # 히스토리 길이 제한 (최대 20개 메시지)
            if len(self.conversation_histories[conversation_id]) > 20:
                self.conversation_histories[conversation_id] = self.conversation_histories[conversation_id][-20:]
            
            logger.info(f"최종 응답 생성 완료: {state.routing_decision.agent_type}")
            
            return {"final_response": final_response, "step": "complete"}
            
        except Exception as e:
            logger.error(f"최종 응답 생성 실패: {e}")
            state.error = f"최종 응답 생성 실패: {str(e)}"
            return {"error": state.error, "step": "error"}
    
    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """오류 처리 노드"""
        logger.error(f"워크플로우 오류: {state.error}")
        
        # 폴백 응답 생성
        fallback_response = UnifiedResponse(
            conversation_id=state.request.conversation_id or 0,
            agent_type=self.config.default_agent,
            response="죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            confidence=0.0,
            routing_decision=RoutingDecision(
                agent_type=self.config.default_agent,
                confidence=0.0,
                reasoning=f"오류로 인한 폴백: {state.error}",
                keywords=[],
            ),
            metadata={"error": state.error}
        )
        
        state.final_response = fallback_response
        
        return {"final_response": fallback_response, "step": "error_handled"}
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """워크플로우 상태 조회"""
        agent_health = await self.agent_manager.health_check_all()
        
        return {
            "workflow_version": "1.0.0",
            "config": {
                "routing_confidence_threshold": self.config.routing_confidence_threshold,
                "enable_multi_agent": self.config.enable_multi_agent,
                "max_alternative_responses": self.config.max_alternative_responses,
                "default_agent": self.config.default_agent.value,
                "enable_context_routing": self.enable_context_routing
            },
            "agent_health": {agent.value: status for agent, status in agent_health.items()},
            "total_agents": len(self.config.agents),
            "active_agents": sum(1 for config in self.config.agents.values() if config.enabled),
            "conversation_insights": self.router.get_conversation_insights(),
            "active_conversations": len(self.conversation_histories)
        }
    
    # 컨텍스트 라우팅 관리 메서드들
    def enable_context_routing_mode(self, enabled: bool = True):
        """컨텍스트 라우팅 활성화/비활성화"""
        self.enable_context_routing = enabled
        logger.info(f"컨텍스트 라우팅 {'활성화' if enabled else '비활성화'}")
    
    def get_conversation_history(self, conversation_id: int) -> List[Dict[str, Any]]:
        """특정 대화의 히스토리 되돌리기"""
        return self.conversation_histories.get(conversation_id, [])
    
    def clear_conversation_history(self, conversation_id: int = None):
        """대화 히스토리 삭제"""
        if conversation_id is None:
            # 모든 대화 히스토리 삭제
            self.conversation_histories.clear()
            self.router.reset_context()
            logger.info("모든 대화 히스토리 삭제")
        else:
            # 특정 대화 히스토리만 삭제
            if conversation_id in self.conversation_histories:
                del self.conversation_histories[conversation_id]
                # 해당 대화의 라우터 컨텍스트도 초기화 (실제로는 대화별로 관리되어야 함)
                logger.info(f"대화 {conversation_id} 히스토리 삭제")
    
    def configure_routing_settings(self, **kwargs):
        """라우팅 설정 변경 (새로운 라우터는 자동으로 최적화됨)"""
        # 새로운 라우터는 대화 흐름 기반으로 자동 최적화되므로 별도 설정 불필요
        logger.info("새로운 라우터는 자동으로 대화 흐름을 최적화합니다")
    
    async def cleanup(self):
        """리소스 정리"""
        await self.agent_manager.close_all()
        logger.info("워크플로우 리소스 정리 완료")


# 워크플로우 싱글톤 인스턴스
_workflow_instance = None

def get_workflow() -> UnifiedAgentWorkflow:
    """워크플로우 싱글톤 인스턴스 반환"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = UnifiedAgentWorkflow()
    return _workflow_instance
