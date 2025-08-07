"""
Enhanced Marketing Agent State Management
완전히 개선된 마케팅 에이전트 상태 관리

✅ 핵심 개선사항:
- 통합된 상태 관리
- 명확한 진행 조건
- 효율적인 정보 추적
- 컨텍스트 인식 강화
"""

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)

class MarketingStage(Enum):
    """마케팅 상담 단계"""
    INITIAL = "initial"           # 기본 정보 수집
    GOAL_SETTING = "goal_setting" # 목표 설정
    TARGET_ANALYSIS = "target"    # 타겟 분석
    STRATEGY = "strategy"         # 전략 수립
    CONTENT_CREATION = "content"  # 콘텐츠 생성
    EXECUTION = "execution"       # 실행 가이드
    COMPLETED = "completed"       # 완료

class InfoCategory(Enum):
    """정보 카테고리"""
    BASIC = "basic"           # 업종, 제품 등 기본 정보
    GOAL = "goal"            # 목표, 예산 등 목표 관련
    TARGET = "target"        # 타겟 고객 관련
    CHANNEL = "channel"      # 마케팅 채널 관련
    CONTENT = "content"      # 콘텐츠 관련

@dataclass
class CollectedInfo:
    """수집된 정보 데이터 클래스"""
    value: Any
    category: InfoCategory
    source: str  # "user_input", "extracted", "inferred"
    confidence: float  # 0.0 - 1.0
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "category": self.category.value,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class ConversationContext:
    """대화 컨텍스트 관리"""
    user_id: int
    conversation_id: int
    current_stage: MarketingStage = MarketingStage.INITIAL
    flags: Dict[str, Any] = field(default_factory=dict)

    # 🔥 핵심 개선: 체계적 정보 관리
    collected_info: Dict[str, CollectedInfo] = field(default_factory=dict)
    required_info: Dict[MarketingStage, Set[str]] = field(default_factory=lambda: {
        MarketingStage.INITIAL: {"business_type", "product"},
        MarketingStage.GOAL_SETTING: {"main_goal"},
        MarketingStage.TARGET_ANALYSIS: {"target_audience"},
        MarketingStage.STRATEGY: {"budget", "channels"},
        MarketingStage.CONTENT_CREATION: {"business_type", "product"},
    })
    
    # 대화 이력
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 사용자 상태 추적
    user_engagement: str = "high"  # high, medium, low
    question_fatigue: int = 0
    negative_responses: int = 0
    
    # 세션 메타데이터
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # 🔥 핵심 개선: 명확한 진행 조건
    def can_proceed_to_next_stage(self) -> bool:
        """다음 단계로 진행 가능한지 명확한 조건 확인"""
        required = self.required_info.get(self.current_stage, set())
        
        if not required:
            return True
            
        # 필수 정보 확인
        collected_keys = set(self.collected_info.keys())
        missing_required = required - collected_keys
        
        # 필수 정보가 모두 수집되었거나, 사용자가 더 이상 답하지 않으려 할 때
        if not missing_required or self.should_skip_questions():
            return True
            
        return False
    
    def should_skip_questions(self) -> bool:
        """질문을 건너뛰어야 하는지 판단"""
        return (
            self.question_fatigue >= 3 or
            self.negative_responses >= 2 or
            self.user_engagement == "low"
        )
    
    # 🔥 핵심 개선: 수집된 정보 기반 컨텍스트 생성
    def get_context_summary(self) -> str:
        """수집된 정보를 바탕으로 명확한 컨텍스트 요약 (다음 단계 정보 포함)"""
        context_parts = []
        
        # 현재 단계와 진행 상황
        context_parts.append(f"현재 단계: {self.current_stage.value}")
        
        # 수집된 정보 요약 (카테고리별)
        info_by_category = {}
        for key, info in self.collected_info.items():
            category = info.category.value
            if category not in info_by_category:
                info_by_category[category] = {}
            info_by_category[category][key] = info.value
        
        if info_by_category:
            context_parts.append("수집된 정보:")
            for category, items in info_by_category.items():
                context_parts.append(f"  {category}: {json.dumps(items, ensure_ascii=False)}")
        
        # 사용자 상태
        context_parts.append(f"사용자 참여도: {self.user_engagement}")
        context_parts.append(f"질문 피로도: {self.question_fatigue}")
        
        return "\n".join(context_parts)

    
    def get_missing_required_info(self) -> List[str]:
        """현재 단계에서 부족한 필수 정보 목록"""
        required = self.required_info.get(self.current_stage, set())
        collected_keys = set(self.collected_info.keys())
        missing = required - collected_keys
        return list(missing)
    
    def add_info(self, key: str, value: Any, category: InfoCategory, 
                source: str = "user_input", confidence: float = 1.0):
        """정보 추가 with 메타데이터"""
        self.collected_info[key] = CollectedInfo(
            value=value,
            category=category,
            source=source,
            confidence=confidence,
            timestamp=datetime.now()
        )
        self.last_activity = datetime.now()
        logger.info(f"정보 수집: {key} = {value} (카테고리: {category.value})")
    
    def get_info_value(self, key: str) -> Any:
        """정보 값 조회"""
        info = self.collected_info.get(key)
        return info.value if info else None
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """메시지 추가"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "stage": self.current_stage.value
        }
        if metadata:
            message.update(metadata)
        
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
        
        # 대화 이력 크기 제한
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
    
    def record_negative_response(self):
        """부정적 응답 기록"""
        self.negative_responses += 1
        self.question_fatigue += 1
        
        if self.negative_responses >= 2:
            self.user_engagement = "low"
        elif self.negative_responses >= 1:
            self.user_engagement = "medium"
    
    def reset_engagement(self):
        """참여도 리셋"""
        self.negative_responses = 0
        self.question_fatigue = 0
        self.user_engagement = "high"
    
    def advance_stage(self, next_stage: MarketingStage):
        """다음 단계로 진행"""
        logger.info(f"단계 진행: {self.current_stage.value} → {next_stage.value}")
        self.current_stage = next_stage
        self.reset_engagement()  # 새 단계에서는 참여도 리셋
    
    def get_completion_rate(self) -> float:
        """전체 완료율 계산"""
        total_required = 0
        total_collected = 0
        
        for stage, required_set in self.required_info.items():
            stage_weight = self._get_stage_weight(stage)
            total_required += len(required_set) * stage_weight
            
            for req_key in required_set:
                if req_key in self.collected_info:
                    total_collected += stage_weight
        
        return total_collected / total_required if total_required > 0 else 0.0
    
    def _get_stage_weight(self, stage: MarketingStage) -> float:
        """단계별 가중치"""
        weights = {
            MarketingStage.INITIAL: 2.0,      # 기본 정보가 가장 중요
            MarketingStage.GOAL_SETTING: 1.5,
            MarketingStage.TARGET_ANALYSIS: 1.5,
            MarketingStage.STRATEGY: 1.0,
            MarketingStage.CONTENT_CREATION: 0.5
        }
        return weights.get(stage, 1.0)

class EnhancedStateManager:
    """개선된 상태 관리자"""
    
    def __init__(self):
        self.conversations: Dict[int, ConversationContext] = {}
    
    def get_or_create_conversation(self, user_id: int, conversation_id: int) -> ConversationContext:
        """대화 컨텍스트 조회 또는 생성"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext(
                user_id=user_id,
                conversation_id=conversation_id
            )
            logger.info(f"새 대화 생성: {conversation_id}")
        
        return self.conversations[conversation_id]
    
    def extract_info_from_text(self, text: str) -> Dict[str, tuple]:
        """텍스트에서 정보 추출 (규칙 기반)"""
        extracted = {}
        text_lower = text.lower()
        
        # 업종 추출
        business_patterns = {
            "카페": ["카페", "커피", "음료"],
            "온라인쇼핑몰": ["쇼핑몰", "이커머스", "온라인"],
            "뷰티": ["뷰티", "화장품", "미용"],
            "음식점": ["식당", "레스토랑", "음식"],
            "헬스": ["헬스", "운동", "피트니스", "체육관"]
        }
        
        for business_type, keywords in business_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                extracted["business_type"] = (business_type, InfoCategory.BASIC)
                break
        
        # 목표 추출
        goal_patterns = {
            "매출증대": ["매출", "수익", "판매", "돈"],
            "브랜드인지도": ["인지도", "브랜드", "알려", "유명"],
            "신규고객": ["고객", "손님", "방문", "신규"]
        }
        
        for goal_type, keywords in goal_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                extracted["main_goal"] = (goal_type, InfoCategory.GOAL)
                break
        
        # 타겟 추출
        if any(word in text_lower for word in ["20대", "청년"]):
            extracted["target_audience"] = ("20대", InfoCategory.TARGET)
        elif any(word in text_lower for word in ["30대", "직장인"]):
            extracted["target_audience"] = ("30대 직장인", InfoCategory.TARGET)
        
        # 채널 추출
        channel_patterns = {
            "인스타그램": ["인스타", "instagram"],
            "페이스북": ["페이스북", "facebook"],
            "블로그": ["블로그", "blog"],
            "유튜브": ["유튜브", "youtube"]
        }
        
        for channel, keywords in channel_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                if "channels" not in extracted:
                    extracted["channels"] = ([], InfoCategory.CHANNEL)
                extracted["channels"][0].append(channel)
        
        return extracted

# 전역 상태 관리자 인스턴스
enhanced_state_manager = EnhancedStateManager()
