"""
통합 고객 서비스 에이전트 매니저 - 멀티턴 대화 시스템 (기존 구조 기반 수정)
마케팅 에이전트의 구조를 참고하여 리팩토링
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import json
from datetime import datetime

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
    PromptTemplate,
    get_templates_by_type
)

from customer_service_agent.config.persona_config import PERSONA_CONFIG, get_persona_by_topic
from customer_service_agent.config.prompts_config import PROMPT_META
from langchain.schema import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from shared_modules.queries import get_user_persona_info

logger = logging.getLogger(__name__)

class ConversationStage(Enum):
    """대화 단계 정의"""
    INITIAL = "initial"                    # 초기 접촉
    PROBLEM_IDENTIFICATION = "problem_identification"  # 문제 파악
    INFORMATION_GATHERING = "info_gathering"  # 정보 수집
    ANALYSIS = "analysis"                  # 분석
    SOLUTION_PROPOSAL = "solution_proposal"  # 해결책 제안
    FEEDBACK = "feedback"                  # 피드백 수집
    REFINEMENT = "refinement"              # 수정
    FINAL_RESULT = "final_result"          # 최종 결과
    COMPLETED = "completed"                # 완료

class ConversationState:
    """대화 상태 관리 클래스"""
    
    def __init__(self, conversation_id: int, user_id: int):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.stage = ConversationStage.INITIAL
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # 🔥 수정: 간소화된 정보 수집
        self.collected_info = {
            "business_type": None,           # 사업 유형
            "customer_issue": None,          # 고객 문제/불만
            "customer_segment": None,        # 고객 세그먼트
            "current_situation": None,       # 현재 상황
            "desired_outcome": None,         # 원하는 결과
            "urgency_level": None,           # 긴급도
            "available_resources": None,     # 가용 자원
            "previous_attempts": None,       # 이전 시도
            "customer_data": None,          # 고객 데이터
            "communication_channel": None,   # 소통 채널
            "timeline": None,               # 해결 기한
            "budget": None,                 # 예산
            "additional_context": {}
        }
        
        # 분석 결과
        self.analysis_results = {
            "primary_topics": [],
            "intent_analysis": {},
            "customer_sentiment": "neutral",
            "problem_category": None,
            "recommendations": []
        }
        
        # 해결책 및 제안
        self.solutions = []
        self.feedback_history = []
        self.refinements = []
        
        # 최종 결과
        self.final_solution = None
        self.action_plan = None
        
        # 단계별 프롬프트 기록
        self.stage_prompts = {}
        
    def update_stage(self, new_stage: ConversationStage):
        """단계 업데이트"""
        self.stage = new_stage
        self.updated_at = datetime.now()
        
    def add_collected_info(self, key: str, value: Any):
        """수집된 정보 추가"""
        self.collected_info[key] = value
        self.updated_at = datetime.now()
        
    def add_feedback(self, feedback: Dict[str, Any]):
        """피드백 추가"""
        feedback["timestamp"] = datetime.now()
        self.feedback_history.append(feedback)
        self.updated_at = datetime.now()
        
    def is_information_complete(self) -> bool:
        """정보 수집 완료 여부 확인 (완화된 조건)"""
        # 🔥 수정: 필수 필드 2개 + 총 3개 이상
        essential_fields = ["business_type", "desired_outcome"]
        has_essentials = all(self.collected_info.get(field) for field in essential_fields)
        filled_count = len([v for v in self.collected_info.values() if v])
        return has_essentials and filled_count >= 3
        
    def get_completion_rate(self) -> float:
        """정보 수집 완료율"""
        total_fields = len(self.collected_info)
        completed_fields = len([v for v in self.collected_info.values() if v])
        return completed_fields / total_fields if total_fields > 0 else 0.0

class CustomerServiceAgentManager:
    """통합 고객 서비스 에이전트 관리자 - 멀티턴 대화 시스템"""
    
    def __init__(self):
        """고객 서비스 매니저 초기화"""
        self.config = get_config()
        self.llm_manager = get_llm_manager()
        self.vector_manager = get_vector_manager()
        
        # 프롬프트 디렉토리 설정
        self.prompts_dir = Path(__file__).parent.parent / 'prompts'
        
        # 전문 지식 벡터 스토어 설정
        self.knowledge_collection = 'customer-service-knowledge'
        
        # 고객 서비스 토픽 정의
        self.customer_topics = {
            "customer_service": "고객 응대 및 클레임 처리",
            "customer_retention": "재방문 유도 및 고객 유지",
            "customer_satisfaction": "고객 만족도 개선",
            "customer_feedback": "고객 피드백 분석",
            "customer_segmentation": "고객 타겟팅 및 세분화",
            "community_building": "커뮤니티 구축",
            "customer_data": "고객 데이터 활용",
            "privacy_compliance": "개인정보 보호",
            "customer_message": "고객 메시지 템플릿",
            "customer_etc": "기타 고객 관리"
        }
        
        # 대화 상태 관리 (메모리 기반)
        self.conversation_states: Dict[int, ConversationState] = {}
        
        # 🔥 수정: 간소화된 질문 템플릿 (우선순위 순)
        self.info_gathering_questions = {
            "business_type": "어떤 업종/사업을 운영하고 계신가요?",
            "desired_outcome": "어떤 결과를 원하시나요?",
            "customer_issue": "현재 어떤 고객 관련 문제나 이슈가 있으신가요?",
            "current_situation": "현재 상황을 자세히 설명해주실 수 있나요?",
            "customer_segment": "주요 고객층은 어떻게 되나요?",
            "urgency_level": "이 문제의 긴급도는 어느 정도인가요?",
            "available_resources": "현재 활용 가능한 자원(인력, 시스템 등)은 어떻게 되나요?",
            "previous_attempts": "이전에 시도해본 해결 방법이 있나요?",
            "customer_data": "고객 데이터나 피드백이 있다면 알려주세요",
            "communication_channel": "주로 어떤 채널로 고객과 소통하시나요?",
            "timeline": "언제까지 해결하고 싶으신가요?",
            "budget": "예산 범위가 있다면 알려주세요"
        }
        
        # 지식 기반 초기화
        self._initialize_knowledge_base()
    
    def call_llm_api(self, model: str, prompt: str) -> str:
        """LLM API 호출 함수"""
        try:
            messages = [
                SystemMessage(content="당신은 도움이 되는 AI 어시스턴트입니다."),
                HumanMessage(content=prompt)
            ]
            
            llm = ChatOpenAI(model_name=model, temperature=0)
            raw_response = llm.invoke(messages)
            response = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
            return response
            
        except Exception as e:
            logger.error(f"LLM API 호출 실패: {e}")
            return ""
    
    # 🔥 새로 추가: LLM 기반 정보 추출
    def extract_info_with_llm(self, user_input: str) -> Dict[str, str]:
        """LLM을 사용한 지능적 정보 추출"""
        try:
            extraction_prompt = f"""사용자의 답변에서 고객 서비스 관련 정보를 추출해주세요.

사용자 답변: "{user_input}"

다음 정보를 찾아서 JSON으로 반환해주세요:
- business_type: 사업 유형 (예: 온라인 쇼핑몰, 카페, 병원 등)
- customer_issue: 고객 문제 (예: 클레임, 환불요구, 불만 등)
- desired_outcome: 원하는 결과 (예: 재방문 유도, 만족도 향상 등)
- current_situation: 현재 상황 설명
- customer_segment: 고객층 (예: 20대 여성, 직장인 등)
- urgency_level: 긴급도 (높음/보통/낮음)

명확하지 않은 정보는 포함하지 마세요.

응답 예시:
{{"business_type": "온라인 쇼핑몰", "desired_outcome": "고객 만족도 향상"}}

응답:"""

            response = self.call_llm_api(model="gpt-4o-mini", prompt=extraction_prompt)
            
            # JSON 추출
            if "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                extracted = json.loads(json_str)
                logger.info(f"정보 추출 성공: {extracted}")
                return extracted
            
            return {}
            
        except Exception as e:
            logger.error(f"정보 추출 실패: {e}")
            return {}
    
    # 🔥 새로 추가: 실제 분석 수행
    def perform_comprehensive_analysis(self, state: ConversationState) -> str:
        """종합적인 고객 서비스 분석 수행"""
        try:
            collected_info = {k: v for k, v in state.collected_info.items() if v}
            
            analysis_prompt = f"""고객 서비스 전문 컨설턴트로서 다음 정보를 종합 분석하여 구체적인 해결책을 제시해주세요.

**수집된 정보:**
{json.dumps(collected_info, ensure_ascii=False, indent=2)}

**분석 요구사항:**
1. 문제 상황 진단 및 원인 분석
2. 고객 감정 상태 및 리스크 평가
3. 즉시 실행 가능한 해결 방안 (단계별)
4. 고객 재구매/만족도 향상 전략
5. 향후 예방 방안

**응답 형식:**
## 🔍 상황 분석
- 핵심 문제: 
- 고객 감정 상태: 
- 리스크 수준: 

## 💡 즉시 실행 방안
### 1단계: 초기 대응 (24시간 내)
1. 
2. 

### 2단계: 문제 해결 (48시간 내)
1. 
2. 

### 3단계: 관계 회복 (1주일 내)
1. 
2. 

## 🎯 재구매 유도 전략
- 
- 

## 🛡️ 향후 예방책
- 
- 

## 📋 고객 응대 메시지 예시
- 즉시 발송용: 
- 해결 완료 후:

구체적이고 실행 가능한 조언을 제공해주세요."""

            response = self.call_llm_api(model="gpt-4o", prompt=analysis_prompt)
            
            # 분석 결과를 상태에 저장
            state.analysis_results["comprehensive_analysis"] = response
            state.update_stage(ConversationStage.COMPLETED)
            
            return response
            
        except Exception as e:
            logger.error(f"종합 분석 수행 실패: {e}")
            return "분석 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def is_follow_up(self, user_input: str, last_message: str, model="gpt-4o-mini") -> bool:
        """이전 메시지와 연결되는 후속 질문인지 판단"""
        try:
            prompt = f"""아래 사용자 발화가 이전 메시지 "{last_message}"와 의미적으로 연결되는 후속 질문인지 판단해.
후속 질문이면 true, 아니면 false만 출력해.

사용자 발화: "{user_input}"""
            
            response = self.call_llm_api(model=model, prompt=prompt)
            return "true" in response.lower()
            
        except Exception as e:
            logger.error(f"is_follow_up 판단 실패: {e}")
            return False
    
    def _initialize_knowledge_base(self):
        """고객 서비스 전문 지식 벡터 스토어 초기화"""
        try:
            vectorstore = self.vector_manager.get_vectorstore(
                collection_name=self.knowledge_collection,
                create_if_not_exists=True
            )
            
            if not vectorstore:
                logger.warning("벡터 스토어 초기화 실패")
                return
            
            logger.info("✅ 고객 서비스 전문 지식 벡터 스토어 초기화 완료")
            
        except Exception as e:
            logger.error(f"전문 지식 벡터 스토어 초기화 실패: {e}")
    
    def get_or_create_conversation_state(self, conversation_id: int, user_id: int) -> ConversationState:
        """대화 상태 조회 또는 생성"""
        if conversation_id not in self.conversation_states:
            self.conversation_states[conversation_id] = ConversationState(conversation_id, user_id)
        return self.conversation_states[conversation_id]
    
    def classify_customer_topic_with_llm(self, user_input: str, context: str = "") -> List[str]:
        """LLM을 활용한 고객 서비스 토픽 분류"""
        try:
            topic_classification_prompt = f"""다음 사용자 질문을 분석하여 관련된 고객 서비스 토픽을 분류해주세요.

사용 가능한 고객 서비스 토픽:
{chr(10).join([f"- {key}: {value}" for key, value in self.customer_topics.items()])}

{f"대화 컨텍스트: {context}" if context else ""}

사용자 질문: "{user_input}"

위 질문과 가장 관련성이 높은 토픽을 최대 2개까지 선택하여 키워드만 쉼표로 구분하여 답변해주세요.
예시: customer_service, customer_retention

답변:"""

            messages = [
                SystemMessage(content="당신은 고객 서비스 전문가로서 사용자 질문을 정확한 고객 관리 토픽으로 분류합니다."),
                HumanMessage(content=topic_classification_prompt)
            ]
            
            llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
            raw_response = llm.invoke(messages)
            response = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
            
            if response:
                topics = [topic.strip() for topic in response.split(',')]
                valid_topics = [topic for topic in topics if topic in self.customer_topics]
                return valid_topics[:2] if valid_topics else ["customer_service"]
            
            return ["customer_service"]
            
        except Exception as e:
            logger.error(f"LLM 토픽 분류 실패: {e}")
            return ["customer_service", "customer_etc"]
    
    def handle_template_request(self, user_input: str, state: ConversationState) -> str:
        """고객 메시지 템플릿 요청 처리"""
        try:
            template_type = self.extract_template_type(user_input)
            logger.info(f"추출된 템플릿 타입: {template_type}")
            
            templates = get_templates_by_type(template_type)
            
            if template_type == "고객 맞춤 메시지" and templates:
                filtered_templates = self.filter_templates_by_query(templates, user_input)
            else:
                filtered_templates = templates
            
            if filtered_templates:
                answer_blocks = []
                for t in filtered_templates:
                    if t.get("content_type") == "html":
                        preview_url = f"http://localhost:8001/preview/{t['template_id']}"
                        answer_blocks.append(f"📋 **{t['title']}**\n\n[HTML 미리보기]({preview_url})")
                    else:
                        answer_blocks.append(f"📋 **{t['title']}**\n\n{t['content']}")
                
                answer = "\n\n---\n\n".join(answer_blocks)
                answer += f"\n\n✅ 위 템플릿들을 참고하여 고객에게 보낼 메시지를 작성해보세요!"
                return answer
            else:
                return f"'{template_type}' 관련 템플릿을 찾지 못했습니다. 다른 키워드로 다시 검색해보세요."
            
        except Exception as e:
            logger.error(f"템플릿 요청 처리 실패: {e}")
            return "템플릿 검색 중 오류가 발생했습니다."
    
    def extract_template_type(self, user_input: str) -> str:
        """템플릿 타입 추출"""
        template_extract_prompt = f"""다음은 고객 메시지 템플릿 유형 목록입니다.
- 생일/기념일
- 구매 후 안내 (출고 완료, 배송 시작, 배송 안내 등 포함)
- 재구매 유도
- 고객 맞춤 메시지 (VIP, 가입 고객 등 포함)
- 리뷰 요청
- 설문 요청
- 이벤트 안내
- 예약
- 재방문
- 해당사항 없음

아래 질문에서 가장 잘 맞는 템플릿 유형을 한글로 정확히 1개만 골라주세요.
설명 없이 키워드만 출력하세요.

질문: {user_input}
"""

        try:
            messages = [
                SystemMessage(content=template_extract_prompt),
                HumanMessage(content=user_input)
            ]
            
            llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
            raw_response = llm.invoke(messages)
            result = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
            
            return result.strip() if result else "해당사항 없음"
            
        except Exception as e:
            logger.error(f"템플릿 타입 추출 실패: {e}")
            return "해당사항 없음"
    
    def filter_templates_by_query(self, templates: List[Dict], query: str) -> List[Dict]:
        """쿼리에 따른 템플릿 필터링"""
        query_lower = query.lower()
        filtered = []
        
        for t in templates:
            title = t.get('title', '')
            title_lower = title.lower()
            
            if ('vip' in query_lower or '단골' in query_lower) and ('vip' in title_lower or '단골' in title_lower):
                filtered.append(t)
            elif ('휴면' in query_lower or '장기미구매' in query_lower) and '휴면' in title:
                filtered.append(t)
            elif ('가입' in query_lower or '회원가입' in query_lower) and ('가입' in title_lower or '회원가입' in title_lower):
                filtered.append(t)
            elif ('최근 구매' in query_lower or '최근구매' in query_lower) and ('최근 구매' in title_lower or '최근구매' in title_lower):
                filtered.append(t)
        
        return filtered if filtered else templates
    
    def _determine_conversation_mode_with_history(self, user_input: str, user_id: int, conversation_id: Optional[int] = None) -> bool:
        """히스토리를 고려한 싱글턴/멀티턴 모드 자동 판단"""
        try:
            # 🔥 수정: 기존 대화가 있으면 무조건 멀티턴 유지
            if conversation_id is not None:
                try:
                    with get_session_context() as db:
                        recent_messages = get_recent_messages(db, conversation_id, limit=1)
                        if recent_messages:
                            logger.info("기존 대화 존재 - 멀티턴 모드 유지")
                            return False  # 멀티턴 유지
                except:
                    pass
            
            # 첫 대화일 때만 키워드 기반 판단
            return self._determine_conversation_mode_by_keywords(user_input)
            
        except Exception as e:
            logger.error(f"히스토리 기반 대화 모드 판단 실패: {e}")
            return True
    
    def _determine_conversation_mode_by_keywords(self, user_input: str) -> bool:
        """키워드 기반 싱글턴/멀티턴 모드 판단 (수정된 버전)"""
        try:
            # 🔥 수정: 템플릿 요청은 무조건 싱글턴
            if any(keyword in user_input for keyword in ["템플릿", "메시지", "문구", "알림", "예시"]):
                return True
            
            # 멀티턴 키워드 (상담/분석 필요)
            multi_turn_keywords = [
                "상담", "도움", "해결", "분석", "계획", "전략",
                "단계별", "자세히", "체계적", "컨설팅",
                "긴급", "문제", "개선", "전문적", "조언",
                "클레임", "고객", "응대", "처리", "관리",
                "불만", "환불", "재방문", "만족도", "관계",
                "어떻게 응대", "어떻게 처리", "어떻게 해결",
                "어떻게 관리", "어떻게 개선", "어떤 방법"
            ]
            
            user_lower = user_input.lower()
            
            # 멀티턴 키워드 체크
            for keyword in multi_turn_keywords:
                if keyword in user_lower:
                    return False  # 멀티턴
            
            # 문장 길이 기반 판단
            if len(user_input) < 20 and user_input.count('?') <= 1:
                return True  # 짧고 단순한 질문은 싱글턴
            
            # 기본값: 복잡한 질문은 멀티턴
            return False
            
        except Exception as e:
            logger.error(f"키워드 기반 대화 모드 판단 실패: {e}")
            return False
    
    def _process_single_turn_query(self, user_input: str, user_id: int) -> Dict[str, Any]:
        """싱글턴 대화 처리"""
        try:
            if any(keyword in user_input for keyword in ["템플릿", "메시지", "문구", "알림"]):
                response_content = self._handle_single_turn_template_request(user_input, user_id)
            else:
                response_content = self._handle_single_turn_general_query(user_input, user_id)
            
            return create_success_response({
                "answer": response_content,
                "agent_type": "customer_service",
                "mode": "single_turn",
                "timestamp": get_current_timestamp()
            })
            
        except Exception as e:
            logger.error(f"싱글턴 쿼리 처리 실패: {e}")
            return create_error_response(
                error_message=f"싱글턴 상담 처리 중 오류: {str(e)}",
                error_code="SINGLE_TURN_ERROR"
            )
    
    def _handle_single_turn_template_request(self, user_input: str) -> str:
        """싱글턴 템플릿 요청 처리"""
        try:
            template_type = self.extract_template_type(user_input)
            templates = get_templates_by_type(template_type)
            
            if template_type == "고객 맞춤 메시지" and templates:
                filtered_templates = self.filter_templates_by_query(templates, user_input)
            else:
                filtered_templates = templates
            
            if filtered_templates:
                answer_blocks = []
                for t in filtered_templates:
                    if t.get("content_type") == "html":
                        preview_url = f"http://localhost:8001/preview/{t['template_id']}"
                        answer_blocks.append(f"📋 **{t['title']}**\n\n[HTML 미리보기]({preview_url})")
                    else:
                        answer_blocks.append(f"📋 **{t['title']}**\n\n{t['content']}")
                
                answer = "\n\n---\n\n".join(answer_blocks)
                answer += f"\n\n✅ 위 템플릿들을 참고하여 고객에게 보낼 메시지를 작성해보세요!"
                return answer
            else:
                return f"'{template_type}' 관련 템플릿을 찾지 못했습니다. 다른 키워드로 다시 검색해보세요."
            
        except Exception as e:
            logger.error(f"싱글턴 템플릿 요청 실패: {e}")
            return "템플릿 검색 중 오류가 발생했습니다."
        
    def get_user_persona_info(self, user_id: int) -> dict:
        """사용자의 페르소나 정보 조회"""
        try:
            with get_session_context() as db:
                persona_info = get_user_persona_info(db, user_id)
            
            logger.info(f"페르소나 정보 조회 완료: {persona_info}")
            return persona_info
            
        except Exception as e:
            logger.error(f"페르소나 정보 조회 실패: {e}")
            return {}
        
    def _handle_single_turn_general_query(self, user_input: str, user_id: int) -> str:
        """싱글턴 일반 쿼리 처리 (페르소나 적용)"""
        try:
            # 🔥 페르소나 정보 가져오기
            persona_info = self.get_user_persona_info(user_id)
            
            topics = self.classify_customer_topic_with_llm(user_input)
            primary_topic = topics[0] if topics else "customer_service"
            
            knowledge_texts = self.get_relevant_knowledge(user_input, topics)
            
            # 🔥 페르소나 기반 프롬프트 생성
            persona_context = ""
            if persona_info:
                business_type = persona_info.get('business_type', '')
                nickname = persona_info.get('nickname', '사장님')
                experience = persona_info.get('experience', 0)
                exp_level = "초보자" if experience == 0 else "경험자"


                persona_context = ""
                if persona_info:
                    business_type = persona_info.get('business_type', '')
                    experience = persona_info.get('experience', 0)
                    
                    persona_context = f"""
        사용자는 {business_type} 업종에서 일하며, {'고객 관리가 처음인' if experience == 0 else '고객 관리 경험이 있는'} 상황입니다.
        이 업종 특성에 맞는 구체적이고 실용적인 조언을 해주되, 업종을 직접적으로 언급하지 말고 자연스럽게 반영해주세요.
        {'기본 개념부터 쉽게 설명하며' if experience == 0 else '실무 중심의 고급 팁을 제공하고'} 실제 상황에서 바로 적용할 수 있는 방법을 제시하세요.
        """
            
            general_prompt = f"""당신은 고객 서비스 전문 컨설턴트입니다.

    {persona_context}

    사용자 질문: "{user_input}"
    주요 토픽: {primary_topic}

    {"관련 전문 지식:" + chr(10) + chr(10).join(knowledge_texts) if knowledge_texts else ""}

    💼 응답 지침:
    1. 업종별 특성을 고려한 맞춤형 조언
    2. 구체적이고 즉시 실행 가능한 해결책
    3. 친근하고 공감적인 톤(과도한 인사나 축하는 생략)
    4. 실제 상황 예시 포함
    5. 경험 수준에 맞는 설명

    응답:"""
            
            messages = [
                SystemMessage(content="당신은 고객 서비스 전문 컨설턴트로서 사용자의 업종과 경험 수준에 맞는 실용적인 조언을 제공합니다."),
                HumanMessage(content=general_prompt)
            ]
            
            llm = ChatOpenAI(model_name="gpt-4o", temperature=0.8)  # 더 창의적으로
            raw_response = llm.invoke(messages)
            response = str(raw_response.content) if hasattr(raw_response, 'content') else str(raw_response)
            
            return response if response else "더 구체적인 상황을 말씀해 주시면 맞춤형 조언을 드릴 수 있어요."
            
        except Exception as e:
            logger.error(f"싱글턴 일반 쿼리 처리 실패: {e}")
            return "죄송합니다. 질문 처리 중 오류가 발생했습니다. 다시 시도해주세요."
        
    def _process_multi_turn_query(self, user_input: str, user_id: int, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        """멀티턴 대화 처리 (수정된 버전)"""
        try:
            # 대화 세션 처리
            session_info = get_or_create_conversation_session(user_id, conversation_id)
            conversation_id = session_info["conversation_id"]
            
            # 대화 상태 조회/생성
            state = self.get_or_create_conversation_state(conversation_id, user_id)
            
            # 사용자 메시지 저장
            with get_session_context() as db:
                create_message(db, conversation_id, "user", "customer_service", user_input)
            
            # 템플릿 요청 체크
            if any(keyword in user_input for keyword in ["템플릿", "메시지", "문구", "알림"]):
                response_content = self.handle_template_request(user_input, state)
            else:
                # 🔥 수정: 현재 단계에 따른 처리
                if state.stage == ConversationStage.INITIAL:
                    # 첫 질문에서 정보 추출 시도
                    extracted_info = self.extract_info_with_llm(user_input)
                    
                    # 추출된 정보 저장
                    for key, value in extracted_info.items():
                        if key in state.collected_info:
                            state.add_collected_info(key, value)
                    
                    # 충분한 정보가 있으면 바로 분석
                    if state.is_information_complete():
                        logger.info("첫 질문에서 충분한 정보 확보 - 즉시 분석")
                        state.update_stage(ConversationStage.ANALYSIS)
                        analysis_result = self.perform_comprehensive_analysis(state)
                        
                        collected_summary = self._create_collected_info_summary(state)
                        response_content = f"""

{analysis_result}"""
                    else:
                        # 추가 정보 필요
                        state.update_stage(ConversationStage.INFORMATION_GATHERING)
                        response_content = f"""안녕하세요! 고객 서비스 컨설턴트입니다. 😊  

보다 정확하고 상황에 맞는 해결책을 드리기 위해 몇 가지 정보가 더 필요해요.
  
**{self._get_next_question(state)}**

너무 어렵게 생각하지 마시고, 편하게 답해주시면 돼요. 함께 차근차근 풀어나가 볼게요!"""
                
                elif state.stage == ConversationStage.INFORMATION_GATHERING:
                    # 정보 수집 단계
                    response_content = self.handle_information_gathering(user_input, state)
                
                elif state.stage == ConversationStage.ANALYSIS:
                    # 분석 완료 후 추가 질문
                    response_content = "분석이 완료되었습니다. 추가 질문이나 수정이 필요한 부분이 있으시면 말씀해주세요!"
                
                else:
                    response_content = "상담이 완료되었습니다. 새로운 질문이 있으시면 언제든 말씀해주세요!"
            
            # 응답 메시지 저장
            insert_message_raw(
                conversation_id=conversation_id,
                sender_type="agent",
                agent_type="customer_service",
                content=response_content
            )
            
            # 표준 응답 형식으로 반환
            try:
                from shared_modules.standard_responses import create_customer_response
                return create_customer_response(
                    conversation_id=conversation_id,
                    answer=response_content,
                    topics=getattr(state.analysis_results, 'primary_topics', []),
                    sources=f"멀티턴 대화 시스템 (단계: {state.stage.value})",
                    conversation_stage=state.stage.value,
                    completion_rate=state.get_completion_rate(),
                    collected_info=state.collected_info,
                    multiturn_flow=True
                )
            except ImportError:
                # 백업용 표준 응답
                return create_success_response({
                    "conversation_id": conversation_id,
                    "answer": response_content,
                    "agent_type": "customer_service",
                    "stage": state.stage.value,
                    "completion_rate": state.get_completion_rate(),
                    "timestamp": get_current_timestamp()
                })
                
        except Exception as e:
            logger.error(f"멀티턴 대화 처리 실패: {e}")
            return create_error_response(f"멀티턴 처리 중 오류: {str(e)}", "MULTITURN_ERROR")
    
    def _get_next_question(self, state: ConversationState) -> str:
        """다음 질문 선택 (우선순위 기반)"""
        for field, question in self.info_gathering_questions.items():
            if not state.collected_info.get(field):
                return question
        return "추가로 알려주실 내용이 있다면 말씀해주세요."
    
    def _create_collected_info_summary(self, state: ConversationState) -> str:
        """수집된 정보 요약 생성"""
        collected_summary = []
        for field, value in state.collected_info.items():
            if value:
                field_name = self.info_gathering_questions.get(field, field)
                collected_summary.append(f"✓ {field_name}: {value}")
        
        if collected_summary:
            return f"""**수집된 정보 ({len(collected_summary)}개):**
{chr(10).join(collected_summary)}"""
        else:
            return "**수집된 정보:** 아직 없음"
    
    def handle_information_gathering(self, user_input: str, state: ConversationState) -> str:
        """정보 수집 단계 처리 (간소화된 버전)"""
        try:
            # LLM으로 정보 추출
            extracted_info = self.extract_info_with_llm(user_input)
            
            # 추출된 정보를 상태에 업데이트
            for key, value in extracted_info.items():
                if key in state.collected_info:
                    state.add_collected_info(key, value)
                    logger.info(f"정보 업데이트: {key} = {value}")
            
            # 🔥 수정: 완료 조건 체크
            filled_count = len([v for v in state.collected_info.values() if v])
            
            if state.is_information_complete() or filled_count >= 3:
                logger.info(f"정보 수집 완료 - 분석 시작 (필드: {filled_count}개)")
                
                # 분석 단계로 전환하고 즉시 분석 수행
                state.update_stage(ConversationStage.ANALYSIS)
                analysis_result = self.perform_comprehensive_analysis(state)
                
                collected_summary = self._create_collected_info_summary(state)
                
                return f"""


{analysis_result}"""
            
            # 아직 더 정보가 필요한 경우
            else:
                next_question = self._get_next_question(state)
                collected_summary = self._create_collected_info_summary(state)
                
                return f"""

{next_question}

더 정확한 해결책을 위해 위 정보를 알려주세요!"""
                
        except Exception as e:
            logger.error(f"정보 수집 처리 실패: {e}")
            return "정보 수집 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def process_user_query(
        self, 
        user_input: str, 
        user_id: int, 
        conversation_id: Optional[int] = None,
        single_turn: Optional[bool] = None
    ) -> Dict[str, Any]:
        """사용자 쿼리 처리 - 자동 멀티턴/싱글턴 대화 지원"""
        
        try:
            single_turn=True
            # 1. 대화 모드 자동 판단 (single_turn이 명시되지 않은 경우)
            if single_turn is None:
                single_turn = self._determine_conversation_mode_with_history(user_input, user_id, conversation_id)
                
            logger.info(f"{'싱글턴' if single_turn else '멀티턴'} 모드로 고객 서비스 쿼리 처리 시작: {user_input[:50]}...")
            
            # 2. 싱글턴 모드 처리
            if single_turn:
                return self._process_single_turn_query(user_input, user_id)
            
            # 3. 멀티턴 모드 처리
            return self._process_multi_turn_query(user_input, user_id, conversation_id)
            
        except Exception as e:
            logger.error(f"{'싱글턴' if single_turn else '멀티턴'} 고객 서비스 쿼리 처리 실패: {e}")
            return create_error_response(
                error_message=f"고객 서비스 상담 처리 중 오류가 발생했습니다: {str(e)}",
                error_code="CUSTOMER_SERVICE_ERROR"
            )
    
    def get_agent_status(self) -> Dict[str, Any]:
        """고객 서비스 에이전트 상태 반환"""
        return {
            "agent_type": "customer_service",
            "version": "3.1.0",
            "conversation_system": "smart_multiturn",
            "stages": [stage.value for stage in ConversationStage],
            "active_conversations": len(self.conversation_states),
            "conversation_stages": {
                conv_id: state.stage.value 
                for conv_id, state in self.conversation_states.items()
            },
            "supported_features": [
                "고객 메시지 템플릿",
                "지능적 멀티턴/싱글턴 모드",
                "LLM 기반 정보 추출",
                "실제 분석 수행",
                "간소화된 대화 흐름"
            ]
        }

    def get_relevant_knowledge(self, query: str, topics: List[str] = None) -> List[str]:
        """실제 전문 지식 검색"""
        try:
            if not hasattr(self.vector_manager, 'search_documents'):
                return []
                
            search_results = self.vector_manager.search_documents(
                query=query,
                collection_name=self.knowledge_collection,
                k=5
            )
            
            filtered_results = []
            for doc in search_results:
                if doc.metadata.get('type') != 'prompt_template':
                    filtered_results.append(doc)
            
            knowledge_texts = []
            for doc in filtered_results[:3]:
                knowledge_area = doc.metadata.get('knowledge_area', '일반')
                content = doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
                knowledge_texts.append(f"[{knowledge_area}]\n{content}")
            
            return knowledge_texts
            
        except Exception as e:
            logger.error(f"전문 지식 검색 실패: {e}")
            return []