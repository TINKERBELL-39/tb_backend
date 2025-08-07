"""
Customer Service Specialized Agents
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseCustomerServiceAgent

logger = logging.getLogger(__name__)

class CustomerServiceAgent(BaseCustomerServiceAgent):
    """고객 응대 전문 에이전트"""
    
    def __init__(self):
        super().__init__("고객 응대 전문가")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """고객 응대 관련 쿼리 처리"""
        try:
            # 전문화된 프롬프트 생성
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            
            # 관련 지식 검색
            knowledge = self.search_knowledge(user_input)
            
            # 프롬프트에 지식 추가
            if knowledge:
                specialized_prompt += f"\n\n참고 자료:\n{chr(10).join(knowledge)}"
            
            # 응답 생성
            response = self.generate_response(specialized_prompt, context)
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "customer_service"
            }
            
        except Exception as e:
            logger.error(f"고객 응대 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "고객 응대 관련 처리 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """고객 응대 전문 프롬프트 생성"""
        return f"""당신은 고객 응대 전문가입니다.
        
다음 영역에 대한 전문적인 조언을 제공해주세요:
- 고객 감정에 공감하는 커뮤니케이션
- 정중하고 효과적인 응답 방법
- 클레임 및 불만 처리 전략
- 후속 조치 방안

사용자 질문: {user_input}

고객 정보:
{context.get('collected_info', '정보 없음')}

고객의 감정을 이해하고 적절히 대응할 수 있는 실용적인 가이드를 제공해주세요."""

class CustomerRetentionAgent(BaseCustomerServiceAgent):
    """고객 유지 전문 에이전트"""
    
    def __init__(self):
        super().__init__("고객 유지 전문가")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """고객 유지 관련 쿼리 처리"""
        try:
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input)
            
            if knowledge:
                specialized_prompt += f"\n\n참고 자료:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "customer_retention"
            }
            
        except Exception as e:
            logger.error(f"고객 유지 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "고객 유지 관련 처리 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """고객 유지 전문 프롬프트 생성"""
        return f"""당신은 고객 유지 전문가입니다.
        
다음 관점에서 전문적인 리텐션 전략을 제공해주세요:
- 고객 행동 패턴 분석
- 재방문 및 재구매 유도 방법
- 단골 고객 전환 전략
- 고객 생애 가치(LTV) 증대
- 이탈 방지 및 윈백 캠페인

사용자 질문: {user_input}

고객 세그먼트: {context.get('collected_info', {}).get('customer_segment', '명시되지 않음')}
현재 상황: {context.get('collected_info', {}).get('current_situation', '명시되지 않음')}

데이터 기반의 실행 가능한 리텐션 전략을 제시해주세요."""

class CustomerSatisfactionAgent(BaseCustomerServiceAgent):
    """고객 만족도 전문 에이전트"""
    
    def __init__(self):
        super().__init__("고객 만족도 전문가")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """고객 만족도 관련 쿼리 처리"""
        try:
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input)
            
            if knowledge:
                specialized_prompt += f"\n\n참고 자료:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "customer_satisfaction"
            }
            
        except Exception as e:
            logger.error(f"고객 만족도 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "고객 만족도 관련 처리 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """고객 만족도 전문 프롬프트 생성"""
        return f"""당신은 고객 만족도 전문가입니다.
        
다음 요소들을 포함한 체계적인 만족도 개선 방안을 제시해주세요:
- 고객 여정(Customer Journey) 분석
- 터치포인트별 만족도 측정
- CSAT, NPS 등 만족도 지표 활용
- 불만족 요인 분석 및 개선
- 고객 경험(CX) 최적화
- 서비스 품질 향상 방안

사용자 질문: {user_input}

수집된 고객 정보:
{context.get('collected_info', '정보 없음')}

실행 가능하고 측정 가능한 만족도 개선 전략을 제안해주세요."""

class CommunityBuildingAgent(BaseCustomerServiceAgent):
    """커뮤니티 구축 전문 에이전트"""
    
    def __init__(self):
        super().__init__("커뮤니티 구축 전문가")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """커뮤니티 구축 관련 쿼리 처리"""
        try:
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input)
            
            if knowledge:
                specialized_prompt += f"\n\n참고 자료:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "community_building"
            }
            
        except Exception as e:
            logger.error(f"커뮤니티 구축 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "커뮤니티 구축 관련 처리 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """커뮤니티 구축 전문 프롬프트 생성"""
        return f"""당신은 커뮤니티 구축 전문가입니다.
        
다음 영역에서 효과적인 커뮤니티 전략을 제시해주세요:
- 온라인/오프라인 커뮤니티 플랫폼 선택
- 고객 참여 유도 전략
- 커뮤니티 콘텐츠 기획
- 이벤트 및 캠페인 운영
- 브랜드 애착도 및 충성도 증진
- 커뮤니티 운영 가이드라인

사용자 질문: {user_input}

비즈니스 타입: {context.get('collected_info', {}).get('business_type', '명시되지 않음')}
고객 세그먼트: {context.get('collected_info', {}).get('customer_segment', '명시되지 않음')}

실제 운영 가능한 구체적인 커뮤니티 구축 방안을 제안해주세요."""
