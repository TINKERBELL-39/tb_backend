"""
라우팅 로직 - 대화 흐름 분석과 의도 이해 중심의 라우팅
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .models import AgentType, RoutingDecision, Priority, UnifiedRequest
from .config import OPENAI_API_KEY, GEMINI_API_KEY, get_system_config

logger = logging.getLogger(__name__)


class ConversationFlow:
    """대화 흐름과 컨텍스트를 분석하는 클래스"""
    
    def __init__(self):
        self.current_agent: Optional[AgentType] = None
        self.previous_agent: Optional[AgentType] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.last_agent_output: Optional[str] = None
        self.conversation_topic: Optional[str] = None
        self.task_chain: List[Dict[str, Any]] = []  # 연결된 작업들
        
    def add_interaction(self, user_message: str, agent_type: AgentType, 
                       agent_response: str, routing_reasoning: str):
        """새로운 상호작용 추가"""
        self.previous_agent = self.current_agent
        self.current_agent = agent_type
        self.last_agent_output = agent_response
        
        interaction = {
            "timestamp": datetime.now(),
            "user_message": user_message,
            "agent_type": agent_type,
            "agent_response": agent_response,
            "routing_reasoning": routing_reasoning
        }
        
        self.conversation_history.append(interaction)
        
        # 최근 10개 상호작용만 유지
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def analyze_reference_intent(self, current_message: str) -> Dict[str, Any]:
        """참조 표현과 의도 분석"""
        analysis = {
            "has_reference": False,
            "reference_type": None,
            "intended_action": None,
            "target_agent": None,
            "confidence": 0.0
        }
        
        # 참조 표현 패턴
        reference_patterns = [
            r'\b(그거|그것|이거|이것|위의|앞의|해당|저거|저것)\s*(기반|바탕|토대|참고|활용)*',
            r'\b(이전|방금|앞서)\s*(만든|작성한|생성한)*',
            r'\b(그|이|저)\s*(계획|기획|문서|결과|내용)'
        ]
        
        # 참조 표현 확인
        for pattern in reference_patterns:
            if re.search(pattern, current_message, re.IGNORECASE):
                analysis["has_reference"] = True
                analysis["reference_type"] = "previous_output"
                break
        
        # 의도된 액션 분석
        action_patterns = {
            "marketing": [
                r'마케팅.*?(제작|만들|생성|작성)',
                r'(광고|홍보|컨텐츠|콘텐츠).*?(만들|제작|생성|작성)',
                r'(카피|문구|슬로건).*?(만들|제작|생성|작성)',
                r'(SNS|블로그|소셜미디어).*?(컨텐츠|콘텐츠|포스팅)'
            ],
            "customer_service": [
                r'(고객|서비스|상담).*?(응답|답변|매뉴얼|가이드)',
                r'(FAQ|질문|문의).*?(만들|작성|정리)',
                r'(고객지원|고객응대).*?(시나리오|스크립트)'
            ],
            "task_automation": [
                r'(자동화|워크플로우|프로세스).*?(만들|구성|설계)',
                r'(업무|작업).*?(자동화|효율화|시스템화)',
                r'(스케줄|일정).*?(관리|자동화)'
            ],
            "mental_health": [
                r'(상담|치료|힐링).*?(계획|프로그램|가이드)',
                r'(스트레스|우울|불안).*?(관리|해결|대처)',
                r'(정신건강|멘탈헬스).*?(프로그램|상담)'
            ]
        }
        
        for agent_key, patterns in action_patterns.items():
            for pattern in patterns:
                if re.search(pattern, current_message, re.IGNORECASE):
                    analysis["intended_action"] = agent_key
                    analysis["target_agent"] = self._get_agent_type(agent_key)
                    analysis["confidence"] = 0.8
                    break
            if analysis["target_agent"]:
                break
        
        return analysis
    
    def _get_agent_type(self, agent_key: str) -> AgentType:
        """문자열을 AgentType으로 변환"""
        mapping = {
            "marketing": AgentType.MARKETING,
            "customer_service": AgentType.CUSTOMER_SERVICE,
            "task_automation": AgentType.TASK_AUTOMATION,
            "mental_health": AgentType.MENTAL_HEALTH,
            "business_planning": AgentType.BUSINESS_PLANNING
        }
        return mapping.get(agent_key, AgentType.BUSINESS_PLANNING)
    
    def should_continue_with_current_agent(self, current_message: str) -> bool:
        """현재 에이전트와 계속해야 하는지 판단"""
        if not self.current_agent or not self.last_agent_output:
            return False
        
        # 단순한 후속 질문들
        simple_followup_patterns = [
            r'^(네|응|좋아|감사|고마워|알겠어)',
            r'^(더|또|추가로|그리고).*?(알려|설명|말해)',
            r'^(자세히|구체적으로|더).*?(설명|알려)',
            r'^(이해했어|알겠어|좋아).*?'
        ]
        
        for pattern in simple_followup_patterns:
            if re.search(pattern, current_message, re.IGNORECASE):
                return True
        
        return False
    
    def get_context_summary(self) -> str:
        """현재 대화 컨텍스트 요약"""
        if not self.conversation_history:
            return "새로운 대화"
        
        recent_interactions = self.conversation_history[-3:]
        context_parts = []
        
        for interaction in recent_interactions:
            agent = interaction["agent_type"].value
            user_msg = interaction["user_message"][:50] + "..."
            context_parts.append(f"{agent}: {user_msg}")
        
        return " → ".join(context_parts)


class QueryRouter:
    """대화 흐름 분석 기반 쿼리 라우터"""
    
    def __init__(self):
        self.config = get_system_config()
        self.llm = self._initialize_llm()
        self.conversation_flow = ConversationFlow()
        self._create_enhanced_prompts()
        
    def _initialize_llm(self):
        """LLM 초기화"""
        try:
            if OPENAI_API_KEY:
                return ChatOpenAI(
                    model="gpt-3.5-turbo",
                    temperature=0.1,  # 일관된 라우팅을 위해 낮은 temperature
                    api_key=OPENAI_API_KEY
                )
        except Exception as e:
            logger.warning(f"OpenAI 초기화 실패: {e}")
        
        try:
            if GEMINI_API_KEY:
                return ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    temperature=0.1,
                    google_api_key=GEMINI_API_KEY
                )
        except Exception as e:
            logger.error(f"Gemini 초기화도 실패: {e}")
            raise Exception("사용 가능한 LLM이 없습니다")
    
    def _create_enhanced_prompts(self):
        """향상된 프롬프트 생성"""
        
        # 기본 라우팅 프롬프트 (첫 번째 메시지용)
        self.initial_routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """
당신은 사용자의 의도를 정확히 파악하여 적절한 전문 에이전트를 선택하는 라우터입니다.

사용 가능한 에이전트들:
1. business_planning: 사업 계획, 창업 아이디어, 비즈니스 전략 수립
2. marketing: 마케팅 전략, 광고 컨텐츠, 홍보 자료 제작
3. customer_service: 고객 서비스, 상담, 지원 시스템 구축
4. task_automation: 업무 자동화, 워크플로우, 프로세스 개선
5. mental_health: 정신건강, 스트레스 관리, 심리 상담

사용자의 **핵심 의도**를 파악하여 가장 적합한 에이전트를 선택하세요.

출력 형식:
AGENT: [에이전트명]
CONFIDENCE: [0.0-1.0]
REASONING: [선택 이유를 한 문장으로]
"""),
            ("human", "사용자 요청: {query}")
        ])
        
        # 컨텍스트 기반 라우팅 프롬프트
        self.context_routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """
당신은 대화의 흐름을 분석하여 적절한 에이전트를 선택하는 전문가입니다.

이전 대화 컨텍스트:
{context_summary}

현재 에이전트: {current_agent}
이전 에이전트 출력: {previous_output}

분석해야 할 요소들:
1. 사용자가 이전 결과물을 참조하고 있는가? ("그거", "이것", "위의" 등)
2. 새로운 작업을 요청하는가?
3. 이전 결과를 다른 형태로 가공/활용하려는가?
4. 단순히 추가 설명을 원하는가?

**중요한 패턴들:**
- "그거 기반으로 마케팅 컨텐츠 만들어줘" → MARKETING 에이전트
- "이걸로 고객 응답 매뉴얼 작성해줘" → CUSTOMER_SERVICE 에이전트  
- "이 계획을 자동화할 수 있을까?" → TASK_AUTOMATION 에이전트
- "더 자세히 설명해줘" → 현재 에이전트 유지

사용 가능한 에이전트: business_planning, marketing, customer_service, task_automation, mental_health

출력 형식:
REFERENCE_DETECTED: [yes/no] - 이전 결과물 참조 여부
NEW_TASK: [yes/no] - 새로운 작업 요청 여부
AGENT: [에이전트명]
CONFIDENCE: [0.0-1.0]
REASONING: [상세한 분석과 선택 이유]
"""),
            ("human", "새로운 사용자 요청: {query}")
        ])
    
    async def route_query(self, request: UnifiedRequest, 
                         conversation_history: Optional[List[Dict[str, Any]]] = None,
                         enable_context_routing: bool = True) -> RoutingDecision:
        """향상된 쿼리 라우팅"""
        try:
            # 1. 선호 에이전트가 명시된 경우
            if request.preferred_agent:
                return RoutingDecision(
                    agent_type=request.preferred_agent,
                    confidence=1.0,
                    reasoning="사용자가 직접 지정한 에이전트",
                    keywords=[],
                    priority=Priority.MEDIUM
                )
            
            # 2. 첫 번째 메시지이거나 컨텍스트가 없는 경우
            if not self.conversation_flow.conversation_history or not enable_context_routing:
                return await self._initial_routing(request.message)
            
            # 3. 컨텍스트 기반 라우팅
            return await self._context_aware_routing(request.message, conversation_history)
            
        except Exception as e:
            logger.error(f"라우팅 실패: {e}")
            return RoutingDecision(
                agent_type=self.config.default_agent,
                confidence=0.5,
                reasoning=f"라우팅 오류로 기본 에이전트 사용: {str(e)}",
                keywords=[],
                priority=Priority.MEDIUM
            )
    
    async def _initial_routing(self, query: str) -> RoutingDecision:
        """첫 번째 메시지에 대한 라우팅"""
        try:
            chain = self.initial_routing_prompt | self.llm | StrOutputParser()
            result = await chain.ainvoke({"query": query})
            
            return self._parse_routing_result(result)
            
        except Exception as e:
            logger.error(f"초기 라우팅 실패: {e}")
            raise
    
    async def _context_aware_routing(self, query: str, 
                                   conversation_history: Optional[List[Dict[str, Any]]]) -> RoutingDecision:
        """컨텍스트를 고려한 라우팅"""
        try:
            # 참조 의도 분석
            reference_analysis = self.conversation_flow.analyze_reference_intent(query)
            
            # 현재 에이전트와 계속할지 판단
            if self.conversation_flow.should_continue_with_current_agent(query):
                return RoutingDecision(
                    agent_type=self.conversation_flow.current_agent,
                    confidence=0.9,
                    reasoning="단순 후속 질문으로 현재 에이전트 유지",
                    keywords=[],
                    priority=Priority.MEDIUM
                )
            
            # 참조 의도가 감지되고 명확한 타겟 에이전트가 있는 경우
            if (reference_analysis["has_reference"] and 
                reference_analysis["target_agent"] and 
                reference_analysis["confidence"] > 0.7):
                
                return RoutingDecision(
                    agent_type=reference_analysis["target_agent"],
                    confidence=reference_analysis["confidence"],
                    reasoning=f"참조 기반 새로운 작업 요청: {reference_analysis['intended_action']}",
                    keywords=[],
                    priority=Priority.MEDIUM
                )
            
            # LLM 기반 컨텍스트 라우팅
            context_vars = {
                "query": query,
                "context_summary": self.conversation_flow.get_context_summary(),
                "current_agent": (self.conversation_flow.current_agent.value 
                                if self.conversation_flow.current_agent else "none"),
                "previous_output": (self.conversation_flow.last_agent_output[:200] + "..." 
                                  if self.conversation_flow.last_agent_output else "없음")
            }
            
            chain = self.context_routing_prompt | self.llm | StrOutputParser()
            result = await chain.ainvoke(context_vars)
            
            return self._parse_context_result(result)
            
        except Exception as e:
            logger.error(f"컨텍스트 라우팅 실패: {e}")
            # 안전한 폴백
            if self.conversation_flow.current_agent:
                return RoutingDecision(
                    agent_type=self.conversation_flow.current_agent,
                    confidence=0.6,
                    reasoning=f"컨텍스트 라우팅 오류로 현재 에이전트 유지: {str(e)}",
                    keywords=[],
                    priority=Priority.MEDIUM
                )
            else:
                return await self._initial_routing(query)
    
    def _parse_routing_result(self, result: str) -> RoutingDecision:
        """기본 라우팅 결과 파싱"""
        try:
            lines = result.strip().split('\n')
            parsed = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed[key.strip().upper()] = value.strip()
            
            agent_str = parsed.get('AGENT', '').lower()
            confidence = float(parsed.get('CONFIDENCE', '0.5'))
            reasoning = parsed.get('REASONING', 'LLM 기반 라우팅')
            
            # AgentType 매핑
            agent_mapping = {
                'business_planning': AgentType.BUSINESS_PLANNING,
                'marketing': AgentType.MARKETING,
                'customer_service': AgentType.CUSTOMER_SERVICE,
                'task_automation': AgentType.TASK_AUTOMATION,
                'mental_health': AgentType.MENTAL_HEALTH
            }
            
            agent_type = agent_mapping.get(agent_str, AgentType.BUSINESS_PLANNING)
            
            return RoutingDecision(
                agent_type=agent_type,
                confidence=max(0.0, min(1.0, confidence)),
                reasoning=reasoning,
                keywords=[],
                priority=Priority.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"라우팅 결과 파싱 실패: {e}")
            return RoutingDecision(
                agent_type=AgentType.BUSINESS_PLANNING,
                confidence=0.5,
                reasoning=f"파싱 오류: {str(e)}",
                keywords=[],
                priority=Priority.MEDIUM
            )
    
    def _parse_context_result(self, result: str) -> RoutingDecision:
        """컨텍스트 라우팅 결과 파싱"""
        try:
            lines = result.strip().split('\n')
            parsed = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed[key.strip().upper()] = value.strip()
            
            reference_detected = parsed.get('REFERENCE_DETECTED', 'no').lower() == 'yes'
            new_task = parsed.get('NEW_TASK', 'no').lower() == 'yes'
            agent_str = parsed.get('AGENT', '').lower()
            confidence = float(parsed.get('CONFIDENCE', '0.5'))
            reasoning = parsed.get('REASONING', '컨텍스트 기반 라우팅')
            
            # 에이전트 매핑
            agent_mapping = {
                'business_planning': AgentType.BUSINESS_PLANNING,
                'marketing': AgentType.MARKETING,
                'customer_service': AgentType.CUSTOMER_SERVICE,
                'task_automation': AgentType.TASK_AUTOMATION,
                'mental_health': AgentType.MENTAL_HEALTH
            }
            
            agent_type = agent_mapping.get(agent_str, AgentType.BUSINESS_PLANNING)
            
            # 참조 감지되었지만 새로운 작업이 아닌 경우 현재 에이전트 유지
            if reference_detected and not new_task and self.conversation_flow.current_agent:
                agent_type = self.conversation_flow.current_agent
                reasoning += " (참조 기반 연속 질문)"
            
            return RoutingDecision(
                agent_type=agent_type,
                confidence=max(0.0, min(1.0, confidence)),
                reasoning=reasoning,
                keywords=[],
                priority=Priority.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"컨텍스트 라우팅 결과 파싱 실패: {e}")
            return RoutingDecision(
                agent_type=self.conversation_flow.current_agent or AgentType.BUSINESS_PLANNING,
                confidence=0.5,
                reasoning=f"파싱 오류로 현재 에이전트 유지: {str(e)}",
                keywords=[],
                priority=Priority.MEDIUM
            )
    
    def update_conversation_flow(self, user_message: str, agent_type: AgentType, 
                               agent_response: str, routing_reasoning: str):
        """대화 흐름 업데이트"""
        self.conversation_flow.add_interaction(
            user_message, agent_type, agent_response, routing_reasoning
        )
    
    def get_conversation_insights(self) -> Dict[str, Any]:
        """대화 인사이트 반환"""
        return {
            "current_agent": (self.conversation_flow.current_agent.value 
                            if self.conversation_flow.current_agent else None),
            "previous_agent": (self.conversation_flow.previous_agent.value 
                             if self.conversation_flow.previous_agent else None),
            "interaction_count": len(self.conversation_flow.conversation_history),
            "context_summary": self.conversation_flow.get_context_summary(),
            "task_chain_length": len(self.conversation_flow.task_chain)
        }
    
    def reset_context(self):
        """컨텍스트 초기화"""
        self.conversation_flow = ConversationFlow()
        logger.info("대화 컨텍스트가 초기화되었습니다")
    
    def get_agent_recommendations(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """에이전트 추천 (간단한 폴백용)"""
        # 이 메서드는 기존 호환성을 위해 유지하지만 간소화
        return [
            {
                'agent_type': AgentType.BUSINESS_PLANNING,
                'confidence': 0.5,
                'matched_keywords': [],
                'description': '기본 에이전트'
            }
        ]
