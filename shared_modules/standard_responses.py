"""
표준 에이전트 응답 구조 정의
모든 에이전트가 동일한 응답 구조를 사용하도록 통일
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class StandardAgentResponse(BaseModel):
    """표준 에이전트 응답 모델"""
    conversation_id: int = Field(description="대화 ID")
    topics: List[str] = Field(default_factory=list, description="분류된 토픽 목록")
    answer: str = Field(description="에이전트 응답 내용")
    sources: str = Field(default="", description="참고 문서 또는 소스")
    retrieval_used: bool = Field(default=False, description="검색 기능 사용 여부") 
    response_type: str = Field(default="normal", description="응답 타입 (normal, emergency, template 등)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="응답 생성 시간")

class AgentResponseFactory:
    """에이전트 응답 팩토리 클래스"""
    
    @staticmethod
    def create_standard_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "",
        retrieval_used: bool = False,
        response_type: str = "normal",
        **kwargs
    ) -> Dict[str, Any]:
        """표준 에이전트 응답 생성"""
        
        response = StandardAgentResponse(
            conversation_id=conversation_id,
            topics=topics or [],
            answer=answer,
            sources=sources,
            retrieval_used=retrieval_used,
            response_type=response_type,
            metadata=kwargs
        )
        
        return response.dict()
    
    @staticmethod
    def create_business_planning_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "",
        lean_canvas_data: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """비즈니스 플래닝 전용 응답"""
        
        metadata = kwargs.copy()
        if lean_canvas_data:
            metadata["lean_canvas"] = lean_canvas_data
        
        return AgentResponseFactory.create_standard_response(
            conversation_id=conversation_id,
            answer=answer,
            topics=topics or [],
            sources=sources,
            retrieval_used=True,
            response_type="business_planning",
            **metadata
        )
    
    @staticmethod
    def create_customer_service_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "",
        inquiry_type: str = "general",
        business_type: str = "common",
        **kwargs
    ) -> Dict[str, Any]:
        """고객 서비스 전용 응답"""
        
        metadata = kwargs.copy()
        metadata.update({
            "inquiry_type": inquiry_type,
            "business_type": business_type
        })
        
        return AgentResponseFactory.create_standard_response(
            conversation_id=conversation_id,
            answer=answer,
            topics=topics or [],
            sources=sources,
            retrieval_used=True,
            response_type="customer_service",
            **metadata
        )
    
    @staticmethod
    def create_marketing_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "LLM 기반 유연한 마케팅 시스템",
        templates: List[Dict[str, Any]] = None,
        conversation_stage: str = None,
        completion_rate: float = None,
        collected_info: Dict[str, Any] = None,
        multiturn_flow: bool = False,
        intent: str = None,
        confidence: float = 0.9,
        mcp_results: Dict[str, Any] = None,
        prompts_used: List[str] = None,
        mcp_tools_used: List[str] = None,
        entities_extracted: Dict[str, Any] = None,
        llm_classification: bool = False,
        topic_specific_prompts: bool = False,
        real_time_analysis: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        마케팅 전용 응답 생성 함수 (멀티턴 및 실시간 분석 지원)
        """

        metadata = kwargs.copy()

        # 템플릿 지원
        if templates:
            metadata["templates"] = templates

        # 멀티턴 대화 메타데이터
        if multiturn_flow:
            metadata.update({
                "multiturn_flow": True,
                "conversation_stage": conversation_stage,
                "completion_rate": completion_rate,
                "collected_info": collected_info or {}
            })

        # Intent 분석 결과
        if intent:
            metadata.update({
                "intent": intent,
                "confidence": confidence
            })

        # MCP 결과
        if mcp_results:
            metadata.update({
                "mcp_results": mcp_results,
                "real_time_analysis": real_time_analysis
            })

        # 프롬프트 사용 내역
        if prompts_used:
            metadata.update({
                "prompts_used": prompts_used,
                "topic_specific_prompts": topic_specific_prompts
            })

        # MCP 툴 사용 내역
        if mcp_tools_used:
            metadata["mcp_tools_used"] = mcp_tools_used

        # 엔티티 추출 결과
        if entities_extracted:
            metadata["entities_extracted"] = entities_extracted

        # LLM 분류 결과 여부
        if llm_classification:
            metadata["llm_classification"] = True

        # 응답 타입 결정
        if templates:
            response_type = "template_recommendation"
        elif multiturn_flow:
            response_type = "multiturn_marketing"
        elif real_time_analysis:
            response_type = "realtime_marketing_analysis"
        else:
            response_type = "marketing"

        return AgentResponseFactory.create_standard_response(
            conversation_id=conversation_id,
            answer=answer,
            topics=topics or [],
            sources=sources,
            retrieval_used=True,
            response_type=response_type,
            **metadata
        )

    
    @staticmethod
    def create_mental_health_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "",
        analysis: Dict[str, Any] = None,
        phq9_suggested: bool = False,
        emergency_contacts: List[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """정신건강 전용 응답"""
        
        metadata = kwargs.copy()
        if analysis:
            metadata["analysis"] = analysis
        if phq9_suggested:
            metadata["phq9_suggested"] = phq9_suggested
        if emergency_contacts:
            metadata["emergency_contacts"] = emergency_contacts
        
        # 긴급상황 체크
        response_type = "emergency" if emergency_contacts else "mental_health"
        
        return AgentResponseFactory.create_standard_response(
            conversation_id=conversation_id,
            answer=answer,
            topics=topics or ["mental_health"],
            sources=sources,
            retrieval_used=False,
            response_type=response_type,
            **metadata
        )
    
    @staticmethod
    def create_task_automation_response(
        conversation_id: int,
        answer: str,
        topics: List[str] = None,
        sources: str = "",
        intent: str = "general_inquiry",
        urgency: str = "medium",
        actions: List[Dict[str, Any]] = None,
        automation_created: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """업무 자동화 전용 응답"""
        
        metadata = kwargs.copy()
        metadata.update({
            "intent": intent,
            "urgency": urgency,
            "automation_created": automation_created
        })
        if actions:
            metadata["actions"] = actions
        
        return AgentResponseFactory.create_standard_response(
            conversation_id=conversation_id,
            answer=answer,
            topics=topics or [intent],
            sources=sources,
            retrieval_used=False,
            response_type="task_automation",
            **metadata
        )

# 편의를 위한 별칭 함수들
def create_business_response(conversation_id: int, answer: str, **kwargs) -> Dict[str, Any]:
    """비즈니스 플래닝 응답 생성 편의 함수"""
    return AgentResponseFactory.create_business_planning_response(conversation_id, answer, **kwargs)

def create_customer_response(conversation_id: int, answer: str, **kwargs) -> Dict[str, Any]:
    """고객 서비스 응답 생성 편의 함수"""
    return AgentResponseFactory.create_customer_service_response(conversation_id, answer, **kwargs)

def create_marketing_response(conversation_id: int, answer: str, **kwargs) -> Dict[str, Any]:
    """마케팅 응답 생성 편의 함수"""
    return AgentResponseFactory.create_marketing_response(conversation_id, answer, **kwargs)

def create_mental_response(conversation_id: int, answer: str, **kwargs) -> Dict[str, Any]:
    """정신건강 응답 생성 편의 함수"""
    return AgentResponseFactory.create_mental_health_response(conversation_id, answer, **kwargs)

def create_task_response(conversation_id: int, answer: str, **kwargs) -> Dict[str, Any]:
    """업무 자동화 응답 생성 편의 함수"""
    return AgentResponseFactory.create_task_automation_response(conversation_id, answer, **kwargs)
