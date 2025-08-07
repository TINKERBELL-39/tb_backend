"""
대화 관리자 - 개선된 버전
✅ 진행형 대화, 질문 배치 개선, 맞춤화 강화, 피로도 관리, 밀도 최적화
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import openai
from general_marketing_tools import MarketingTools
from mcp_marketing_tools import MarketingAnalysisTools

logger = logging.getLogger(__name__)

class MarketingStage(Enum):
    """마케팅 단계 정의"""
    INITIAL = "INITIAL"
    GOAL = "GOAL"
    TARGET = "TARGET"
    STRATEGY = "STRATEGY"
    EXECUTION = "EXECUTION"
    CONTENT_CREATION = "CONTENT_CREATION"
    COMPLETED = "COMPLETED"

class ConversationMode(Enum):
    """대화 모드"""
    QUESTIONING = "QUESTIONING"
    SUGGESTING = "SUGGESTING"
    CONTENT_CREATION = "CONTENT_CREATION"

@dataclass
class ConversationState:
    """대화 상태 관리 - 개선된 버전"""
    user_id: int
    conversation_id: int
    current_stage: MarketingStage = MarketingStage.INITIAL
    current_mode: ConversationMode = ConversationMode.QUESTIONING
    business_type: str = None
    collected_info: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    stage_progress: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # 🆕 개선된 사용자 응답 패턴 추적
    negative_response_count: int = 0
    last_negative_response: Optional[str] = None
    suggestion_attempts: int = 0
    user_engagement_level: str = "high"
    question_fatigue_level: int = 0  # 질문 피로도 추가
    
    # 🆕 대화 진행 추적
    topics_covered: List[str] = field(default_factory=list)  # 다룬 주제들
    last_main_topic: Optional[str] = None  # 마지막 주요 주제
    conversation_depth: int = 0  # 대화 깊이
    
    # 컨텐츠 제작 관련 상태
    current_content_session: Optional[Dict[str, Any]] = None
    content_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 포스팅 관련 상태
    awaiting_posting_confirmation: bool = False
    awaiting_scheduling_time: bool = False
    current_content_for_posting: Optional[Dict[str, Any]] = None
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """메시지 추가 - 토픽 추적 개선"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "stage": self.current_stage.value,
            "mode": self.current_mode.value,
            "conversation_depth": self.conversation_depth
        }
        if metadata:
            message.update(metadata)
        
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
        
        # 🆕 대화 깊이 증가
        if role == "user":
            self.conversation_depth += 1
            
        # 히스토리 크기 제한 (최근 15개만 유지 - 밀도 최적화)
        if len(self.conversation_history) > 15:
            self.conversation_history = self.conversation_history[-15:]
    
    def add_info(self, key: str, value: Any, source: str = "user"):
        """정보 수집 - 토픽 추적 추가"""
        self.collected_info[key] = {
            "value": value,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "conversation_depth": self.conversation_depth
        }
        
        # 🆕 주요 토픽으로 추가
        if key in ["business_type", "product", "main_goal", "target_audience"]:
            if key not in self.topics_covered:
                self.topics_covered.append(key)
                self.last_main_topic = key
    
    def get_info(self, key: str) -> Any:
        """정보 조회"""
        info = self.collected_info.get(key)
        return info["value"] if info else None
    
    # 🆕 질문 피로도 관리
    def increase_question_fatigue(self):
        """질문 피로도 증가"""
        self.question_fatigue_level += 1
        if self.question_fatigue_level >= 3:
            self.user_engagement_level = "medium"
        if self.question_fatigue_level >= 5:
            self.user_engagement_level = "low"
    
    def reset_question_fatigue(self):
        """질문 피로도 리셋"""
        self.question_fatigue_level = 0
        self.user_engagement_level = "high"
    
    def should_avoid_questions(self) -> bool:
        """질문을 피해야 하는지 판단"""
        return (self.question_fatigue_level >= 3 or 
                self.negative_response_count >= 2 or
                self.user_engagement_level == "low")
    
    # 🆕 대화 진행 상황 분석
    def get_conversation_progress(self) -> Dict[str, Any]:
        """대화 진행 상황 종합 분석"""
        return {
            "depth": self.conversation_depth,
            "topics_covered": self.topics_covered,
            "completion_rate": self.get_completion_rate(),
            "engagement_level": self.user_engagement_level,
            "question_fatigue": self.question_fatigue_level,
            "stage": self.current_stage.value,
            "ready_for_next_stage": self.is_ready_for_next_stage(),
            "suggested_next_action": self.get_suggested_next_action()
        }
    
    def is_ready_for_next_stage(self) -> bool:
        """다음 단계 준비 여부"""
        if self.current_stage == MarketingStage.INITIAL:
            return bool(self.business_type and self.business_type != "일반")
        elif self.current_stage == MarketingStage.GOAL:
            return bool(self.get_info('main_goal'))
        elif self.current_stage == MarketingStage.TARGET:
            return bool(self.get_info('target_audience'))
        elif self.current_stage == MarketingStage.STRATEGY:
            return bool(self.get_info('budget') or self.get_info('channels'))
        else:
            return True
    
    def get_suggested_next_action(self) -> str:
        """다음 권장 액션"""
        if self.should_avoid_questions():
            return "provide_suggestions"
        elif self.get_completion_rate() > 0.6:
            return "create_content"
        elif self.is_ready_for_next_stage():
            return "advance_stage"
        else:
            return "gather_info"
    
    # 기존 메서드들 유지...
    def record_negative_response(self, response: str):
        """부정적 응답 기록"""
        self.negative_response_count += 1
        self.last_negative_response = response
        self.increase_question_fatigue()
        
        if self.negative_response_count >= 2:
            self.user_engagement_level = "low"
        elif self.negative_response_count >= 1:
            self.user_engagement_level = "medium"
    
    def reset_negative_responses(self):
        """부정적 응답 카운터 리셋"""
        self.negative_response_count = 0
        self.last_negative_response = None
        self.reset_question_fatigue()
    
    def should_switch_to_suggestion_mode(self) -> bool:
        """제안 모드로 전환해야 하는지 판단"""
        return (self.negative_response_count >= 2 or 
                self.user_engagement_level == "low" or
                self.question_fatigue_level >= 4)
    
    def switch_to_suggestion_mode(self):
        """제안 모드로 전환"""
        self.current_mode = ConversationMode.SUGGESTING
        self.suggestion_attempts += 1
    
    def has_sufficient_info_for_suggestions(self) -> bool:
        """제안을 위한 충분한 정보가 있는지 확인"""
        return (self.business_type != "일반" or 
                self.get_info('product') or 
                self.get_info('business_type') or
                self.get_info('main_goal') or
                len(self.collected_info) > 1)  # 최소 2개 정보 필요
    
    # 컨텐츠 세션 관련 메서드들...
    def start_content_session(self, initial_request: str):
        """컨텐츠 제작 세션 시작"""
        session_data = {
            "initial_request": initial_request,
            "created_at": datetime.now().isoformat(),
            "iteration_count": 1,
            "last_content": None,
            "context_info": {
                "business_type": self.business_type,
                "keywords": self.get_info('keywords'),
                "trend_data": self.get_info('trend_data'),
                "product": self.get_info('product'),
                "target_audience": self.get_info('target_audience'),
                "main_goal": self.get_info('main_goal')
            }
        }
        self.current_content_session = session_data
        self.current_mode = ConversationMode.CONTENT_CREATION
        logger.info(f"컨텐츠 세션 시작: 컨텍스트 정보 포함")
    
    def update_content_session(self, new_content: str, user_feedback: str = None):
        """컨텐츠 제작 세션 업데이트"""
        if self.current_content_session:
            self.current_content_session["last_content"] = new_content
            self.current_content_session["iteration_count"] += 1
            if user_feedback:
                self.current_content_session["last_feedback"] = user_feedback
            logger.info(f"컨텐츠 세션 업데이트: 반복 {self.current_content_session['iteration_count']}회")
    
    def end_content_session(self):
        """컨텐츠 제작 세션 종료"""
        if self.current_content_session:
            self.content_history.append(self.current_content_session.copy())
            self.current_content_session = None
            self.current_mode = ConversationMode.SUGGESTING
            logger.info("컨텐츠 세션 종료")
    
    def is_in_content_creation(self) -> bool:
        """컨텐츠 제작 단계 여부"""
        return self.current_stage == MarketingStage.CONTENT_CREATION and self.current_content_session is not None
    
    # 포스팅 관련 메서드들...
    def start_posting_confirmation(self, content_data: Dict[str, Any]):
        """포스팅 확인 단계 시작"""
        self.awaiting_posting_confirmation = True
        self.current_content_for_posting = content_data
        logger.info(f"포스팅 확인 단계 시작: {content_data.get('type', 'unknown')}")
    
    def confirm_posting_and_request_schedule(self):
        """포스팅 확인 후 스케줄 입력 요청"""
        self.awaiting_posting_confirmation = False
        self.awaiting_scheduling_time = True
        logger.info("포스팅 확인됨, 스케줄 입력 대기 중")
    
    def complete_posting_process(self):
        """포스팅 프로세스 완료"""
        self.awaiting_posting_confirmation = False
        self.awaiting_scheduling_time = False
        self.current_content_for_posting = None
        logger.info("포스팅 프로세스 완료")
    
    def cancel_posting_process(self):
        """포스팅 프로세스 취소"""
        self.awaiting_posting_confirmation = False
        self.awaiting_scheduling_time = False
        self.current_content_for_posting = None
        logger.info("포스팅 프로세스 취소됨")
    
    def is_awaiting_posting_response(self) -> bool:
        """포스팅 관련 응답 대기 중인지 확인"""
        return self.awaiting_posting_confirmation or self.awaiting_scheduling_time
    
    def get_completion_rate(self) -> float:
        """전체 완료율 계산"""
        required_fields = ["business_type", "product", "main_goal", "target_audience", "budget", "channels"]
        completed_fields = sum(1 for field in required_fields if self.get_info(field))
        return completed_fields / len(required_fields)
    
    def get_missing_info(self, for_content_creation: bool = False) -> List[str]:
        """부족한 정보 목록"""
        if for_content_creation:
            has_keywords_or_trends = self.get_info('keywords') or self.get_info('trend_data')
            if has_keywords_or_trends:
                essential_fields = ["business_type", "product"]
                missing = [field for field in essential_fields if not self.get_info(field) and (field != "business_type" or self.business_type == "일반")]
                return missing if len(missing) == len(essential_fields) else []
        
        required_fields = ["business_type", "product", "main_goal", "target_audience", "budget", "channels", "pain_points"]
        return [field for field in required_fields if not self.get_info(field)]
    
    def get_context_based_missing_info(self) -> Dict[str, Any]:
        """🆕 컨텍스트 기반 부족한 정보 분석 - 개선된 버전"""
        missing_info = self.get_missing_info()
        
        # 🆕 단계별 우선순위 정보 정의 (더 세분화)
        stage_priorities = {
            MarketingStage.INITIAL: ["business_type"],
            MarketingStage.GOAL: ["main_goal", "business_type", "product"],
            MarketingStage.TARGET: ["target_audience", "product"],
            MarketingStage.STRATEGY: ["budget", "channels"],
            MarketingStage.EXECUTION: ["channels", "budget"],
            MarketingStage.CONTENT_CREATION: ["product", "target_audience"]
        }
        
        current_priorities = stage_priorities.get(self.current_stage, [])
        priority_missing = [field for field in current_priorities if field in missing_info]
        
        # 🆕 질문 피로도 고려
        can_ask_questions = not self.should_avoid_questions()
        
        return {
            "total_missing": missing_info,
            "priority_missing": priority_missing,
            "completion_rate": self.get_completion_rate(),
            "current_stage": self.current_stage.value,
            "can_proceed": len(priority_missing) <= 1,
            "can_ask_questions": can_ask_questions,
            "suggested_focus": priority_missing[0] if priority_missing else None,
            "alternative_action": "provide_suggestions" if not can_ask_questions else "continue_questioning"
        }

    def get_conversation_context(self) -> str:
        """🆕 개선된 대화 컨텍스트 요약 - 밀도 최적화"""
        context_parts = []
        
        # 핵심 정보만 간결하게
        if self.business_type != "일반":
            context_parts.append(f"업종: {self.business_type}")
        
        # 🆕 대화 진행 상황
        context_parts.append(f"진행도: {self.get_completion_rate():.0%} | 깊이: {self.conversation_depth}")
        context_parts.append(f"참여도: {self.user_engagement_level} | 피로도: {self.question_fatigue_level}")
        
        # 🆕 다룬 주제들
        if self.topics_covered:
            context_parts.append(f"논의 완료: {', '.join(self.topics_covered)}")
        
        # 핵심 수집 정보만 요약
        key_info = {}
        for key, info in self.collected_info.items():
            if key in ['product', 'main_goal', 'target_audience', 'budget']:
                key_info[key] = info["value"]
        
        if key_info:
            context_parts.append(f"핵심 정보: {json.dumps(key_info, ensure_ascii=False)}")
        
        # 최근 대화 3개만 (밀도 최적화)
        recent_messages = self.conversation_history[-3:] if self.conversation_history else []
        if recent_messages:
            context_parts.append("최근 대화:")
            for msg in recent_messages:
                role = "사용자" if msg["role"] == "user" else "AI"
                context_parts.append(f"- {role}: {msg['content'][:80]}...")
        
        return "\n".join(context_parts)
    
    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """세션 만료 확인"""
        expiry_time = self.last_activity + timedelta(minutes=timeout_minutes)
        return datetime.now() > expiry_time

class ConversationManager:
    """🆕 개선된 대화 관리자 - 진행형 대화, 피로도 관리, 맞춤화 강화"""
    
    def __init__(self):
        from config import config
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.temperature = config.TEMPERATURE
        self.conversations: Dict[int, ConversationState] = {}
        
        self._init_enhanced_prompts()
        logger.info("🆕 개선된 ConversationManager 초기화 완료")
    
    def _init_enhanced_prompts(self):
        """🆕 개선된 프롬프트 초기화 - 진행형 대화, 밀도 최적화"""
        
        # 🆕 진행형 대화 생성 프롬프트 (핵심 개선)
        self.progressive_response_prompt = """당신은 친근하고 전문적인 마케팅 컨설턴트입니다. 사용자와 진행형 대화를 나누며 단계적으로 발전시켜 나가세요.

### **응답 원칙 (중요):**

**1. 진행형 대화 구조**
- 이미 논의한 내용은 반복하지 말고, 다음 단계로 자연스럽게 발전
- 이전 대화가 있을 경우에만 "앞서 말씀해주신 [정보]를 바탕으로..." 식으로 이전 정보 활용
- 새로운 관점이나 심화된 조언 제공

**2. 질문 배치 개선**
- 본문에서는 조언과 제안에 집중
- 후속 질문은 **반드시 마지막 문단에만** 배치
- 질문은 최대 2개, 자연스럽게 연결되도록 작성

**3. 맞춤화 강화**
- 사용자의 업종, 제품, 상황을 반영한 구체적 예시
- "일반적으로"보다는 "귀하의 [업종]에서는" 방식으로 표현 (정보가 있을 때만)
- 실제 활용 가능한 방법과 팁 제공

**4. 밀도 최적화**
- 핵심 내용만 간결하게, 불필요한 개행 최소화
- 한 문단에 하나의 주제만 다루기
- 실행 가능한 구체적 방법 우선 제시

**5. 피로도 관리**
- 사용자가 답변하기 어려워하면 직접 제안으로 전환
- 질문보다는 "이런 방법은 어떠세요?" 식 제안 우선
- 과도한 정보 요구 지양

### **응답 구조:**
1. **맥락 인식** (첫 대화면 인사, 이어지는 대화면 이전 맥락 활용)
2. **핵심 조언/제안** (구체적이고 실행 가능한 방법)
3. **맞춤 예시** (사용자 상황 반영, 정보가 있을 때만)
4. **다음 단계 제안** (자연스러운 발전 방향)
5. **후속 질문** (마지막 문단에 1-2개만, 선택적)

### **톤 유지:**
- 친근하면서도 전문적
- 격려하고 지지하는 어조
- 실용적이고 해결 중심적
- 과도한 감탄이나 칭찬 지양

사용자의 현재 상황과 이전 대화를 고려하여 다음 단계로 자연스럽게 이어가는 응답을 작성해주세요. 첫 대화인 경우 자연스러운 인사로 시작하고, 이어지는 대화인 경우에만 이전 정보를 활용하세요."""

        # 🆕 맞춤형 제안 생성 프롬프트
        self.customized_suggestion_prompt = """당신은 경험이 풍부한 마케팅 전문가입니다. 사용자의 구체적 상황에 맞는 실행 가능한 제안을 제공하세요.

### **제안 원칙:**

**1. 맞춤화 우선**
- 업종, 제품, 타겟, 예산 등 모든 정보 활용
- "일반적으로"가 아닌 "귀하의 상황에서는" 접근
- 구체적 예시와 방법 제시

**2. 실행 중심**
- 바로 시작할 수 있는 방법
- 단계별 실행 가이드
- 예상 결과와 효과 설명

**3. 우선순위 제시**
- 가장 효과적인 방법부터 순서대로
- 예산과 상황에 맞는 선택지 제공
- 단기/중기/장기 관점 구분

**4. 실용성 강조**
- 복잡한 이론보다 실무 중심
- 즉시 적용 가능한 팁과 노하우
- 성공 사례 기반 조언

### **제안 구조:**
1. **상황 인식** (사용자 정보 요약)
2. **우선 추천** (가장 효과적인 방법 1-2개)
3. **실행 방법** (구체적 단계)
4. **부가 옵션** (추가 고려사항)
5. **다음 액션** (후속 진행 방향)

사용자의 수집된 정보를 최대한 활용하여 맞춤형 제안을 생성해주세요."""

        # 🆕 단계별 정보 수집 프롬프트
        self.stage_aware_collection_prompt = """당신은 단계별 마케팅 상담 전문가입니다. 사용자의 현재 단계에 맞는 최적의 정보 수집 방법을 선택하세요.

### **단계별 접근:**

**INITIAL 단계:** 업종과 기본 상황 파악
**GOAL 단계:** 마케팅 목표와 원하는 결과
**TARGET 단계:** 고객층과 시장 분석
**STRATEGY 단계:** 예산, 채널, 방향성
**EXECUTION 단계:** 구체적 실행 계획

### **정보 수집 원칙:**

**1. 단계 맞춤**
- 현재 단계에 필요한 정보 우선
- 다음 단계 준비를 위한 부가 정보
- 불필요한 정보 요구 지양

**2. 피로도 고려**
- 사용자 참여도와 피로도 체크
- 부정적 응답 시 제안 모드 전환
- 과도한 질문 연속 방지

**3. 맥락적 수집**
- 이미 수집된 정보 기반 심화 질문
- 업종별 특화 정보 우선
- 실행에 필요한 필수 정보 집중

### **응답 방식:**
- 정보 부족 시: 자연스러운 질문 (최대 2개)
- 충분한 정보: 직접 제안과 조언
- 피로도 높음: 수집된 정보 기반 추천

현재 단계와 사용자 상황을 고려하여 최적의 접근을 선택해주세요."""

        # 기존 프롬프트들 개선
        self.negative_response_detection_prompt = """사용자의 응답이 부정적이거나 정보 제공을 거부하는 내용인지 분석해주세요.

분석 대상:
- "몰라", "모르겠어", "잘 모르겠어"
- "니가 알려줘", "당신이 말해줘", "추천해줘"
- "잘 모르겠는데", "확실하지 않아"
- "그냥", "아무거나", "상관없어"
- "별로", "싫어", "안 좋아"

JSON 형식으로 답변:
{
    "is_negative": true/false,
    "type": "no_knowledge|request_suggestion|indifferent|rejection|neutral",
    "confidence": 0.0-1.0,
    "suggested_action": "switch_to_suggestion|continue_questioning|provide_options"
}"""

        # 🆕 컨텐츠 피드백 분석 프롬프트 개선
        self.content_feedback_prompt = """사용자의 콘텐츠 관련 피드백을 분석하여 다음 액션을 결정해주세요.

분석 항목:
- 만족도 (높음/보통/낮음)
- 수정 요청 여부 및 구체적 내용
- 추가 생성 요청 여부
- 포스팅 의향

JSON 형식으로 답변:
{
    "request_type": "modify|regenerate|new_content|approval|feedback",
    "satisfaction_level": "high|medium|low",
    "specific_changes": ["구체적인 수정 요청들"],
    "content_direction": {
        "tone": "변경하고자 하는 톤",
        "style": "변경하고자 하는 스타일",
        "focus": "집중하고자 하는 포인트"
    },
    "action_needed": {
        "type": "revise_content|create_new|provide_feedback|end_session",
        "priority": "high|medium|low"
    }
}"""

        # 🆕 사용자 의도 분석 프롬프트 개선
        self.intent_analysis_prompt = """사용자의 메시지를 분석하여 마케팅 상담에서의 의도와 정보를 추출해주세요.

분석 항목:
1. 주요 의도 (정보 요청, 목표 설정, 콘텐츠 생성 등)
2. 추출 가능한 비즈니스 정보
3. 현재 단계 완료 여부
4. 사용자 감정 상태

JSON 형식으로 답변:
{
    "intent": {
        "primary": "정보_요청|목표_설정|타겟_분석|전략_기획|콘텐츠_생성|일반_질문",
        "confidence": 0.0-1.0,
        "description": "의도 설명"
    },
    "extracted_info": {
        "business_type": "추출된 업종 (없으면 null)",
        "product": "제품/서비스 정보 (없으면 null)",
        "main_goal": "주요 목표 (없으면 null)",
        "target_audience": "타겟 고객 (없으면 null)",
        "budget": "예산 정보 (없으면 null)",
        "channels": "선호 채널 (없으면 null)"
    },
    "stage_assessment": {
        "current_stage_complete": true/false,
        "ready_for_next": true/false,
        "suggested_next_stage": "goal|target|strategy|execution|content_creation"
    },
    "user_sentiment": {
        "engagement_level": "high|medium|low",
        "frustration_level": "none|low|medium|high",
        "needs_encouragement": true/false
    }
}"""
    
    async def _call_enhanced_llm(self, prompt: str, user_input: str, context: str = "") -> Dict[str, Any]:
        """🆕 개선된 LLM 호출 - 더 안정적인 파싱"""
        try:
            full_prompt = f"""
{prompt}

현재 상황:
{context}

사용자 입력:
"{user_input}"
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_prompt}
                ],
                temperature=self.temperature,
                max_tokens=1200  # 토큰 수 증가
            )
            
            content = response.choices[0].message.content
            
            try:
                # JSON 블록 추출 시도 (개선된 파싱)
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_content = content[json_start:json_end].strip()
                elif "{" in content and "}" in content:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    json_content = content[json_start:json_end]
                else:
                    # JSON이 없으면 텍스트 응답으로 처리
                    return {"raw_response": content}
                
                parsed_result = json.loads(json_content)
                
                # 필수 필드 검증
                if isinstance(parsed_result, dict):
                    return parsed_result
                else:
                    return {"raw_response": content}
                
            except json.JSONDecodeError:
                return {"raw_response": content}
                
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return {"error": str(e)}
    
    
    def detect_topic_shift(self, primary_intent: str, conversation: ConversationState) -> bool:
        """
        멀티턴 대화 중 주제 전환 여부 감지.
        - 콘텐츠 생성 단계에서 전략/정보 요청 등 새로운 주제 발생 시 True 반환
        - 다른 Stage에서도 이전 토픽과 전혀 관련 없는 질문이면 Stage 리셋 가능
        """
        # 콘텐츠 피드백 루프에서 벗어나야 할 조건
        if conversation.is_in_content_creation() and primary_intent not in ["콘텐츠_생성", "피드백", "수정"]:
            logger.info(f"[{conversation.conversation_id}] 콘텐츠 피드백 루프 중 새로운 주제 감지 → Stage STRATEGY로 전환")
            conversation.end_content_session()
            conversation.current_stage = MarketingStage.STRATEGY
            conversation.current_mode = ConversationMode.QUESTIONING
            return True

        # Stage와 무관하게 대화 주제 변화 감지 (비즈니스 맥락과 무관한 질문 등)
        unrelated_intents = ["일반_질문", "정보_요청", "전략_기획"]
        if primary_intent in unrelated_intents and conversation.current_stage == MarketingStage.CONTENT_CREATION:
            logger.info(f"[{conversation.conversation_id}] 콘텐츠 생성 단계에서 다른 주제 감지 → Stage STRATEGY로 전환")
            conversation.current_stage = MarketingStage.STRATEGY
            conversation.current_mode = ConversationMode.QUESTIONING
            return True

        return False

    
    # 🆕 핵심 개선 메서드: 진행형 대화 생성
    async def generate_progressive_response(self, user_input: str, conversation: ConversationState) -> str:
        """🆕 진행형 대화 응답 생성 - 핵심 개선 메서드"""
        conversation.add_message("user", user_input)
        logger.info(f"[{conversation.conversation_id}] 진행형 대화 처리: {user_input[:50]}")

        try:
            # 🆕 포스팅 관련 응답 처리 우선
            if conversation.is_awaiting_posting_response():
                return await self._handle_posting_response(user_input, conversation)
            
            # 🆕 컨텐츠 제작 세션 중인지 확인
            if conversation.is_in_content_creation():
                return await self._handle_content_creation_session(user_input, conversation)
            
            # 🆕 부정적 응답 감지 및 피로도 관리
            negative_analysis = await self.detect_negative_response(user_input, conversation)
            if negative_analysis.get("is_negative", False):
                conversation.record_negative_response(user_input)
                
                # 제안 모드로 전환
                if conversation.should_switch_to_suggestion_mode():
                    conversation.switch_to_suggestion_mode()
                    
                    if conversation.has_sufficient_info_for_suggestions():
                        response = await self.generate_customized_suggestions(conversation)
                    else:
                        response = await self.generate_minimal_info_suggestions(user_input, conversation)
                    
                    conversation.add_message("assistant", response)
                    return response
            else:
                conversation.reset_negative_responses()
            
            # 🆕 사용자 의도 분석 및 정보 추출
            intent_analysis = await self.analyze_user_intent_enhanced(user_input, conversation)
            logger.info(f"[{conversation.conversation_id}] 의도 분석: {intent_analysis.get('intent', {}).get('primary', 'unknown')}")

            # 추출된 정보 저장
            extracted_info = intent_analysis.get("extracted_info", {})
            for key, value in extracted_info.items():
                if value:
                    conversation.add_info(key, value, "llm_extracted")
                    if key == "business_type" and value != "일반":
                        conversation.business_type = value
      
            primary_intent = intent_analysis.get('intent', {}).get('primary', '')
            
            # 🆕 주제 전환 감지 및 Stage 전환
            if self.detect_topic_shift(primary_intent, conversation):
                logger.info(f"[{conversation.conversation_id}] 주제 전환 처리 완료")
                
            # 새로운 주제 탐지 로직 추가
            if conversation.is_in_content_creation() and primary_intent not in ["콘텐츠_생성", "피드백", "수정"]:
                logger.info(f"[{conversation.conversation_id}] 새로운 주제 감지: 콘텐츠 세션 종료 및 단계 리셋")
                conversation.end_content_session()
                conversation.current_stage = MarketingStage.STRATEGY
                conversation.current_mode = ConversationMode.QUESTIONING
            
            # 🆕 컨텐츠 생성 요청 감지 (개선된 조건)
            has_basic_info = self._has_sufficient_context_for_content(conversation)
            
            if primary_intent == "콘텐츠_생성" and has_basic_info and extracted_info.get("channels"):
                # conversation.current_stage = MarketingStage.CONTENT_CREATION
                # conversation.start_content_session(user_input)
                # return "TRIGGER_CONTENT_GENERATION"
                conversation.current_stage = MarketingStage.CONTENT_CREATION
                conversation.start_content_session(user_input)
                return await self._handle_content_creation_session(user_input, conversation, is_initial=True)

            # 🆕 대화 진행 방식 결정
            progress_info = conversation.get_conversation_progress()
            suggested_action = progress_info["suggested_next_action"]
            
            if suggested_action == "provide_suggestions":
                # 제안 중심 응답
                conversation.switch_to_suggestion_mode()
                response = await self.generate_customized_suggestions(conversation)
            elif suggested_action == "create_content":
                # 컨텐츠 생성 제안
                if conversation.is_in_content_creation():
                    return await self._handle_content_creation_session(user_input, conversation)
            else:
                # 진행형 대화 계속
                response = await self.generate_stage_aware_response(user_input, conversation)
            
            conversation.add_message("assistant", response)
            return response

        except Exception as e:
            logger.error(f"[{conversation.conversation_id}] 진행형 응답 생성 중 오류: {e}", exc_info=True)
            error_prompt = "대화 중 기술적 문제가 발생했을 때 친근하게 사과하고 다시 시도를 요청하는 메시지를 생성해주세요."
            error_result = await self._call_enhanced_llm(error_prompt, "", "")
            return error_result.get("raw_response", "죄송합니다. 잠시 문제가 발생했네요. 다시 한 번 말씀해주시면 도움을 드리겠습니다!")
    
    # 🆕 맞춤형 제안 생성
    async def generate_customized_suggestions(self, conversation: ConversationState) -> str:
        """🆕 맞춤형 제안 생성 - 수집된 정보 최대 활용"""
        context = f"""
        업종: {conversation.business_type}
        완료율: {conversation.get_completion_rate():.0%}
        대화 깊이: {conversation.conversation_depth}
        참여도: {conversation.user_engagement_level}
        
        수집된 정보:
        {json.dumps(conversation.collected_info, ensure_ascii=False)}
        
        다룬 주제: {', '.join(conversation.topics_covered)}
        
        대화 맥락:
        {conversation.get_conversation_context()}
        """
        
        result = await self._call_enhanced_llm(self.customized_suggestion_prompt, "", context)
        return result.get("raw_response", "지금까지의 정보를 바탕으로 맞춤형 전략을 추천해드리겠습니다!")
    
    # 🆕 단계별 인식 응답 생성
    async def generate_stage_aware_response(self, user_input: str, conversation: ConversationState) -> str:
        """🆕 단계별 맞춤 응답 생성"""
        context = f"""
        현재 단계: {conversation.current_stage.value}
        다음 단계 준비: {conversation.is_ready_for_next_stage()}
        완료율: {conversation.get_completion_rate():.0%}
        질문 피로도: {conversation.question_fatigue_level}
        부족한 정보: {conversation.get_context_based_missing_info()}
        
        업종: {conversation.business_type}
        수집된 정보: {json.dumps(conversation.collected_info, ensure_ascii=False)}
        
        대화 맥락:
        {conversation.get_conversation_context()}
        """
        
        # 질문 피로도가 높으면 제안 프롬프트 사용
        if conversation.should_avoid_questions():
            result = await self._call_enhanced_llm(self.customized_suggestion_prompt, user_input, context)
        else:
            result = await self._call_enhanced_llm(self.progressive_response_prompt, user_input, context)
        
        return result.get("raw_response", "")
    
    # 🆕 컨텐츠 생성 제안
    async def suggest_content_creation(self, conversation: ConversationState) -> str:
        """🆕 컨텐츠 생성 제안"""
        context = f"""
        업종: {conversation.business_type}
        제품: {conversation.get_info('product')}
        타겟: {conversation.get_info('target_audience')}
        목표: {conversation.get_info('main_goal')}
        완료율: {conversation.get_completion_rate():.0%}
        """
        
        prompt = """사용자의 마케팅 정보가 충분히 수집되어 이제 실제 컨텐츠를 만들 시점임을 알리고, 다양한 컨텐츠 옵션을 제안하는 메시지를 작성해주세요.

제안할 컨텐츠 유형:
- 인스타그램 포스트
- 블로그 포스트  
- 마케팅 전략서
- 캠페인 기획서

**중요**: 사용자의 업종, 제품, 타겟 고객, 목표를 분석하여 어떤 컨텐츠 유형이 가장 적합한지 구체적으로 추천해주세요. 예를 들어:
- B2C 제품이고 젊은 타겟이면 인스타그램 포스트 우선 추천
- B2B 서비스면 블로그 포스트나 마케팅 전략서 추천
- 신제품 런칭이 목표면 캠페인 기획서 추천
- 브랜드 인지도 향상이 목표면 다양한 컨텐츠 조합 추천

각 옵션의 특징을 간단히 설명하고, 사용자 상황에 맞는 1-2개의 컨텐츠를 우선 추천한 후, 어떤 것을 먼저 만들어볼지 자연스럽게 물어보세요."""
        
        result = await self._call_enhanced_llm(prompt, "", context)
        return result.get("raw_response", "이제 실제 마케팅 컨텐츠를 만들어볼까요?")
    
    # 🆕 최소 정보 제안
    async def generate_minimal_info_suggestions(self, user_input: str, conversation: ConversationState) -> str:
        """🆕 최소 정보로도 도움이 되는 제안 생성"""
        context = f"""
        현재 수집된 정보: {json.dumps(conversation.collected_info, ensure_ascii=False)}
        업종: {conversation.business_type}
        대화 깊이: {conversation.conversation_depth}
        사용자 부정적 응답: {user_input}
        """
        
        prompt = """사용자가 구체적인 정보를 제공하기 어려워하지만, 현재까지 수집된 최소한의 정보라도 활용하여 도움이 되는 마케팅 조언을 제공해주세요.

조언 방향:
- 일반적이지만 실용적인 마케팅 팁
- 업종별 기본 전략 (업종 정보가 있는 경우)
- 시작하기 쉬운 마케팅 방법
- 정보 부족 시에도 할 수 있는 기본 준비사항

친근하고 격려하는 톤으로 작성하되, 구체적이고 실행 가능한 조언을 포함해주세요."""
        
        result = await self._call_enhanced_llm(prompt, user_input, context)
        return result.get("raw_response", "괜찮습니다! 지금 상황에서도 시작할 수 있는 마케팅 방법들을 알려드릴게요.")
    
    # 🆕 충분한 컨텍스트 확인
    def _has_sufficient_context_for_content(self, conversation: ConversationState) -> bool:
        """🆕 컨텐츠 생성을 위한 충분한 컨텍스트 확인"""
        # 기본 정보 확인
        has_basic_info = (conversation.business_type and conversation.business_type != "일반") or conversation.get_info('product')
        
        # 키워드나 트렌드 데이터가 있으면 추가 점수
        has_keywords_or_trends = conversation.get_info('keywords') or conversation.get_info('trend_data')
        
        # 완료율이 30% 이상이거나 키워드/트렌드 데이터가 있으면 충분
        return has_basic_info or has_keywords_or_trends or conversation.get_completion_rate() > 0.3
    
    # 기존 메서드들 개선...
    async def detect_negative_response(self, user_input: str, conversation: ConversationState) -> Dict[str, Any]:
        """부정적 응답 감지 - 개선된 버전"""
        context = f"""
        현재 대화 모드: {conversation.current_mode.value}
        부정적 응답 횟수: {conversation.negative_response_count}
        질문 피로도: {conversation.question_fatigue_level}
        사용자 참여도: {conversation.user_engagement_level}
        """
        
        result = await self._call_enhanced_llm(self.negative_response_detection_prompt, user_input, context)
        
        if "error" in result:
            return {"is_negative": False, "type": "neutral", "confidence": 0.0}
        
        return result
    
    async def analyze_user_intent_enhanced(self, user_input: str, conversation: ConversationState) -> Dict[str, Any]:
        """🆕 개선된 사용자 의도 분석"""
        context = f"""
        현재 단계: {conversation.current_stage.value}
        현재 모드: {conversation.current_mode.value}
        업종: {conversation.business_type}
        완료율: {conversation.get_completion_rate():.0%}
        대화 깊이: {conversation.conversation_depth}
        다룬 주제: {', '.join(conversation.topics_covered)}
        질문 피로도: {conversation.question_fatigue_level}
        
        대화 컨텍스트:
        {conversation.get_conversation_context()}
        """
        
        result = await self._call_enhanced_llm(self.intent_analysis_prompt, user_input, context)
        
        if result.get("intent", {}).get("primary") in ["전략_기획", "정보_요청"] and conversation.current_stage == MarketingStage.CONTENT_CREATION:
            logger.info(f"[{conversation.conversation_id}] 새로운 전략 질문 감지 → Stage STRATEGY로 복귀")
            conversation.current_stage = MarketingStage.STRATEGY
            conversation.current_mode = ConversationMode.QUESTIONING

        # 기본값 설정 (개선된 버전)
        if "error" in result:
            return {
                "intent": {"primary": "일반_질문", "confidence": 0.5},
                "extracted_info": {},
                "stage_assessment": {"current_stage_complete": False, "ready_for_next": False},
                "user_sentiment": {"engagement_level": "medium", "frustration_level": "none", "needs_encouragement": False}
            }
        
        return result

    async def handle_content_feedback_enhanced(self, user_input: str, conversation: ConversationState) -> Dict[str, Any]:
        """🆕 개선된 컨텐츠 피드백 처리"""
        context = f"""
        현재 컨텐츠 세션: {conversation.current_content_session}
        이전 컨텐츠: {conversation.current_content_session.get('last_content', '') if conversation.current_content_session else ''}
        반복 횟수: {conversation.current_content_session.get('iteration_count', 0) if conversation.current_content_session else 0}
        """
        
        result = await self._call_enhanced_llm(self.content_feedback_prompt, user_input, context)
        
        if "error" in result:
            return {
                "request_type": "feedback",
                "satisfaction_level": "medium",
                "specific_changes": [],
                "content_direction": {},
                "action_needed": {"type": "provide_feedback", "priority": "medium"}
            }
        
        return result

    # 기존 메서드들 유지하되 개선...
    async def _handle_posting_response(self, user_input: str, conversation: ConversationState) -> str:
        """포스팅 관련 응답 처리 - 개선된 버전"""
        user_input_lower = user_input.lower().strip()
        
        if conversation.awaiting_posting_confirmation:
            if any(word in user_input_lower for word in ["네", "예", "포스팅", "posting", "업로드", "게시"]):
                conversation.confirm_posting_and_request_schedule()
                
                prompt = "사용자가 포스팅을 확인했을 때, 친근하게 언제 포스팅할지 시간을 물어보는 메시지를 생성해주세요. 다양한 시간 입력 예시도 포함해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                return result.get("raw_response", "포스팅 일정을 알려주세요!")
            else:
                conversation.cancel_posting_process()
                conversation.end_content_session()
                conversation.current_stage = MarketingStage.COMPLETED
                
                prompt = "포스팅을 취소했을 때 자연스럽게 컨텐츠 제작 완료를 알리고 추가 도움을 제안하는 메시지를 생성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                return result.get("raw_response", "컨텐츠 제작이 완료되었습니다!")
        
        elif conversation.awaiting_scheduling_time:
            try:
                scheduled_at = await self._parse_schedule_time(user_input)
                
                if scheduled_at:
                    return f"TRIGGER_AUTOMATION_TASK:{scheduled_at.isoformat()}|자동화 예약이 완료되었습니다!"
                else:
                    prompt = "시간 형식을 인식할 수 없을 때 친근하게 다시 입력을 요청하는 메시지를 생성해주세요."
                    result = await self._call_enhanced_llm(prompt, "", "")
                    return result.get("raw_response", "시간 형식을 다시 확인해주세요.")
            except Exception as e:
                logger.error(f"스케줄 파싱 오류: {e}")
                prompt = "시간 처리 중 오류가 발생했을 때 사과하고 다시 시도를 요청하는 메시지를 생성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                return result.get("raw_response", "시간 처리 중 문제가 발생했습니다. 다시 시도해주세요.")
        
        return "예상치 못한 포스팅 상태입니다."
    
    async def _handle_content_creation_session(self, user_input: str, conversation: ConversationState, is_initial: bool = False) -> str:
        """컨텐츠 제작 세션 처리 - 개선된 버전"""
        if is_initial:
                prompt = f"'{user_input}'라는 컨텐츠를 작성할 계획입니다. {conversation.business_type} 업종, {conversation.get_info('product')} 제품, {conversation.get_info('target_audience')} 타겟을 고려한 캠페인 기획서 초안을 작성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                conversation.update_content_session(result.get("raw_response", "초안 생성 실패"))
                return result.get("raw_response", "컨텐츠 제작을 시작합니다!")
        else:
            # 개선된 피드백 처리
            feedback_analysis = await self.handle_content_feedback_enhanced(user_input, conversation)
            
            request_type = feedback_analysis.get("request_type", "feedback")
            
            if request_type == "modify":
                prompt = "사용자가 컨텐츠 수정을 요청했을 때 친근하게 수정하겠다고 알리는 메시지를 생성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                conversation.update_content_session("수정 중...", user_input)
                return "TRIGGER_CONTENT_MODIFICATION:" + result.get("raw_response", "컨텐츠를 수정하겠습니다!")
                
            elif request_type == "regenerate":
                prompt = "새로운 컨텐츠를 생성하겠다고 친근하게 알리는 메시지를 생성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                conversation.update_content_session("재생성 중...", user_input)
                return "TRIGGER_CONTENT_REGENERATION:" + result.get("raw_response", "새로운 컨텐츠를 생성하겠습니다!")
                
            elif request_type == "approval":
                if conversation.current_content_for_posting:
                    prompt = "사용자가 컨텐츠를 마음에 들어할 때 포스팅 여부를 친근하게 묻는 메시지를 생성해주세요."
                    result = await self._call_enhanced_llm(prompt, "", "")
                    conversation.start_posting_confirmation(conversation.current_content_for_posting)
                    return result.get("raw_response", "포스팅하시겠습니까?")
                else:
                    prompt = "컨텐츠 제작이 완료되었을 때 추가 도움을 제안하는 메시지를 생성해주세요."
                    result = await self._call_enhanced_llm(prompt, "", "")
                    conversation.end_content_session()
                    conversation.current_stage = MarketingStage.COMPLETED
                    return result.get("raw_response", "컨텐츠 제작이 완료되었습니다!")
            else:
                prompt = "사용자의 피드백에 감사를 표하고 더 구체적인 수정 방향을 묻는 메시지를 생성해주세요."
                result = await self._call_enhanced_llm(prompt, "", "")
                return result.get("raw_response", "피드백 감사합니다!")

    async def _parse_schedule_time(self, user_input: str) -> Optional[datetime]:
        """사용자 입력에서 시간 파싱 - 개선된 버전"""
        user_input_lower = user_input.lower().strip()
        
        # 지금 바로
        if any(word in user_input_lower for word in ["지금", "바로", "now", "immediately"]):
            return datetime.now()
        
        # LLM을 사용한 시간 파싱
        try:
            time_parsing_prompt = f"""다음 사용자 입력에서 날짜와 시간을 추출하여 ISO 8601 형식으로 반환해주세요.
            
사용자 입력: "{user_input}"
현재 시간: {datetime.now().isoformat()}

다음 형식으로만 응답해주세요:
- 성공: "2024-01-15T14:30:00" (정확한 ISO 8601 형식)
- 실패: "INVALID"

추가 설명 없이 오직 날짜/시간 또는 "INVALID"만 반환하세요."""
            
            result = await self._call_enhanced_llm("당신은 시간 파싱 전문가입니다.", time_parsing_prompt)
            
            if isinstance(result, dict) and "raw_response" in result:
                time_str = result["raw_response"].strip()
            else:
                time_str = str(result).strip()
            
            if time_str != "INVALID" and "T" in time_str:
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                
        except Exception as e:
            logger.warning(f"시간 파싱 실패: {e}")
        
        return None
    
    # 대화 관리 관련 메서드들 (기존 유지)
    def get_or_create_conversation(self, user_id: int, conversation_id: Optional[int] = None) -> Tuple[ConversationState, bool]:
        """대화 상태 조회 또는 생성"""
        if conversation_id is None:
            conversation_id = self._generate_conversation_id(user_id)
        
        if conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
            if conversation.is_expired():
                logger.info(f"만료된 대화 재시작: {conversation_id}")
                conversation = ConversationState(user_id, conversation_id)
                self.conversations[conversation_id] = conversation
                return conversation, True
            return conversation, False
        
        conversation = ConversationState(user_id, conversation_id)
        self.conversations[conversation_id] = conversation
        logger.info(f"새 대화 시작: user_id={user_id}, conversation_id={conversation_id}")
        return conversation, True
    
    def _generate_conversation_id(self, user_id: int) -> int:
        """대화 ID 생성"""
        import time
        return int(f"{user_id}{int(time.time())}")
    
    def get_conversation_summary(self, conversation_id: int) -> Dict[str, Any]:
        """🆕 개선된 대화 요약 정보"""
        if conversation_id not in self.conversations:
            return {"error": "대화를 찾을 수 없습니다"}
        
        conversation = self.conversations[conversation_id]
        
        return {
            "conversation_id": conversation_id,
            "user_id": conversation.user_id,
            "current_stage": conversation.current_stage.value,
            "current_mode": conversation.current_mode.value,
            "business_type": conversation.business_type,
            "completion_rate": conversation.get_completion_rate(),
            "conversation_depth": conversation.conversation_depth,
            "topics_covered": conversation.topics_covered,
            "collected_info_count": len(conversation.collected_info),
            "message_count": len(conversation.conversation_history),
            "created_at": conversation.created_at.isoformat(),
            "last_activity": conversation.last_activity.isoformat(),
            "user_engagement_level": conversation.user_engagement_level,
            "question_fatigue_level": conversation.question_fatigue_level,
            "negative_response_count": conversation.negative_response_count,
            "in_content_creation": conversation.is_in_content_creation(),
            "progress_info": conversation.get_conversation_progress(),
            "features": [
                "progressive_conversation", 
                "fatigue_management", 
                "stage_awareness", 
                "contextual_customization", 
                "density_optimization"
            ]
        }
    
    def cleanup_expired_conversations(self):
        """만료된 대화 정리"""
        expired_ids = []
        for conv_id, conv in self.conversations.items():
            if conv.is_expired():
                expired_ids.append(conv_id)
        
        for conv_id in expired_ids:
            del self.conversations[conv_id]
            logger.info(f"만료된 대화 정리: {conv_id}")
        
        return len(expired_ids)
