#!/usr/bin/env python3
"""
Unified Agent System MCP Server
통합 에이전트 시스템을 위한 MCP 서버 구현
"""

import sys
import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import logging

# 상위 디렉토리 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, Field

# 통합 시스템 import
try:
    from core.models import (
        UnifiedRequest, UnifiedResponse, AgentType, 
        RoutingDecision, Priority, WorkflowState
    )
    from core.workflow import get_workflow
    from shared_modules import (
        get_session_context, create_conversation, 
        create_message, get_recent_messages, 
        get_or_create_conversation_session,
        create_success_response, create_error_response
    )
except ImportError:
    # 공통 모듈 import 실패 시 기본 로깅만 사용
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# 로깅 설정
logger = logging.getLogger(__name__)

class QueryInput(BaseModel):
    """쿼리 입력 모델"""
    user_id: int = Field(..., description="사용자 ID")
    message: str = Field(..., description="사용자 메시지")
    conversation_id: Optional[int] = Field(default=None, description="대화 ID")
    preferred_agent: Optional[str] = Field(default=None, description="선호 에이전트")
    context: Dict[str, Any] = Field(default_factory=dict, description="추가 컨텍스트")

class WorkflowExecutionInput(BaseModel):
    """워크플로우 실행 입력 모델"""
    workflow_type: str = Field(..., description="워크플로우 타입")
    user_id: int = Field(..., description="사용자 ID")
    conversation_id: Optional[int] = Field(default=None, description="대화 ID")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="워크플로우 매개변수")

class MultiAgentInput(BaseModel):
    """멀티 에이전트 입력 모델"""
    query: str = Field(..., description="질의 내용")
    agents: List[str] = Field(..., description="사용할 에이전트 목록")
    user_id: int = Field(..., description="사용자 ID")
    conversation_id: Optional[int] = Field(default=None, description="대화 ID")

class RoutingTestInput(BaseModel):
    """라우팅 테스트 입력 모델"""
    message: str = Field(..., description="테스트할 메시지")
    user_id: int = Field(default=1, description="사용자 ID")

class ConversationInput(BaseModel):
    """대화 생성 입력 모델"""
    user_id: int = Field(..., description="사용자 ID")
    title: Optional[str] = Field(default=None, description="대화 제목")

class UnifiedSystemMCPServer:
    """통합 시스템 MCP 서버"""
    
    def __init__(self):
        self.server = Server("unified-agent-system")
        self.workflow = None
        self.setup_tools()
    
    async def initialize(self):
        """워크플로우 초기화"""
        try:
            self.workflow = get_workflow()
            logger.info("통합 시스템 MCP 서버 초기화 완료")
        except Exception as e:
            logger.error(f"워크플로우 초기화 실패: {e}")
            raise
    
    def setup_tools(self):
        """MCP 도구 설정"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="process_unified_query",
                    description="통합 에이전트 시스템에 질의 처리",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "integer", "description": "사용자 ID"},
                            "message": {"type": "string", "description": "사용자 메시지"},
                            "conversation_id": {"type": "integer", "description": "대화 ID"},
                            "preferred_agent": {"type": "string", "description": "선호 에이전트 (business_planning, marketing, customer_service, task_automation, mental_health)"},
                            "context": {"type": "object", "description": "추가 컨텍스트"}
                        },
                        "required": ["user_id", "message"]
                    }
                ),
                Tool(
                    name="route_query",
                    description="질의를 적절한 에이전트로 라우팅",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "테스트할 메시지"},
                            "user_id": {"type": "integer", "description": "사용자 ID", "default": 1}
                        },
                        "required": ["message"]
                    }
                ),
                Tool(
                    name="execute_workflow",
                    description="특정 워크플로우 실행",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workflow_type": {"type": "string", "description": "워크플로우 타입 (blog_marketing, business_planning, etc.)"},
                            "user_id": {"type": "integer", "description": "사용자 ID"},
                            "conversation_id": {"type": "integer", "description": "대화 ID"},
                            "parameters": {"type": "object", "description": "워크플로우 매개변수"}
                        },
                        "required": ["workflow_type", "user_id"]
                    }
                ),
                Tool(
                    name="multi_agent_query",
                    description="여러 에이전트에 동시 질의",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "질의 내용"},
                            "agents": {"type": "array", "items": {"type": "string"}, "description": "사용할 에이전트 목록"},
                            "user_id": {"type": "integer", "description": "사용자 ID"},
                            "conversation_id": {"type": "integer", "description": "대화 ID"}
                        },
                        "required": ["query", "agents", "user_id"]
                    }
                ),
                Tool(
                    name="get_system_status",
                    description="시스템 상태 확인",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="get_agent_health",
                    description="에이전트 상태 확인",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_type": {"type": "string", "description": "에이전트 타입"}
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="create_conversation",
                    description="새 대화 세션 생성",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "integer", "description": "사용자 ID"},
                            "title": {"type": "string", "description": "대화 제목"}
                        },
                        "required": ["user_id"]
                    }
                ),
                Tool(
                    name="get_conversation_history",
                    description="대화 기록 조회",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "integer", "description": "대화 ID"},
                            "limit": {"type": "integer", "description": "조회할 메시지 수", "default": 50}
                        },
                        "required": ["conversation_id"]
                    }
                ),
                Tool(
                    name="test_system",
                    description="시스템 통합 테스트 실행",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="get_workflow_status",
                    description="워크플로우 상태 조회",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                if not self.workflow:
                    await self.initialize()
                
                if name == "process_unified_query":
                    return await self.handle_unified_query(arguments)
                elif name == "route_query":
                    return await self.handle_route_query(arguments)
                elif name == "execute_workflow":
                    return await self.handle_workflow_execution(arguments)
                elif name == "multi_agent_query":
                    return await self.handle_multi_agent_query(arguments)
                elif name == "get_system_status":
                    return await self.handle_system_status(arguments)
                elif name == "get_agent_health":
                    return await self.handle_agent_health(arguments)
                elif name == "create_conversation":
                    return await self.handle_create_conversation(arguments)
                elif name == "get_conversation_history":
                    return await self.handle_conversation_history(arguments)
                elif name == "test_system":
                    return await self.handle_system_test(arguments)
                elif name == "get_workflow_status":
                    return await self.handle_workflow_status(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return [TextContent(
                    type="text",
                    text=f"도구 실행 중 오류가 발생했습니다: {str(e)}"
                )]
    
    async def handle_unified_query(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """통합 질의 처리"""
        try:
            user_id = arguments.get("user_id", 1)
            message = arguments.get("message", "")
            conversation_id = arguments.get("conversation_id")
            preferred_agent = arguments.get("preferred_agent")
            context = arguments.get("context", {})
            
            # 대화 세션 처리
            if not conversation_id:
                session_info = get_or_create_conversation_session(user_id, conversation_id)
                conversation_id = session_info["conversation_id"]
            
            # 에이전트 타입 변환
            agent_type = None
            if preferred_agent:
                agent_mapping = {
                    "business_planning": AgentType.BUSINESS_PLANNING,
                    "marketing": AgentType.MARKETING,
                    "customer_service": AgentType.CUSTOMER_SERVICE,
                    "task_automation": AgentType.TASK_AUTOMATION,
                    "mental_health": AgentType.MENTAL_HEALTH
                }
                agent_type = agent_mapping.get(preferred_agent)
            
            # 통합 요청 생성
            unified_request = UnifiedRequest(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                context=context,
                preferred_agent=agent_type
            )
            
            # 워크플로우 처리
            response = await self.workflow.process_request(unified_request)
            
            # 응답 포맷팅
            response_text = f"""
# 🤖 통합 에이전트 시스템 응답

## 처리 결과
{response.response}

## 📊 처리 정보
- **담당 에이전트**: {response.agent_type.value}
- **신뢰도**: {response.confidence:.2f}
- **처리 시간**: {response.processing_time:.2f}초
- **대화 ID**: {response.conversation_id}

## 🎯 라우팅 결정
- **선택된 에이전트**: {response.routing_decision.agent_type.value}
- **라우팅 신뢰도**: {response.routing_decision.confidence:.2f}
- **라우팅 이유**: {response.routing_decision.reasoning}
- **추출된 키워드**: {', '.join(response.routing_decision.keywords)}
- **우선순위**: {response.routing_decision.priority}

## 📚 참고 자료
{response.sources or "없음"}

## 🔄 대안 응답
{len(response.alternatives)}개의 대안 응답이 있습니다.

## 📅 처리 시간: {response.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            # 대안 응답 추가
            if response.alternatives:
                response_text += "\n\n### 📋 대안 응답들\n"
                for i, alt in enumerate(response.alternatives, 1):
                    response_text += f"**{i}. {alt.agent_type.value}** (신뢰도: {alt.confidence:.2f})\n"
                    response_text += f"{alt.response[:200]}...\n\n"
            
            return [TextContent(type="text", text=response_text)]
            
        except Exception as e:
            logger.error(f"Unified query error: {e}")
            return [TextContent(
                type="text",
                text=f"통합 질의 처리 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_route_query(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """질의 라우팅 처리"""
        try:
            message = arguments.get("message", "")
            user_id = arguments.get("user_id", 1)
            
            # 테스트용 요청 생성
            test_request = UnifiedRequest(
                user_id=user_id,
                message=message
            )
            
            # 라우팅 결정
            routing_decision = await self.workflow.router.route_query(test_request)
            
            routing_text = f"""
# 🎯 질의 라우팅 분석

## 입력 메시지
"{message}"

## 🤖 라우팅 결과
- **선택된 에이전트**: {routing_decision.agent_type.value}
- **신뢰도**: {routing_decision.confidence:.2f}
- **라우팅 이유**: {routing_decision.reasoning}
- **추출된 키워드**: {', '.join(routing_decision.keywords)}
- **우선순위**: {routing_decision.priority}

## 📊 에이전트 설명
{self._get_agent_description(routing_decision.agent_type)}

## 🎯 라우팅 품질
{"✅ 높은 신뢰도" if routing_decision.confidence > 0.8 else "⚠️ 중간 신뢰도" if routing_decision.confidence > 0.5 else "❌ 낮은 신뢰도"}

## 📅 분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=routing_text)]
            
        except Exception as e:
            logger.error(f"Route query error: {e}")
            return [TextContent(
                type="text",
                text=f"라우팅 분석 중 오류가 발생했습니다: {str(e)}"
            )]
    
    def _get_agent_description(self, agent_type: AgentType) -> str:
        """에이전트 설명 반환"""
        descriptions = {
            AgentType.BUSINESS_PLANNING: "💼 비즈니스 기획 전문가 - 창업, 사업 계획, 시장 분석 등",
            AgentType.MARKETING: "📢 마케팅 전문가 - 마케팅 전략, SNS, 브랜딩 등",
            AgentType.CUSTOMER_SERVICE: "🤝 고객 서비스 전문가 - 고객 관리, 서비스 개선 등",
            AgentType.TASK_AUTOMATION: "⚡ 업무 자동화 전문가 - 일정 관리, 업무 효율성 등",
            AgentType.MENTAL_HEALTH: "🧠 멘탈 헬스 전문가 - 스트레스 관리, 심리 상담 등"
        }
        return descriptions.get(agent_type, "알 수 없는 에이전트")
    
    async def handle_workflow_execution(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """워크플로우 실행 처리"""
        try:
            workflow_type = arguments.get("workflow_type", "")
            user_id = arguments.get("user_id", 1)
            conversation_id = arguments.get("conversation_id")
            parameters = arguments.get("parameters", {})
            
            # 워크플로우 타입별 처리
            if workflow_type == "blog_marketing":
                # 블로그 마케팅 워크플로우
                base_keyword = parameters.get("base_keyword", "")
                if not base_keyword:
                    raise ValueError("블로그 마케팅 워크플로우에는 base_keyword가 필요합니다")
                
                # 통합 요청 생성
                unified_request = UnifiedRequest(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message=f"블로그 마케팅 워크플로우: {base_keyword}",
                    context=parameters
                )
                
                response = await self.workflow.process_request(unified_request)
                
                workflow_text = f"""
# 🚀 블로그 마케팅 워크플로우 실행 결과

## 기본 키워드: {base_keyword}

## 📊 실행 결과
{response.response}

## 🎯 워크플로우 정보
- **워크플로우 타입**: {workflow_type}
- **담당 에이전트**: {response.agent_type.value}
- **처리 시간**: {response.processing_time:.2f}초
- **신뢰도**: {response.confidence:.2f}

## 📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
            else:
                # 기타 워크플로우
                workflow_text = f"""
# ⚙️ 워크플로우 실행

## 워크플로우 타입: {workflow_type}

현재 지원되지 않는 워크플로우 타입입니다.

## 🎯 지원되는 워크플로우
- blog_marketing: 블로그 마케팅 자동화
- business_planning: 사업 계획 수립
- customer_service: 고객 서비스 개선
- task_automation: 업무 자동화
- mental_health: 멘탈 헬스 케어

## 📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            
            return [TextContent(type="text", text=workflow_text)]
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return [TextContent(
                type="text",
                text=f"워크플로우 실행 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_multi_agent_query(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """멀티 에이전트 질의 처리"""
        try:
            query = arguments.get("query", "")
            agents = arguments.get("agents", [])
            user_id = arguments.get("user_id", 1)
            conversation_id = arguments.get("conversation_id")
            
            # 각 에이전트에 질의
            results = []
            for agent_name in agents:
                try:
                    # 에이전트 타입 매핑
                    agent_mapping = {
                        "business_planning": AgentType.BUSINESS_PLANNING,
                        "marketing": AgentType.MARKETING,
                        "customer_service": AgentType.CUSTOMER_SERVICE,
                        "task_automation": AgentType.TASK_AUTOMATION,
                        "mental_health": AgentType.MENTAL_HEALTH
                    }
                    
                    agent_type = agent_mapping.get(agent_name)
                    if not agent_type:
                        continue
                    
                    # 개별 요청 생성
                    unified_request = UnifiedRequest(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message=query,
                        preferred_agent=agent_type
                    )
                    
                    # 워크플로우 처리
                    response = await self.workflow.process_request(unified_request)
                    
                    results.append({
                        "agent": agent_name,
                        "response": response.response,
                        "confidence": response.confidence,
                        "processing_time": response.processing_time
                    })
                    
                except Exception as e:
                    results.append({
                        "agent": agent_name,
                        "error": str(e),
                        "confidence": 0.0,
                        "processing_time": 0.0
                    })
            
            # 결과 포맷팅
            multi_agent_text = f"""
# 🤖 멀티 에이전트 질의 결과

## 질의: "{query}"

## 📊 각 에이전트 응답
            """
            
            for i, result in enumerate(results, 1):
                if "error" in result:
                    multi_agent_text += f"""
### {i}. {result['agent']} 에이전트 ❌
**오류**: {result['error']}
                    """
                else:
                    multi_agent_text += f"""
### {i}. {result['agent']} 에이전트 ✅
**신뢰도**: {result['confidence']:.2f}
**처리 시간**: {result['processing_time']:.2f}초

{result['response'][:300]}...

---
                    """
            
            multi_agent_text += f"""
## 📈 통계
- **총 에이전트 수**: {len(agents)}
- **성공한 에이전트 수**: {len([r for r in results if 'error' not in r])}
- **평균 신뢰도**: {sum(r.get('confidence', 0) for r in results) / len(results):.2f}
- **총 처리 시간**: {sum(r.get('processing_time', 0) for r in results):.2f}초

## 📅 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=multi_agent_text)]
            
        except Exception as e:
            logger.error(f"Multi-agent query error: {e}")
            return [TextContent(
                type="text",
                text=f"멀티 에이전트 질의 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_system_status(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """시스템 상태 확인"""
        try:
            status = await self.workflow.get_workflow_status()
            
            status_text = f"""
# 🔧 시스템 상태 정보

## 📊 전체 시스템 상태
- **상태**: {"✅ 정상" if status['active_agents'] == status['total_agents'] else "⚠️ 일부 에이전트 비활성"}
- **활성 에이전트**: {status['active_agents']}/{status['total_agents']}
- **워크플로우 버전**: {status['workflow_version']}
- **멀티 에이전트 모드**: {"✅ 활성" if status['config']['enable_multi_agent'] else "❌ 비활성"}

## 🤖 에이전트별 상태
            """
            
            for agent_type, is_healthy in status['agent_health'].items():
                status_icon = "✅" if is_healthy else "❌"
                status_text += f"- **{agent_type}**: {status_icon} {'정상' if is_healthy else '비정상'}\n"
            
            status_text += f"""
## ⚙️ 시스템 설정
- **라우팅 신뢰도 임계값**: {status['config']['routing_confidence_threshold']}
- **최대 대안 응답 수**: {status['config']['max_alternative_responses']}
- **기본 에이전트**: {status['config']['default_agent']}

## 📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=status_text)]
            
        except Exception as e:
            logger.error(f"System status error: {e}")
            return [TextContent(
                type="text",
                text=f"시스템 상태 확인 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_agent_health(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """에이전트 상태 확인"""
        try:
            agent_type = arguments.get("agent_type")
            
            # 전체 에이전트 상태 조회
            agent_health = await self.workflow.agent_manager.health_check_all()
            
            if agent_type:
                # 특정 에이전트 상태
                agent_enum = None
                for enum_value in AgentType:
                    if enum_value.value == agent_type:
                        agent_enum = enum_value
                        break
                
                if agent_enum and agent_enum in agent_health:
                    is_healthy = agent_health[agent_enum]
                    health_text = f"""
# 🤖 {agent_type} 에이전트 상태

## 📊 상태 정보
- **에이전트 타입**: {agent_type}
- **상태**: {"✅ 정상" if is_healthy else "❌ 비정상"}
- **설명**: {self._get_agent_description(agent_enum)}

## 📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                else:
                    health_text = f"""
# ❌ 에이전트를 찾을 수 없습니다

## 에이전트 타입: {agent_type}

지원되는 에이전트 타입:
- business_planning
- marketing
- customer_service
- task_automation
- mental_health

## 📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
            else:
                # 전체 에이전트 상태
                health_text = f"""
# 🤖 전체 에이전트 상태

## 📊 에이전트별 상태
                """
                
                for agent_enum, is_healthy in agent_health.items():
                    status_icon = "✅" if is_healthy else "❌"
                    health_text += f"- **{agent_enum.value}**: {status_icon} {'정상' if is_healthy else '비정상'}\n"
                
                healthy_count = sum(1 for is_healthy in agent_health.values() if is_healthy)
                total_count = len(agent_health)
                
                health_text += f"""
## 📈 통계
- **정상 에이전트**: {healthy_count}/{total_count}
- **시스템 상태**: {"✅ 정상" if healthy_count == total_count else "⚠️ 일부 에이전트 비활성"}

## 📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            
            return [TextContent(type="text", text=health_text)]
            
        except Exception as e:
            logger.error(f"Agent health error: {e}")
            return [TextContent(
                type="text",
                text=f"에이전트 상태 확인 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_create_conversation(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """대화 생성 처리"""
        try:
            user_id = arguments.get("user_id", 1)
            title = arguments.get("title", "새 대화")
            
            # 대화 세션 생성
            session_info = get_or_create_conversation_session(user_id)
            conversation_id = session_info["conversation_id"]
            
            conversation_text = f"""
# 💬 새 대화 세션 생성

## 📋 대화 정보
- **대화 ID**: {conversation_id}
- **사용자 ID**: {user_id}
- **제목**: {title}
- **생성 여부**: {"✅ 새 대화" if session_info["is_new"] else "🔄 기존 대화"}

## 🚀 사용 방법
이제 `process_unified_query` 도구를 사용하여 대화를 시작할 수 있습니다.
conversation_id에 {conversation_id}를 입력하세요.

## 📅 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=conversation_text)]
            
        except Exception as e:
            logger.error(f"Create conversation error: {e}")
            return [TextContent(
                type="text",
                text=f"대화 생성 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_conversation_history(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """대화 기록 조회"""
        try:
            conversation_id = arguments.get("conversation_id", 1)
            limit = arguments.get("limit", 50)
            
            # 대화 기록 조회
            with get_session_context() as db:
                messages = get_recent_messages(db, conversation_id, limit)
            
            if not messages:
                history_text = f"""
# 📝 대화 기록

## 대화 ID: {conversation_id}

대화 기록이 없습니다.

## 📅 조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            else:
                history_text = f"""
# 📝 대화 기록

## 대화 ID: {conversation_id}
## 총 메시지 수: {len(messages)}

## 💬 메시지 목록
                """
                
                for i, msg in enumerate(reversed(messages), 1):
                    role = "🧑‍💻 사용자" if msg.sender_type.lower() == "user" else "🤖 에이전트"
                    timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else "시간 없음"
                    
                    history_text += f"""
### {i}. {role} ({timestamp})
**에이전트**: {msg.agent_type}
**내용**: {msg.content[:200]}{"..." if len(msg.content) > 200 else ""}

---
                    """
                
                history_text += f"""
## 📅 조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            
            return [TextContent(type="text", text=history_text)]
            
        except Exception as e:
            logger.error(f"Conversation history error: {e}")
            return [TextContent(
                type="text",
                text=f"대화 기록 조회 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_system_test(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """시스템 테스트 처리"""
        try:
            # 테스트 질의들
            test_queries = [
                ("사업계획서 작성 방법을 알려주세요", "business_planning"),
                ("고객 불만 처리 방법은?", "customer_service"),
                ("SNS 마케팅 전략을 추천해주세요", "marketing"),
                ("요즘 스트레스가 심해요", "mental_health"),
                ("회의 일정을 자동으로 잡아주세요", "task_automation")
            ]
            
            results = []
            
            for query, expected_agent in test_queries:
                try:
                    # 라우팅 테스트
                    request = UnifiedRequest(user_id=999, message=query)
                    routing_decision = await self.workflow.router.route_query(request)
                    
                    # 결과 저장
                    results.append({
                        "query": query,
                        "expected_agent": expected_agent,
                        "routed_agent": routing_decision.agent_type.value,
                        "confidence": routing_decision.confidence,
                        "correct": routing_decision.agent_type.value == expected_agent
                    })
                    
                except Exception as e:
                    results.append({
                        "query": query,
                        "expected_agent": expected_agent,
                        "error": str(e),
                        "correct": False
                    })
            
            # 정확도 계산
            correct_count = sum(1 for r in results if r.get("correct", False))
            accuracy = correct_count / len(results) if results else 0
            
            # 결과 포맷팅
            test_text = f"""
# 🧪 시스템 통합 테스트 결과

## 📊 전체 결과
- **총 테스트 수**: {len(results)}
- **성공 수**: {correct_count}
- **정확도**: {accuracy:.2%}
- **상태**: {"✅ 통과" if accuracy >= 0.8 else "⚠️ 주의" if accuracy >= 0.6 else "❌ 실패"}

## 📝 개별 테스트 결과
            """
            
            for i, result in enumerate(results, 1):
                status = "✅" if result.get("correct", False) else "❌"
                
                if "error" in result:
                    test_text += f"""
### {i}. {status} 테스트 {i}
**질의**: {result['query']}
**예상 에이전트**: {result['expected_agent']}
**오류**: {result['error']}
                    """
                else:
                    test_text += f"""
### {i}. {status} 테스트 {i}
**질의**: {result['query']}
**예상 에이전트**: {result['expected_agent']}
**라우팅된 에이전트**: {result['routed_agent']}
**신뢰도**: {result['confidence']:.2f}
                    """
            
            test_text += f"""
## 📅 테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=test_text)]
            
        except Exception as e:
            logger.error(f"System test error: {e}")
            return [TextContent(
                type="text",
                text=f"시스템 테스트 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def handle_workflow_status(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """워크플로우 상태 조회"""
        try:
            workflow_status = await self.workflow.get_workflow_status()
            
            status_text = f"""
# ⚙️ 워크플로우 상태

## 📊 기본 정보
- **워크플로우 버전**: {workflow_status['workflow_version']}
- **총 에이전트**: {workflow_status['total_agents']}
- **활성 에이전트**: {workflow_status['active_agents']}

## 🤖 에이전트 상태
            """
            
            for agent_type, is_healthy in workflow_status['agent_health'].items():
                status_icon = "✅" if is_healthy else "❌"
                status_text += f"- **{agent_type}**: {status_icon}\n"
            
            status_text += f"""
## ⚙️ 워크플로우 설정
- **멀티 에이전트 모드**: {"✅ 활성" if workflow_status['config']['enable_multi_agent'] else "❌ 비활성"}
- **라우팅 신뢰도 임계값**: {workflow_status['config']['routing_confidence_threshold']}
- **최대 대안 응답 수**: {workflow_status['config']['max_alternative_responses']}
- **기본 에이전트**: {workflow_status['config']['default_agent']}

## 📈 성능 지표
- **라우터 상태**: {"✅ 정상" if workflow_status['active_agents'] > 0 else "❌ 비정상"}
- **에이전트 매니저 상태**: {"✅ 정상" if workflow_status['total_agents'] > 0 else "❌ 비정상"}

## 📅 조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            return [TextContent(type="text", text=status_text)]
            
        except Exception as e:
            logger.error(f"Workflow status error: {e}")
            return [TextContent(
                type="text",
                text=f"워크플로우 상태 조회 중 오류가 발생했습니다: {str(e)}"
            )]
    
    async def run(self):
        """MCP 서버 실행"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

def main():
    """메인 함수"""
    server = UnifiedSystemMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()
