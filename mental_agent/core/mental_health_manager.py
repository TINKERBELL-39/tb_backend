"""
통합 정신건강 에이전트 매니저 - 멀티턴 대화 시스템
마케팅 에이전트의 구조를 참고하여 리팩토링
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import json
from datetime import datetime
from fastapi import Body

# 공통 모듈 임포트
from shared_modules import (
    get_config,
    get_llm_manager,
    get_vector_manager,
    get_or_create_conversation_session,
    create_message,
    get_recent_messages,
    insert_message_raw,
    get_session_context,
    create_success_response,
    create_error_response,
    get_current_timestamp,
    format_conversation_history,
    load_prompt_from_file,
    get_session
)

# Mental Health 특화 임포트
from mental_agent.config.persona_config import PERSONA_CONFIG, get_persona_by_phq9_score, get_persona_by_issue_type
from mental_agent.utils.mental_health_utils import (
    calculate_phq9_score, analyze_emotional_state, detect_crisis_indicators,
    generate_safety_plan, get_follow_up_questions, recommend_resources, PHQ9_QUESTIONS
)

# DB 관련 (기존 시스템과 호환)
try:
    from shared_modules.queries import save_or_update_phq9_result, get_latest_phq9_by_user
except ImportError:
    logger.warning("PHQ-9 관련 DB 함수를 찾을 수 없습니다. 기본 기능으로 작동합니다.")
    def save_or_update_phq9_result(*args, **kwargs):
        pass
    def get_latest_phq9_by_user(*args, **kwargs):
        return None

logger = logging.getLogger(__name__)

class ConversationStage(Enum):
    """대화 단계 정의"""
    INITIAL = "initial"                    # 초기 접촉
    RAPPORT_BUILDING = "rapport_building"  # 라포 형성
    ASSESSMENT = "assessment"              # 정신건강 평가
    PHQ9_SURVEY = "phq9_survey"           # PHQ-9 설문
    CRISIS_EVALUATION = "crisis_evaluation"  # 위기 평가
    COUNSELING = "counseling"              # 상담
    SAFETY_PLANNING = "safety_planning"    # 안전 계획
    RESOURCE_PROVISION = "resource_provision"  # 자원 제공
    FOLLOW_UP = "follow_up"               # 후속 관리
    COMPLETED = "completed"                # 완료

class ConversationState:
    """대화 상태 관리 클래스"""
    
    def __init__(self, conversation_id: int, user_id: int):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.stage = ConversationStage.INITIAL
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.phq9_survey_requested = False 
        
        # 수집된 정보
        self.collected_info = {
            "emotional_state": None,         # 현재 감정 상태
            "primary_concern": None,         # 주요 관심사/문제
            "symptoms": [],                  # 증상들
            "duration": None,                # 지속 기간
            "triggers": [],                  # 유발 요인들
            "coping_methods": [],            # 기존 대처 방법
            "support_system": None,          # 지지 체계
            "previous_treatment": None,      # 이전 치료 경험
            "risk_factors": [],             # 위험 요인들
            "protective_factors": [],        # 보호 요인들
            "crisis_history": None,         # 위기 이력
            "additional_context": {}
        }
        
        # 평가 결과
        self.assessment_results = {
            "emotional_analysis": {},
            "crisis_indicators": {},
            "phq9_results": None,
            "risk_level": "low",
            "suicide_risk": False,
            "immediate_intervention_needed": False,
            "recommended_persona": "common"
        }
        
        # PHQ-9 설문 상태
        self.phq9_state = {
            "is_active": False,
            "current_question": 0,
            "responses": [],
            "completed": False,
            "score": None,
            "interpretation": None
        }
        
        # 상담 및 계획
        self.counseling_sessions = []
        self.safety_plans = []
        self.resource_recommendations = []
        
        # 최종 결과
        self.final_assessment = None
        self.treatment_plan = None
        
    def update_stage(self, new_stage: ConversationStage):
        """단계 업데이트"""
        self.stage = new_stage
        self.updated_at = datetime.now()
        
    def add_collected_info(self, key: str, value: Any):
        """수집된 정보 추가"""
        if key in self.collected_info:
            self.collected_info[key] = value
        else:
            self.collected_info["additional_context"][key] = value
        self.updated_at = datetime.now()
        
    def add_phq9_response(self, response: int):
        """PHQ-9 응답 추가"""
        if self.phq9_state["is_active"]:
            self.phq9_state["responses"].append(response)
            self.phq9_state["current_question"] += 1
            
            if len(self.phq9_state["responses"]) >= 9:
                self.phq9_state["completed"] = True
                self.phq9_state["is_active"] = False
                # 점수 계산
                result = calculate_phq9_score(self.phq9_state["responses"])
                total_score = result.get("total_score", 0)
                self.phq9_state["score"] = total_score
                self.phq9_state["interpretation"] = result
                self.assessment_results["phq9_results"] = result
                
                # PHQ-9 결과 저장
                try:
                    # PHQ-9 점수를 level로 변환 (0-4: 1, 5-9: 2, 10-14: 3, 15-19: 4, 20-27: 5)
                    level = 1
                    if total_score >= 20:
                        level = 5
                    elif total_score >= 15:
                        level = 4
                    elif total_score >= 10:
                        level = 3
                    elif total_score >= 5:
                        level = 2

                    save_or_update_phq9_result(
                        db=get_session(),
                        user_id=self.user_id,
                        score=total_score,
                        level=level  # 변환된 level 값 사용
                    )
                except Exception as e:
                    logger.error(f"PHQ-9 결과 저장 실패: {e}")
                
                # 자살 위험 업데이트
                if result.get("suicide_risk", False):
                    self.assessment_results["suicide_risk"] = True
                    self.assessment_results["immediate_intervention_needed"] = True
        
        self.updated_at = datetime.now()
    
    def start_phq9_survey(self):
        """PHQ-9 설문 시작"""
        self.phq9_state = {
            "is_active": True,
            "current_question": 0,
            "responses": [],
            "completed": False,
            "score": None,
            "interpretation": None
        }
        self.update_stage(ConversationStage.PHQ9_SURVEY)
        
    def get_completion_rate(self) -> float:
        """정보 수집 완료율"""
        total_fields = len(self.collected_info)
        completed_fields = len([v for v in self.collected_info.values() if v and v != []])
        return completed_fields / total_fields if total_fields > 0 else 0.0
    
    def cancel_phq9(self):
        """PHQ-9 설문 중단"""
        self.phq9_state["is_active"] = False
        self.phq9_state["current_question"] = 0
        self.phq9_state["responses"] = []
        self.phq9_state["completed"] = False
        self.phq9_state["score"] = None
        self.phq9_state["interpretation"] = None
        self.update_stage(ConversationStage.RAPPORT_BUILDING)


class MentalHealthAgentManager:
    """통합 정신건강 에이전트 관리자 - 멀티턴 대화 시스템"""
    
    def __init__(self):
        """정신건강 매니저 초기화"""
        self.config = get_config()
        self.llm_manager = get_llm_manager()
        self.vector_manager = get_vector_manager()
        
        # 전문 지식 벡터 스토어 설정
        self.knowledge_collection = 'mental-health-knowledge'
        
        # 정신건강 토픽 정의
        self.mental_health_topics = {
            "depression": "우울증 및 기분 장애",
            "anxiety": "불안 장애",
            "stress": "스트레스 관리",
            "trauma": "트라우마 및 PTSD",
            "addiction": "중독 문제",
            "family": "가족 및 관계 문제",
            "crisis": "위기 상황 및 자살 예방",
            "mindfulness": "마음챙김 및 명상",
            "therapy": "심리치료 및 상담",
            "medication": "정신과 약물 치료",
            "lifestyle": "생활습관 및 웰빙",
            "general": "일반 정신건강"
        }
        
        # 대화 상태 관리 (메모리 기반)
        self.conversation_states: Dict[int, ConversationState] = {}
        
        # 위기 상황 대응 프로토콜
        self.crisis_protocols = {
            "immediate": ["119 응급실", "1393 생명의전화", "1577-0199 정신건강위기상담"],
            "urgent": ["정신건강의학과 응급진료", "지역 정신건강센터"],
            "non_urgent": ["일반 상담센터", "온라인 상담"]
        }
        
        # 지식 기반 초기화
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """정신건강 전문 지식 벡터 스토어 초기화"""
        try:
            vectorstore = self.vector_manager.get_vectorstore(
                collection_name=self.knowledge_collection,
                create_if_not_exists=True
            )
            
            if not vectorstore:
                logger.warning("벡터 스토어 초기화 실패")
                return
            
            logger.info("✅ 정신건강 전문 지식 벡터 스토어 초기화 완료")
            
        except Exception as e:
            logger.error(f"전문 지식 벡터 스토어 초기화 실패: {e}")
    
    def get_or_create_conversation_state(self, conversation_id: int, user_id: int) -> ConversationState:
        """대화 상태 조회 또는 생성"""
        if conversation_id not in self.conversation_states:
            self.conversation_states[conversation_id] = ConversationState(conversation_id, user_id)
        return self.conversation_states[conversation_id]
    
    def classify_mental_health_topic(self, user_input: str, context: str = "") -> List[str]:
        """정신건강 토픽 분류"""
        try:
            # 감정 상태 분석으로 토픽 추론
            emotional_analysis = analyze_emotional_state(user_input)
            primary_emotion = emotional_analysis.get("primary_emotion", "neutral")
            
            # 위기 지표 감지
            crisis_indicators = detect_crisis_indicators(user_input)
            
            topics = []
            
            # 위기 상황 우선 처리
            if crisis_indicators.get("immediate_intervention", False):
                topics.append("crisis")
            
            # 감정 상태 기반 토픽 매핑
            emotion_topic_mapping = {
                "sad": ["depression"],
                "anxious": ["anxiety"],
                "angry": ["stress"],
                "hopeless": ["depression", "crisis"],
                "suicidal": ["crisis"]
            }
            
            if primary_emotion in emotion_topic_mapping:
                topics.extend(emotion_topic_mapping[primary_emotion])
            
            # 키워드 기반 보완
            keyword_mapping = {
                "우울": "depression",
                "불안": "anxiety", 
                "스트레스": "stress",
                "트라우마": "trauma",
                "중독": "addiction",
                "가족": "family",
                "명상": "mindfulness",
                "치료": "therapy"
            }
            
            for keyword, topic in keyword_mapping.items():
                if keyword in user_input and topic not in topics:
                    topics.append(topic)
            
            return topics if topics else ["general"]
            
        except Exception as e:
            logger.error(f"토픽 분류 실패: {e}")
            return ["general"]
    
    def analyze_user_state(self, user_input: str, state: ConversationState) -> Dict[str, Any]:
        """사용자 상태 종합 분석 - 수정된 버전"""
        try:
            # 감정 상태 분석
            emotional_analysis = analyze_emotional_state(user_input)
            
            # 위기 지표 감지
            crisis_indicators = detect_crisis_indicators(user_input)
            
            # 분석 결과가 딕셔너리인지 확인
            if not isinstance(emotional_analysis, dict):
                logger.warning(f"감정 분석 결과가 딕셔너리가 아님: {type(emotional_analysis)}")
                emotional_analysis = {
                    "primary_emotion": "neutral",
                    "detected_emotions": {},
                    "risk_level": "low",
                    "requires_immediate_attention": False,
                    "emotional_intensity": 0
                }
            
            if not isinstance(crisis_indicators, dict):
                logger.warning(f"위기 지표 결과가 딕셔너리가 아님: {type(crisis_indicators)}")
                crisis_indicators = {
                    "crisis_level": "none",
                    "detected_indicators": {},
                    "immediate_intervention": False,
                    "total_indicators": 0,
                    "emergency_resources_needed": False,
                    "recommended_actions": []
                }
            
            # 분석 결과 저장
            state.assessment_results["emotional_analysis"] = emotional_analysis
            state.assessment_results["crisis_indicators"] = crisis_indicators
            
            # 위험 수준 결정
            risk_level = "low"
            if crisis_indicators.get("immediate_intervention", False):
                risk_level = "critical"
                state.assessment_results["immediate_intervention_needed"] = True
            elif crisis_indicators.get("crisis_level") == "moderate":
                risk_level = "high"
            elif emotional_analysis.get("risk_level") == "medium":
                risk_level = "medium"
            
            state.assessment_results["risk_level"] = risk_level
            
            # 자살 위험 평가
            detected_emotions = emotional_analysis.get("detected_emotions", {})
            if isinstance(detected_emotions, dict) and "suicidal" in detected_emotions:
                state.assessment_results["suicide_risk"] = True
                state.assessment_results["immediate_intervention_needed"] = True
            elif emotional_analysis.get("primary_emotion") == "suicidal":
                state.assessment_results["suicide_risk"] = True
                state.assessment_results["immediate_intervention_needed"] = True
            
            # 적절한 페르소나 추천
            if state.assessment_results.get("suicide_risk", False):
                recommended_persona = "crisis_counselor"
            elif risk_level == "critical":
                recommended_persona = "crisis_counselor"
            elif "anxiety" in str(detected_emotions):
                recommended_persona = "counselor"
            elif emotional_analysis.get("primary_emotion") in ["sad", "anxious"]:
                recommended_persona = "counselor"
            else:
                recommended_persona = "common"
            
            state.assessment_results["recommended_persona"] = recommended_persona
            
            return {
                "emotional_analysis": emotional_analysis,
                "crisis_indicators": crisis_indicators,
                "risk_level": risk_level,
                "immediate_intervention_needed": state.assessment_results.get("immediate_intervention_needed", False),
                "recommended_persona": recommended_persona,
                "next_stage_recommendation": self._recommend_next_stage(state)
            }
            
        except Exception as e:
            logger.error(f"사용자 상태 분석 실패: {e}")
            # 안전한 기본값 반환
            return {
                "emotional_analysis": {
                    "primary_emotion": "neutral",
                    "detected_emotions": {},
                    "risk_level": "low",
                    "requires_immediate_attention": False,
                    "emotional_intensity": 0
                },
                "crisis_indicators": {
                    "crisis_level": "none",
                    "detected_indicators": {},
                    "immediate_intervention": False,
                    "total_indicators": 0,
                    "emergency_resources_needed": False,
                    "recommended_actions": []
                },
                "risk_level": "low",
                "immediate_intervention_needed": False,
                "recommended_persona": "common",
                "next_stage_recommendation": "rapport_building"
            }
    
    def _recommend_next_stage(self, state: ConversationState) -> str:
        """다음 단계 추천"""
        current_stage = state.stage
        assessment = state.assessment_results
        
        if assessment.get("immediate_intervention_needed", False):
            return "crisis_evaluation"
        elif current_stage == ConversationStage.INITIAL:
            return "rapport_building"
        elif current_stage == ConversationStage.RAPPORT_BUILDING:
            return "assessment"
        elif current_stage == ConversationStage.ASSESSMENT:
            if assessment.get("risk_level") in ["high", "critical"]:
                return "crisis_evaluation"
            else:
                return "phq9_survey"
        elif current_stage == ConversationStage.PHQ9_SURVEY:
            if state.phq9_state["completed"]:
                phq9_score = state.phq9_state.get("score", 0)
                if phq9_score >= 15 or state.assessment_results.get("suicide_risk", False):
                    return "crisis_evaluation"
                else:
                    return "counseling"
            else:
                return "phq9_survey"
        elif current_stage == ConversationStage.CRISIS_EVALUATION:
            return "safety_planning"
        elif current_stage == ConversationStage.SAFETY_PLANNING:
            return "resource_provision"
        else:
            return "counseling"
    
    def start_phq9_survey(self, conversation_id: int, user_id: int) -> Dict[str, Any]:
        """PHQ-9 설문 시작 (ConversationState 내부 메서드 호출)"""
        from mental_agent.utils.mental_health_utils import PHQ9_QUESTIONS

        state = self.get_or_create_conversation_state(conversation_id, user_id)

        if state.phq9_state["is_active"]:
            return {
                "message": "이미 PHQ-9 설문이 진행 중입니다.",
                "phq9_active": True,
                "current_index": state.phq9_state.get("current_question", 0)
            }

        # 🔽 ConversationState의 메서드 호출
        state.start_phq9_survey()

        first_question = PHQ9_QUESTIONS[0]

        return {
            "message": {
                "text": first_question["text"],
                "options": first_question["options"],
                "index": 1,
                "total": len(PHQ9_QUESTIONS)
            },
            "phq9_active": True,
            "phq9_completed": False,
            "current_index": 0
        }

    
    def handle_phq9_survey(self, user_input: str, state: ConversationState) -> str:
        """PHQ-9 설문 처리"""
        try:
            if not state.phq9_state["is_active"]:
                # 설문 시작
                state.start_phq9_survey()
                return f"""📋 **PHQ-9 우울증 자가진단 설문**

총 9개 문항으로 구성되어 있습니다. 각 문항에 대해 지난 2주간의 경험을 바탕으로 답변해 주세요.

**응답 방법:**
- 0: 전혀 그렇지 않다
- 1: 며칠 정도 그렇다  
- 2: 일주일 이상 그렇다
- 3: 거의 매일 그렇다

**문항 1/9**: {PHQ9_QUESTIONS[0]}

0, 1, 2, 3 중 하나의 숫자로 답변해 주세요."""

            else:
                # 응답 처리
                try:
                    response = int(user_input.strip())
                    if not (0 <= response <= 3):
                        return "0, 1, 2, 3 중 하나의 숫자로 답변해 주세요."
                    
                    state.add_phq9_response(response)
                    
                    if state.phq9_state["completed"]:
                        # 설문 완료
                        result = state.phq9_state["interpretation"]
                        score = result.get("total_score", 0)
                        severity = result.get("severity", "")
                        recommendation = result.get("recommendation", "")
                        
                        # DB 저장 시도
                        try:
                            with get_session_context() as db:
                                # PHQ-9 점수를 level로 변환 (0-4: 1, 5-9: 2, 10-14: 3, 15-19: 4, 20-27: 5)
                                level = 1
                                if score >= 20:
                                    level = 5
                                elif score >= 15:
                                    level = 4
                                elif score >= 10:
                                    level = 3
                                elif score >= 5:
                                    level = 2

                                save_or_update_phq9_result(
                                    db, state.user_id, score, level
                                )
                        except Exception as e:
                            logger.warning(f"PHQ-9 결과 DB 저장 실패: {e}")
                        
                        response_text = f"""✅ **PHQ-9 설문 완료**

**총점: {score}점**
**평가 결과: {severity}**

{result.get('interpretation', '')}

**권장사항**: {recommendation}
"""
                        
                        # 위기 상황 체크
                        if result.get("suicide_risk", False):
                            response_text += f"""

⚠️ **중요 안내**: 자해나 자살에 대한 생각이 감지되었습니다. 
즉시 전문가의 도움을 받으시기 바랍니다.

**응급 연락처**:
- 생명의전화: 1393
- 정신건강위기상담: 1577-0199
- 응급실: 119"""
                            
                            state.update_stage(ConversationStage.CRISIS_EVALUATION)
                        else:
                            state.update_stage(ConversationStage.COUNSELING)
                        
                        return response_text
                    
                    else:
                        # 다음 문항
                        current_q = state.phq9_state["current_question"]
                        return f"""**문항 {current_q + 1}/9**: {PHQ9_QUESTIONS[current_q]}

0, 1, 2, 3 중 하나의 숫자로 답변해 주세요."""
                
                except ValueError:
                    return "숫자로 답변해 주세요. (0, 1, 2, 3 중 선택)"
                    
        except Exception as e:
            logger.error(f"PHQ-9 설문 처리 실패: {e}")
            return "설문 처리 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def handle_crisis_situation(self, user_input: str, state: ConversationState) -> str:
        """위기 상황 처리"""
        try:
            crisis_info = state.assessment_results.get("crisis_indicators", {})
            safety_plan = generate_safety_plan(crisis_info)
            
            crisis_level = crisis_info.get("crisis_level", "none")
            
            if crisis_level == "severe" or state.assessment_results.get("suicide_risk", False):
                response = """🚨 **응급 상황 안내**

현재 상황이 심각합니다. 즉시 아래 연락처로 도움을 요청하세요.

**응급 연락처**:
- 🚑 응급실: 119
- 📞 생명의전화: 1393 (24시간)
- 📞 정신건강위기상담: 1577-0199

**즉시 해야 할 것들**:
"""
                for action in safety_plan.get("immediate_actions", []):
                    response += f"• {action}\n"
                
                response += f"""
지금 안전한 곳에 계신가요? 누군가와 함께 계신가요?
혼자 계시다면 신뢰할 수 있는 누군가에게 즉시 연락하세요."""
                
            else:
                response = f"""💛 **안전 계획**

현재 상황을 함께 정리해보겠습니다.

**대처 방법**:
"""
                for strategy in safety_plan.get("coping_strategies", []):
                    response += f"• {strategy}\n"
                
                response += f"""
**도움받을 수 있는 곳**:
"""
                for resource in safety_plan.get("professional_resources", []):
                    response += f"• {resource}\n"
            
            state.safety_plans.append({
                "plan": safety_plan,
                "created_at": datetime.now()
            })
            
            state.update_stage(ConversationStage.SAFETY_PLANNING)
            return response
            
        except Exception as e:
            logger.error(f"위기 상황 처리 실패: {e}")
            return "위기 상황 처리 중 오류가 발생했습니다. 즉시 119나 1393으로 연락하세요."
    
    def process_user_query(
        self, 
        user_input: str, 
        user_id: int, 
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """사용자 쿼리 처리 - 멀티턴 대화 플로우"""
        
        try:
            logger.info(f"멀티턴 정신건강 쿼리 처리 시작: {user_input[:50]}...")
            
            # 대화 세션 처리
            session_info = get_or_create_conversation_session(user_id, conversation_id)
            conversation_id = session_info["conversation_id"]
            state = self.get_or_create_conversation_state(conversation_id, user_id)

            if user_input.strip() in ["그만", "그만할래요", "그만하고 싶어요", "설문 종료", "멈춤"]:
                if state.phq9_state["is_active"]:
                    state.cancel_phq9()
                    return {
                        "response": "PHQ-9 설문이 중단되었습니다. 원하실 때 언제든 다시 시작하실 수 있어요.",
                        "end_survey": True
                    }


            # 2. 사용자 메시지 저장
            with get_session_context() as db:
                create_message(db, conversation_id, "user", "mental_health", user_input)

            # 3. 상태 분석
            analysis_result = self.analyze_user_state(user_input, state)

            # 4. 설문 강제 키워드 진입 처리 (모든 단계에서 동작)
            phq9_keywords = [
                "PHQ", "우울증", "우울증 테스트", "우울", "설문", "자가진단", 
                "진단", "검사", "테스트",
                "받고 싶어", "설문 다시", "다시 테스트", "테스트 하고 싶어요"
            ]

            # 1. 사용자가 설문 키워드를 말한 경우: 안내 메시지 먼저
            if any(k in user_input for k in phq9_keywords) and not state.phq9_state["is_active"]:
                state.phq9_survey_requested = True
                return {
                    "response": (
                        "PHQ-9 우울증 자가진단 설문을 시작하시겠습니까?\n\n"
                        "이 설문은 지난 2주간의 우울 증상을 평가하는 9개 문항으로 구성되어 있습니다.\n\n"
                        "설문을 진행하려면 '네' 또는 '시작'이라고 말씀해 주세요.\n"
                        "그만두고 싶으시면 '아니요' 또는 '취소'라고 말씀해 주세요."
                    )
                }

            # 2. 사용자가 설문 시작을 수락한 경우
            if user_input.strip() in ["네", "시작"] and state.phq9_survey_requested and not state.phq9_state["is_active"]:
                state.phq9_survey_requested = False
                return self.start_phq9_survey(conversation_id, user_id)

            # 3. 사용자가 설문을 거절한 경우
            if user_input.strip() in ["아니요", "취소"] and state.phq9_survey_requested:
                state.phq9_survey_requested = False
                return {
                    "response": "알겠습니다. 언제든 원하시면 다시 하실 수 있어요..",
                    "phq9_cancelled": True
                }

            # 6. 위기 상황 우선 처리
            if analysis_result.get("immediate_intervention_needed", False):
                response_content = self.handle_crisis_situation(user_input, state)
            elif state.stage == ConversationStage.INITIAL:
                # 초기 접촉
                if any(word in user_input for word in ["PHQ","우울증","우울증 테스트", "설문", "자가진단", "진단", "검사", "테스트"]):
                    response_content = (
                        "PHQ-9 우울증 자가진단 설문을 시작하시겠습니까?\n\n"
                        "이 설문은 지난 2주간의 우울 증상을 평가하는 9개 문항으로 구성되어 있습니다.\n\n"
                        "설문을 진행하려면 '네' 또는 '시작'이라고 말씀해 주세요.\n"
                        "그만두고 싶으시면 '아니요' 또는 '취소'라고 말씀해 주세요."
                    )
                else:
                    # 바로 상담 응답 생성
                    persona_key = analysis_result.get("recommended_persona", "common")
                    persona = PERSONA_CONFIG.get(persona_key, PERSONA_CONFIG["common"])
                    
                    # 적절한 페르소나로 응답 생성
                    counseling_prompt = f""""당신은 **따뜻하고 전문적인 정신건강 상담사**입니다.

사용자가 "{user_input}"라고 말했습니다.

다음과 같은 구조로 응답해주세요:

1. **감정 공감**: 먼저 사용자의 감정에 공감하는 따뜻한 말을 건네주세요. 너무 정형적이지 않고 자연스럽게 표현해주세요.

2. **실질적 조언 제시**: 그 다음, 도움이 될 만한 조언을 **목록 형식 또는 단락 형식 중 적절하게** 제안해주세요.  
   항목이 많을 경우에는 숫자나 점을 사용하거나, **연결어**(예: 그리고, 또한, 혹은 한 가지 더) 등으로 자연스럽게 이어가 주세요.

3. **따뜻한 마무리**: 마지막에는 진심 어린 격려의 말을 건네주세요.  
   사용자가 **스스로를 믿고 위로받을 수 있도록** 말해주세요.

📝 **스타일 지침**:
- 진정성 있고 인간적인 톤으로 작성해주세요.
- 각 아이디어는 줄바꿈으로 구분하고 **완전한 문장**으로 표현해주세요.
- 강조할 내용은 **마크다운 문법**(`**굵게**`, `- 리스트`)을 적극 활용해주세요."""

                    try:
                        from langchain.schema import SystemMessage, HumanMessage
                        from langchain_openai import ChatOpenAI
                        
                        messages = [
                            SystemMessage(content=counseling_prompt),
                            HumanMessage(content=user_input)
                        ]
                        
                        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
                        raw_response = llm.invoke(messages)
                        response_content = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
                        
                    except Exception as e:
                        logger.error(f"상담 응답 생성 실패: {e}")
                        response_content = "안녕하세요. 정신건강 상담사입니다. 어떤 어려움이든 함께 나누고 해결해 나갈 수 있습니다. 편안하게 이야기해 주세요."

                state.update_stage(ConversationStage.COUNSELING)


                
            else:
                # 일반 상담 처리
                persona_key = analysis_result.get("recommended_persona", "common")
                persona = PERSONA_CONFIG.get(persona_key, PERSONA_CONFIG["common"])
                
                # 적절한 페르소나로 응답 생성
                counseling_prompt = f"""당신은 **따뜻하고 전문적인 정신건강 상담사**입니다.

사용자가 "**{user_input}**"라고 말했습니다.

다음과 같은 구조로 응답해주세요:

1. **감정 공감**  
   먼저 사용자의 감정에 공감하는 **따뜻한 말**을 건네주세요.  
   너무 정형적이지 않고 **자연스럽게 표현**해주세요.

2. **실질적인 조언 제안**  
   그 다음, 해결책이나 도움이 될 만한 조언을 **목록 형식 또는 단락 형식 중 적절하게** 제안해주세요.  
   항목이 많을 경우에는 숫자(1. 2. 3.)나 점(-)을 사용하거나,  
   **연결어**(예: 그리고, 또한, 혹은 한 가지 더)를 활용해 자연스럽게 이어주세요.

3. **진심 어린 격려로 마무리**  
   마지막에는 따뜻하고 **진심 어린 격려의 말**로 마무리해주세요.  
   사용자가 **스스로를 믿고 위로받을 수 있도록** 도와주세요.

📝 **스타일 가이드**  
- 응답은 **진정성 있고 인간적인 톤**으로 작성합니다.  
- 각 아이디어는 **줄바꿈으로 구분**하고 **완전한 문장**으로 표현합니다.  
- 강조할 부분은 **마크다운 문법**(`**굵게**`, `- 리스트`)을 사용해 주세요.


                """


                try:
                    # SystemMessage, HumanMessage를 사용한 메시지 구성
                    from langchain.schema import SystemMessage, HumanMessage
                    from langchain_openai import ChatOpenAI
                    
                    messages = [
                        SystemMessage(content=counseling_prompt),
                        HumanMessage(content=user_input)
                    ]
                    
                    # ChatOpenAI 인스턴스를 직접 사용
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)
                    raw_response = llm.invoke(messages)
                    response_content = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
                    
                    # # 후속 질문 추가
                    # follow_up_questions = get_follow_up_questions(analysis_result.get("emotional_analysis", {}))
                    # if follow_up_questions and analysis_result.get("risk_level") != "critical":
                    #     response_content += f"\n\n더 도움이 되도록 몇 가지 질문을 드려도 될까요?\n"
                    #     response_content += f"• {follow_up_questions['questions'][0]}"
                    
                except Exception as e:
                    logger.error(f"상담 응답 생성 실패: {e}")
                    response_content = "안녕하세요. 정신건강 상담사입니다. 어떤 어려움이든 함께 나누고 해결해 나갈 수 있습니다. 편안하게 이야기해 주세요."
                state.update_stage(ConversationStage.COUNSELING)
            
            # 응답 메시지 저장
            insert_message_raw(
                conversation_id=conversation_id,
                sender_type="agent",
                agent_type="mental_health",
                content=response_content
            )
            
            # 표준 응답 형식으로 반환
            return create_success_response({
                "conversation_id": conversation_id,
                "answer": response_content,
                "agent_type": "mental_health",
                "stage": state.stage.value,
                "completion_rate": state.get_completion_rate(),
                "risk_level": state.assessment_results.get("risk_level", "low"),
                "suicide_risk": state.assessment_results.get("suicide_risk", False),
                "phq9_active": state.phq9_state["is_active"],
                "phq9_completed": state.phq9_state["completed"],
                "phq9_score": state.phq9_state.get("score"),
                "immediate_intervention_needed": state.assessment_results.get("immediate_intervention_needed", False),
                "timestamp": get_current_timestamp()
            })
            
        except Exception as e:
            logger.error(f"멀티턴 정신건강 쿼리 처리 실패: {e}")
            return create_error_response(
                error_message=f"정신건강 상담 처리 중 오류가 발생했습니다: {str(e)}",
                error_code="MULTITURN_MENTAL_HEALTH_ERROR"
            )
    
    def get_agent_status(self) -> Dict[str, Any]:
        """정신건강 에이전트 상태 반환"""
        return {
            "agent_type": "mental_health",
            "version": "3.0.0", 
            "conversation_system": "multiturn",
            "stages": [stage.value for stage in ConversationStage],
            "active_conversations": len(self.conversation_states),
            "conversation_stages": {
                conv_id: state.stage.value 
                for conv_id, state in self.conversation_states.items()
            },
            "crisis_conversations": len([
                state for state in self.conversation_states.values() 
                if state.assessment_results.get("immediate_intervention_needed", False)
            ]),
            "phq9_active_surveys": len([
                state for state in self.conversation_states.values()
                if state.phq9_state["is_active"]
            ]),
            "llm_status": self.llm_manager.get_status(),
            "vector_store_status": self.vector_manager.get_status(),
            "supported_features": [
                "PHQ-9 설문",
                "위기 상황 감지",
                "감정 상태 분석", 
                "안전 계획 수립",
                "전문가 페르소나",
                "멀티턴 상담"
            ]
        }
    # mental_health_manager.py에 추가할 메서드들

    def get_phq9_status(self, conversation_id: int) -> Dict[str, Any]:
        """PHQ-9 설문 상태 조회"""
        try:
            if conversation_id not in self.conversation_states:
                return {
                    "success": False,
                    "is_active": False,
                    "current_question": None,
                    "error": "대화를 찾을 수 없습니다"
                }
            
            state = self.conversation_states[conversation_id]
            
            if state.phq9_state["is_active"]:
                current_q_index = len(state.phq9_state["responses"])
                if current_q_index < 9:
                    return {
                        "success": True,
                        "is_active": True,
                        "current_question": {
                            "index": current_q_index,
                            "text": PHQ9_QUESTIONS[current_q_index],
                            "progress": f"{current_q_index + 1}/9",
                            "options": [
                                {"value": 0, "label": "전혀 그렇지 않다"},
                                {"value": 1, "label": "며칠 정도 그렇다"},
                                {"value": 2, "label": "일주일 이상 그렇다"},
                                {"value": 3, "label": "거의 매일 그렇다"}
                            ]
                        },
                        "completed": False
                    }
            
            return {
                "success": True,
                "is_active": False,
                "current_question": None,
                "completed": state.phq9_state["completed"],
                "score": state.phq9_state.get("score")
            }
            
        except Exception as e:
            logger.error(f"PHQ-9 상태 조회 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def submit_phq9_button_response(self, conversation_id: int, user_id: int, response_value: int) -> Dict[str, Any]:
        """PHQ-9 버튼 응답 처리 - 프론트엔드와 호환되도록 수정"""
        try:
            if conversation_id not in self.conversation_states:
                return {
                    "success": False,
                    "error": "대화를 찾을 수 없습니다"
                }
            
            state = self.conversation_states[conversation_id]
            
            if not state.phq9_state["is_active"]:
                return {
                    "success": False,
                    "error": "PHQ-9 설문이 활성화되지 않았습니다"
                }
            
            if response_value not in [0, 1, 2, 3]:
                return {
                    "success": False,
                    "error": "응답값은 0-3 사이여야 합니다"
                }
            
            # 응답 저장
            state.add_phq9_response(response_value)
            
            # 사용자 응답을 메시지로 저장
            response_labels = ["전혀 그렇지 않다", "며칠 정도 그렇다", "일주일 이상 그렇다", "거의 매일 그렇다"]
            user_response_text = f"[PHQ-9 응답] {response_value}: {response_labels[response_value]}"
            
            with get_session_context() as db:
                create_message(db, conversation_id, "user", "mental_health", user_response_text)

            current_question_index = len(state.phq9_state["responses"])
            
            # 설문 완료 체크
            if state.phq9_state["completed"]:
                # 완료 메시지 생성
                result = state.phq9_state["interpretation"]
                score = result.get("total_score", 0)
                severity = result.get("severity", "")
                recommendation = result.get("recommendation", "")
                
                completion_message = f"""✅ **PHQ-9 설문 완료**

    **총점: {score}점**
    **평가 결과: {severity}**

    {result.get('interpretation', '')}

    **권장사항**: {recommendation}"""
                
                # 위기 상황 체크
                if result.get("suicide_risk", False):
                    completion_message += f"""

    ⚠️ **중요 안내**: 자해나 자살에 대한 생각이 감지되었습니다. 
    즉시 전문가의 도움을 받으시기 바랍니다.

    **응급 연락처**:
    - 생명의전화: 1393
    - 정신건강위기상담: 1577-0199
    - 응급실: 119"""
                    
                    state.update_stage(ConversationStage.CRISIS_EVALUATION)
                else:
                    state.update_stage(ConversationStage.COUNSELING)
                
                # 완료 메시지 저장
                with get_session_context() as db:
                    create_message(db, conversation_id, "agent", "mental_health", completion_message)
                
                return {
                    "success": True,
                    "completed": True,
                    "response": completion_message,  # 프론트엔드에서 기대하는 키
                    "result": {
                        "score": score,
                        "severity": severity,
                        "recommendation": recommendation,
                        "suicide_risk": result.get("suicide_risk", False),
                        "interpretation": result.get("interpretation", "")
                    },
                    "next_stage": state.stage.value,
                }
            
            else:
                # 다음 질문 생성 - 프론트엔드 형식에 맞춤
                if current_question_index < 9:
                    next_question_data = {
                        "text": PHQ9_QUESTIONS[current_question_index],
                        "progress": f"{current_question_index + 1}/9",
                        "question_id": current_question_index + 1,
                        "isDisabled": False
                    }
                    
                    # 프론트엔드가 기대하는 PHQ9_BUTTON 형식으로 메시지 생성
                    agent_message = f"다음 질문입니다.\n\nPHQ9_BUTTON:{json.dumps(next_question_data)}"
                    
                    # 메시지 저장
                    with get_session_context() as db:
                        create_message(db, conversation_id, "agent", "mental_health", agent_message)
                    
                    return {
                        "success": True,
                        "completed": False,
                        "response": agent_message,  # 프론트엔드에서 기대하는 키
                        "next_question": next_question_data,
                        "log_message": user_response_text

                    }
            
            return {
                "success": False,
                "error": "예상치 못한 오류가 발생했습니다"
            }
            
        except Exception as e:
            logger.error(f"PHQ-9 버튼 응답 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def start_phq9_survey(self, conversation_id: int, user_id: int) -> Dict[str, Any]:
        """PHQ-9 설문 시작 - 프론트엔드와 호환되도록 수정"""
        try:
            if conversation_id not in self.conversation_states:
                return {
                    "success": False,
                    "error": "대화를 찾을 수 없습니다"
                }
            
            state = self.conversation_states[conversation_id]
            
            if state.phq9_state["is_active"]:
                return {
                    "success": False,
                    "error": "이미 PHQ-9 설문이 진행 중입니다."
                }
            
            # PHQ-9 시작
            state.start_phq9_survey()
            
            # 시작 메시지와 첫 번째 질문을 PHQ9_BUTTON 형식으로 생성
            first_question_data = {
                "text": PHQ9_QUESTIONS[0],
                "progress": "1/9",
                "question_id": 1,
                "isDisabled": False
            }
            
            start_message = f"""📋 **PHQ-9 우울증 자가진단 설문**

    총 9개 문항으로 구성되어 있습니다. 각 문항에 대해 지난 2주간의 경험을 바탕으로 버튼을 클릭하여 답변해 주세요.

    PHQ9_BUTTON:{json.dumps(first_question_data)}"""
            
            # 시작 메시지 저장
            with get_session_context() as db:
                create_message(db, conversation_id, "agent", "mental_health", start_message)
            
            return {
                "success": True,
                "response": start_message,  # 프론트엔드에서 기대하는 키
                "first_question": first_question_data
            }
            
        except Exception as e:
            logger.error(f"PHQ-9 시작 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }