"""
Task Agent 데이터 모델 v4
공통 모듈의 db_models를 활용하고 Task Agent 전용 Pydantic 모델 정의
"""

import sys
import os
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field
from typing import Union

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))

# ===== Task Agent 전용 Enum =====

class PersonaType(str, Enum):
    CREATOR = "creator"
    BEAUTYSHOP = "beautyshop"
    E_COMMERCE = "ecommerce"
    SELF_EMPLOYMENT = "self_employment" 
    DEVELOPER = "programmer"
    COMMON = "common"

class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AutomationTaskType(str, Enum):
    POST_INSTAGRAM = "sns_publish_instagram"
    SCHEDULE_CALENDAR = "calendar_sync"
    PUBLISH_SNS = "publish_sns"
    SEND_EMAIL = "send_email"
    SEND_REMINDER = "send_reminder"
    SEND_MESSAGE = "send_message"
    TODO_LIST = "todo_list"

class AutomationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class IntentType(str, Enum):
    GENERAL_INQUIRY = "general_inquiry"
    TASK_AUTOMATION = "task_automation"
    SCHEDULE_MANAGEMENT = "schedule_management"
    TOOL_RECOMMENDATION = "tool_recommendation"

class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# ===== API 요청/응답 모델 =====

class UserQuery(BaseModel):
    """사용자 쿼리 요청"""
    user_id: int = Field(..., description="사용자 ID")  # Optional 제거
    conversation_id: Optional[int] = Field(None, description="대화 ID")
    message: str = Field(..., description="사용자 메시지")
    persona: str = Field("common", description="페르소나 타입")  # str로 변경하거나 PersonaType 유지
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,  # int로 변경
                "conversation_id": 456,
                "message": "내일 회의 일정을 예약해줘",
                "persona": "developer"
            }
        }

class QueryResponse(BaseModel):
    """쿼리 응답"""
    status: str = Field(..., description="응답 상태")
    response: str = Field(..., description="응답 메시지")
    conversation_id: str = Field(..., description="대화 ID")
    intent: IntentType = Field(..., description="의도 분류")
    urgency: UrgencyLevel = Field(UrgencyLevel.MEDIUM, description="긴급도")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도")
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="추천 액션")
    sources: List[str] = Field(default_factory=list, description="참조 소스")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "response": "내일 오후 2시에 개발팀 회의를 예약해드렸습니다.",
                "conversation_id": "conv_abc123",
                "intent": "schedule_management",
                "urgency": "medium",
                "confidence": 0.95,
                "actions": [{"type": "calendar_event", "data": {}}],
                "sources": ["calendar_api"],
                "timestamp": "2024-01-15T14:30:00"
            }
        }

class TaskRequest(BaseModel):
    """작업 요청"""
    user_id: str = Field(..., description="사용자 ID")
    title: str = Field(..., description="작업 제목")
    description: Optional[str] = Field(None, description="작업 설명")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="우선순위")
    due_date: Optional[datetime] = Field(None, description="마감일")
    task_data: Dict[str, Any] = Field(default_factory=dict, description="작업 데이터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "title": "주간 보고서 작성",
                "description": "개발 진행 상황 정리",
                "priority": "high",
                "due_date": "2024-01-20T17:00:00",
                "task_data": {"template": "weekly_report"}
            }
        }

class AutomationRequest(BaseModel):
    """자동화 요청"""
    user_id: int = Field(..., description="사용자 ID")
    task_type: AutomationTaskType = Field(..., description="자동화 작업 타입")
    title: str = Field(..., description="작업 제목")
    task_data: Dict[str, Any] = Field(..., description="작업 데이터")
    scheduled_at: Optional[datetime] = Field(None, description="예약 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "task_type": "calendar_sync",
                "title": "팀 회의 예약",
                "task_data": {
                    "title": "개발팀 주간 회의",
                    "start_time": "2024-01-16T14:00:00",
                    "duration": 60,
                    "attendees": ["dev1@company.com", "dev2@company.com"]
                },
                "scheduled_at": "2024-01-16T14:00:00"
            }
        }

class AutomationResponse(BaseModel):
    """자동화 응답"""
    task_id: int = Field(..., description="작업 ID")
    status: AutomationStatus = Field(..., description="작업 상태")
    message: str = Field(..., description="응답 메시지")
    scheduled_time: Optional[datetime] = Field(None, description="예약 시간")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": 456,
                "status": "success",
                "message": "캘린더 이벤트가 성공적으로 생성되었습니다.",
                "scheduled_time": "2024-01-16T14:00:00",
                "timestamp": "2024-01-15T10:30:00"
            }
        }

# ===== 내부 모델 =====

class KnowledgeChunk(BaseModel):
    """지식 청크"""
    content: str = Field(..., description="청크 내용")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="관련성 점수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "개발자를 위한 자동화 도구 사용법...",
                "metadata": {
                    "persona": "developer",
                    "topic": "automation",
                    "source": "manual"
                },
                "relevance_score": 0.85
            }
        }

class SearchResult(BaseModel):
    """검색 결과"""
    chunks: List[KnowledgeChunk] = Field(default_factory=list, description="지식 청크 목록")
    sources: List[str] = Field(default_factory=list, description="참조 소스 목록")
    total_results: int = Field(..., description="총 결과 수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunks": [
                    {
                        "content": "자동화 스크립트 작성 방법...",
                        "metadata": {"topic": "automation"},
                        "relevance_score": 0.9
                    }
                ],
                "sources": ["manual", "documentation"],
                "total_results": 1
            }
        }

class ConversationContext(BaseModel):
    """대화 컨텍스트"""
    conversation_id: str = Field(..., description="대화 ID")
    user_id: str = Field(..., description="사용자 ID")
    persona: PersonaType = Field(..., description="페르소나")
    last_intent: Optional[IntentType] = Field(None, description="마지막 의도")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="컨텍스트 데이터")
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시간")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 시간")

class IntentAnalysisResult(BaseModel):
    """의도 분석 결과"""
    intent: IntentType = Field(..., description="분류된 의도")
    urgency: UrgencyLevel = Field(..., description="긴급도")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    entities: Dict[str, Any] = Field(default_factory=dict, description="추출된 엔티티")
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list, description="제안 액션")

class UserPreferences(BaseModel):
    """사용자 선호도"""
    user_id: str = Field(..., description="사용자 ID")
    persona: PersonaType = Field(..., description="기본 페르소나")
    preferred_response_style: str = Field("friendly", description="응답 스타일")
    automation_settings: Dict[str, Any] = Field(default_factory=dict, description="자동화 설정")
    notification_preferences: Dict[str, bool] = Field(default_factory=dict, description="알림 설정")
    timezone: str = Field("Asia/Seoul", description="시간대")
    language: str = Field("ko", description="언어")

# ===== 통계 및 모니터링 모델 =====

class SystemStats(BaseModel):
    """시스템 통계"""
    total_users: int = Field(..., description="총 사용자 수")
    active_conversations: int = Field(..., description="활성 대화 수")
    pending_tasks: int = Field(..., description="대기 중인 작업 수")
    completed_tasks_today: int = Field(..., description="오늘 완료된 작업 수")
    average_response_time: float = Field(..., description="평균 응답 시간(초)")
    system_health: str = Field(..., description="시스템 상태")
    last_updated: datetime = Field(default_factory=datetime.now, description="마지막 업데이트")

class TaskPerformanceMetrics(BaseModel):
    """작업 성능 지표"""
    task_type: AutomationTaskType = Field(..., description="작업 타입")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="성공률")
    average_execution_time: float = Field(..., description="평균 실행 시간(초)")
    total_executions: int = Field(..., description="총 실행 횟수")
    last_execution: Optional[datetime] = Field(None, description="마지막 실행 시간")

# ===== 에러 모델 =====

class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = Field(False, description="성공 여부")
    error: str = Field(..., description="에러 메시지")
    error_code: Optional[str] = Field(None, description="에러 코드")
    details: Optional[Dict[str, Any]] = Field(None, description="상세 정보")
    timestamp: datetime = Field(default_factory=datetime.now, description="발생 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "유효하지 않은 사용자 ID입니다.",
                "error_code": "INVALID_USER_ID",
                "details": {"user_id": "invalid_id"},
                "timestamp": "2024-01-15T10:30:00"
            }
        }

class EmailRequest(BaseModel):
    to_emails: List[EmailStr]
    subject: str
    body: str
    html_body: Optional[str] = None
    attachments: Optional[List[str]] = None
    cc_emails: Optional[List[EmailStr]] = None
    bcc_emails: Optional[List[EmailStr]] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    service: Optional[str] = None


class InstagramPostRequest(BaseModel):
    instagram_id: str
    access_token: str
    image_url: str
    caption: Optional[str] = None
    
# ===== Pydantic 모델들 =====

class EventBase(BaseModel):
    title: str = Field(..., description="이벤트 제목")
    description: Optional[str] = Field("", description="이벤트 설명")
    location: Optional[str] = Field("", description="이벤트 위치")
    start_time: str = Field(..., description="시작 시간 (ISO 형식)")
    end_time: Optional[str] = Field(None, description="종료 시간 (ISO 형식)")
    timezone: Optional[str] = Field("Asia/Seoul", description="시간대")
    all_day: Optional[bool] = Field(False, description="종일 이벤트 여부")


class EventCreate(EventBase):
    calendar_id: Optional[str] = Field("primary", description="캘린더 ID")
    reminders: Optional[List[Dict[str, Any]]] = Field(
        [{"method": "popup", "minutes": 15}], 
        description="리마인더 설정"
    )
    recurrence: Optional[List[str]] = Field(None, description="반복 설정")


class EventUpdate(EventBase):
    title: Optional[str] = None
    start_time: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    location: Optional[str]
    start_time: str
    end_time: str
    calendar_id: str
    html_link: str
    creator: Optional[Dict[str, Any]]
    attendees: Optional[List[Dict[str, Any]]]


class CalendarListResponse(BaseModel):
    calendars: List[Dict[str, Any]]
    count: int


class QuickEventCreate(BaseModel):
    text: str = Field(..., description="빠른 이벤트 텍스트 (예: '내일 오후 2시에 회의')")
    calendar_id: Optional[str] = Field("primary", description="캘린더 ID")
    
    
from sqlalchemy import Column, Integer, String, Enum, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime

Base = declarative_base()


class TaskTypeEnum(str, enum.Enum):
    calendar_sync = "calendar_sync"
    reminder_notify = "reminder_notify"
    content_generate = "content_generate"
    sns_publish_instagram = "sns_publish_instagram"
    sns_publish_blog = "sns_publish_blog"
    send_email = "send_email"
    mcp_insta = "mcp_insta"
    mcp_blog = "mcp_blog"
    todo_list = "todo_list"

class AutomationTask(Base):
    __tablename__ = "automation_task"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    conversation_id = Column(Integer)
    task_type = Column(Enum(TaskTypeEnum), nullable=False)
    title = Column(String(200), nullable=False)
    template_id = Column(Integer)
    task_data = Column(JSON)  
    status = Column(String(20))
    scheduled_at = Column(DateTime)
    executed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class AiContentSaveRequest(BaseModel):
    user_id: int
    task_type: TaskTypeEnum
    title: str
    task_data: Dict[str, Union[str, List[str], Dict]]  # ✅ 필수!
    status: str = "PENDING"

# 공통 필드 포함 모델
class BaseContentRequest(BaseModel):
    user_id: int
    title: str
    task_type: TaskTypeEnum
    task_data: Dict[str, Union[str, List[str], Dict]]  # 해시태그나 키워드 포함
    status: str = "PENDING"


# 수동 작성 콘텐츠는 content 필드가 필수
class ManualContentRequest(BaseModel):
    user_id: int
    title: str
    task_type: str
    content: str
    platform: str
    task_data: dict
    status: str
    scheduled_at: Optional[datetime] = None

class GenerateContentRequest(BaseModel):
    keyword: str