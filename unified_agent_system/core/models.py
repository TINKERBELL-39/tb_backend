"""
통합 에이전트 시스템의 데이터 모델 정의
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class AgentType(str, Enum):
    """에이전트 타입 열거형"""
    BUSINESS_PLANNING = "business_planning"
    CUSTOMER_SERVICE = "customer_service"
    MARKETING = "marketing"
    MENTAL_HEALTH = "mental_health"
    TASK_AUTOMATION = "task_automation"
    UNKNOWN = "unknown"


class MessageType(str, Enum):
    """메시지 타입"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class Priority(str, Enum):
    """우선순위"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RoutingDecision(BaseModel):
    """라우팅 결정 정보"""
    agent_type: AgentType
    confidence: float = Field(ge=0.0, le=1.0, description="라우팅 신뢰도")
    reasoning: str = Field(description="라우팅 이유")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    priority: Priority = Field(default=Priority.MEDIUM, description="우선순위")


class UnifiedRequest(BaseModel):
    """통합 에이전트 시스템 요청"""
    user_id: int = Field(description="사용자 ID")
    conversation_id: Optional[int] = Field(default=None, description="대화 ID")
    message: str = Field(description="사용자 메시지")
    context: Dict[str, Any] = Field(default_factory=dict, description="추가 컨텍스트")
    preferred_agent: Optional[Union[AgentType, str]] = Field(default=None, description="선호 에이전트")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="대화 기록")


class AgentResponse(BaseModel):
    """개별 에이전트 응답"""
    agent_type: AgentType
    response: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    sources: Optional[str] = Field(default=None, description="참고 문서")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float = Field(default=0.0, description="처리 시간 (초)")


class UnifiedResponse(BaseModel):
    """통합 시스템 응답"""
    conversation_id: int
    agent_type: AgentType
    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    routing_decision: RoutingDecision
    sources: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    alternatives: List[AgentResponse] = Field(default_factory=list, description="대안 응답들")


class WorkflowState(BaseModel):
    """워크플로우 상태"""
    request: UnifiedRequest
    routing_decision: Optional[RoutingDecision] = None
    primary_response: Optional[AgentResponse] = None
    alternative_responses: List[AgentResponse] = Field(default_factory=list)
    final_response: Optional[UnifiedResponse] = None
    error: Optional[str] = None
    step: str = Field(default="start", description="현재 워크플로우 단계")


class AgentConfig(BaseModel):
    """에이전트 설정"""
    name: str
    description: str
    endpoint: str
    timeout: int = Field(default=120, description="타임아웃 (초)")
    enabled: bool = Field(default=True, description="활성화 여부")
    keywords: List[str] = Field(default_factory=list, description="관련 키워드")
    confidence_threshold: float = Field(default=0.7, description="신뢰도 임계값")


class SystemConfig(BaseModel):
    """시스템 설정"""
    agents: Dict[AgentType, AgentConfig]
    routing_confidence_threshold: float = Field(default=0.8, description="라우팅 신뢰도 임계값")
    enable_multi_agent: bool = Field(default=True, description="멀티 에이전트 모드")
    max_alternative_responses: int = Field(default=2, description="최대 대안 응답 수")
    default_agent: AgentType = Field(default=AgentType.BUSINESS_PLANNING, description="기본 에이전트")


class HealthCheck(BaseModel):
    """헬스 체크 응답"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    agents: Dict[AgentType, bool] = Field(description="각 에이전트 상태")
    system_info: Dict[str, Any] = Field(default_factory=dict)


class TemplateUpdateRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[int] = None  # ✅ 이거 추가

# ===== 공통 요청/응답 모델 =====

class ConversationCreate(BaseModel):
    user_id: int
    title: Optional[str] = None
    agent_type: Optional[str] = None  # ✅ 프론트에서 넘겨줌
    

class SocialLoginRequest(BaseModel):
    provider: str
    social_id: str
    username: str
    email: str
    business_type: Optional[str] = None  # 추가
    experience: Optional[bool] = None    # 추가
    instagram_id: Optional[str] = None   # 이미 있지만 확실히 하기 위해

class PHQ9StartRequest(BaseModel):
    user_id: int
    conversation_id: int

class PHQ9SubmitRequest(BaseModel):
    user_id: int
    conversation_id: int
    scores: List[int]

class EmergencyRequest(BaseModel):
    user_id: int
    conversation_id: int
    message: str

class AutomationRequest(BaseModel):
    user_id: int
    task_type: str
    parameters: Dict[str, Any] = {}


class TemplateCreateRequest(BaseModel):
    user_id: int
    title: str
    content: str
    template_type: str
    channel_type: str
    content_type: Optional[str] = "text"
    is_custom: bool
    description: Optional[str] = None
    conversation_id: Optional[int] = None

class ProjectCreate(BaseModel):
    user_id: int
    title: str
    description: str = ""
    category: str = "general"