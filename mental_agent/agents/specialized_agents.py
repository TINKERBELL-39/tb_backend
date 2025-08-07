"""
Mental Health Specialized Agents
정신건강 전문 분야별 에이전트들
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseMentalHealthAgent

logger = logging.getLogger(__name__)

class CounselorAgent(BaseMentalHealthAgent):
    """심리 상담사 에이전트"""
    
    def __init__(self):
        super().__init__("심리 상담사")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """심리 상담 관련 쿼리 처리"""
        try:
            # 안전성 평가
            safety_assessment = self.assess_safety(user_input)
            
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
                "specialization": "counseling",
                "safety_assessment": safety_assessment
            }
            
        except Exception as e:
            logger.error(f"심리 상담 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "상담 처리 중 오류가 발생했습니다. 전문가와 직접 상담하시기 바랍니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """심리 상담 전문 프롬프트 생성"""
        return f"""당신은 경험이 풍부한 심리 상담사입니다.
        
다음 원칙에 따라 상담을 진행해주세요:
- 무조건적 긍정적 관심과 공감
- 비판하지 않는 수용적 태도  
- 내담자의 자기결정권 존중
- 비밀보장 및 안전한 환경 제공
- 경청과 반영적 듣기
- 적절한 개방형 질문

현재 내담자 상태:
{context.get('emotional_analysis', '정보 없음')}

내담자 메시지: "{user_input}"

공감적이고 전문적인 상담을 제공하되, 필요시 추가 평가나 전문가 의뢰를 제안해주세요."""

class CrisisCounselorAgent(BaseMentalHealthAgent):
    """위기 상담사 에이전트"""
    
    def __init__(self):
        super().__init__("위기 상담사")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """위기 상담 관련 쿼리 처리"""
        try:
            # 위기 상황 우선 평가
            safety_assessment = self.assess_safety(user_input)
            
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input + " 위기상황 자살예방")
            
            if knowledge:
                specialized_prompt += f"\n\n위기 개입 지침:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            # 위기 상황인 경우 응급 정보 추가
            if not safety_assessment.get("is_safe", True):
                response += "\n\n🚨 **즉시 도움받을 수 있는 연락처**:\n"
                response += "- 생명의전화: 1393 (24시간)\n"
                response += "- 정신건강위기상담: 1577-0199\n"
                response += "- 응급실: 119\n"
                response += "\n지금 안전한 곳에 계신가요? 혼자 계시지 마시고 누군가와 함께해주세요."
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "crisis_intervention",
                "safety_assessment": safety_assessment,
                "crisis_protocol_activated": not safety_assessment.get("is_safe", True)
            }
            
        except Exception as e:
            logger.error(f"위기 상담 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "위기 상황 처리 중 오류가 발생했습니다. 즉시 119 또는 1393으로 연락하세요.",
                "error": str(e),
                "emergency_contacts": ["119", "1393", "1577-0199"]
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """위기 상담 전문 프롬프트 생성"""
        return f"""당신은 위기 개입 전문 상담사입니다.
        
위기 상담 원칙:
- 즉시 안전 확보가 최우선
- 침착하고 신뢰할 수 있는 태도
- 구체적이고 즉시 실행 가능한 안전 계획
- 지지적이면서도 직접적인 개입
- 전문가 자원 연결

위기 상황 평가:
{context.get('crisis_indicators', '정보 없음')}

내담자 메시지: "{user_input}"

안전을 최우선으로 하여 즉시 도움이 되는 구체적인 지침을 제공해주세요."""

class TherapistAgent(BaseMentalHealthAgent):
    """정신건강 치료사 에이전트"""
    
    def __init__(self):
        super().__init__("정신건강 치료사")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """정신건강 치료 관련 쿼리 처리"""
        try:
            safety_assessment = self.assess_safety(user_input)
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input + " 정신건강 치료 평가")
            
            if knowledge:
                specialized_prompt += f"\n\n치료 가이드라인:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            # PHQ-9 점수가 있는 경우 치료 권고사항 추가
            phq9_score = context.get('phq9_results', {}).get('total_score', 0)
            if phq9_score >= 15:
                response += f"\n\n📋 **치료 권고사항** (PHQ-9: {phq9_score}점):\n"
                response += "- 정신건강의학과 전문의 상담 권장\n"
                response += "- 약물치료와 심리치료 병행 고려\n"
                response += "- 정기적인 모니터링 필요"
            elif phq9_score >= 10:
                response += f"\n\n📋 **치료 권고사항** (PHQ-9: {phq9_score}점):\n"
                response += "- 심리상담 또는 인지행동치료 권장\n"
                response += "- 생활습관 개선과 병행\n"
                response += "- 4-6주 후 재평가"
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "therapy",
                "safety_assessment": safety_assessment,
                "treatment_recommendations": True if phq9_score >= 10 else False
            }
            
        except Exception as e:
            logger.error(f"정신건강 치료 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "치료 상담 중 오류가 발생했습니다. 전문의와 상담하시기 바랍니다.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """정신건강 치료 전문 프롬프트 생성"""
        return f"""당신은 정신건강 치료 전문가입니다.
        
치료적 접근 원칙:
- 과학적 근거 기반 평가
- 개인 맞춤형 치료 계획
- 체계적인 증상 모니터링
- 다학제적 접근 고려
- 치료 순응도 향상

평가 결과:
{context.get('assessment_results', '정보 없음')}

내담자 메시지: "{user_input}"

전문적인 치료 관점에서 평가하고 적절한 치료 방향을 제시해주세요."""

class WellnessCoachAgent(BaseMentalHealthAgent):
    """웰니스 코치 에이전트"""
    
    def __init__(self):
        super().__init__("웰니스 코치")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """웰니스 코칭 관련 쿼리 처리"""
        try:
            safety_assessment = self.assess_safety(user_input)
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input + " 웰빙 생활습관 스트레스관리")
            
            if knowledge:
                specialized_prompt += f"\n\n웰니스 가이드:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            # 실용적인 웰니스 팁 추가
            response += "\n\n💡 **오늘부터 시작할 수 있는 작은 변화**:\n"
            response += "- 하루 10분 산책하기\n"
            response += "- 깊은 호흡 3번 연습\n"
            response += "- 감사한 일 1가지 적어보기\n"
            response += "- 충분한 수분 섭취 (하루 8잔)\n"
            response += "- 규칙적인 수면 시간 지키기"
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "wellness_coaching",
                "safety_assessment": safety_assessment,
                "practical_tips": True
            }
            
        except Exception as e:
            logger.error(f"웰니스 코칭 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "웰니스 코칭 중 오류가 발생했습니다. 기본적인 자기관리를 시작해보세요.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """웰니스 코치 전문 프롬프트 생성"""
        return f"""당신은 웰니스 및 라이프스타일 코치입니다.
        
코칭 원칙:
- 긍정적이고 동기부여하는 접근
- 실현 가능한 작은 목표 설정
- 전인적 웰빙 관점 (신체, 정신, 사회적)
- 개인의 강점과 자원 활용
- 지속 가능한 변화 추구

현재 상태:
{context.get('collected_info', '정보 없음')}

내담자 메시지: "{user_input}"

동기부여가 되고 실천 가능한 웰니스 가이드를 제공해주세요."""

class MindfulnessGuideAgent(BaseMentalHealthAgent):
    """마음챙김 가이드 에이전트"""
    
    def __init__(self):
        super().__init__("마음챙김 가이드")
        
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """마음챙김 관련 쿼리 처리"""
        try:
            safety_assessment = self.assess_safety(user_input)
            specialized_prompt = self.get_specialized_prompt(user_input, context)
            knowledge = self.search_knowledge(user_input + " 명상 마음챙김 호흡법")
            
            if knowledge:
                specialized_prompt += f"\n\n마음챙김 기법:\n{chr(10).join(knowledge)}"
            
            response = self.generate_response(specialized_prompt, context)
            
            # 간단한 마음챙김 실습 추가
            response += "\n\n🧘‍♀️ **지금 바로 해볼 수 있는 마음챙김**:\n"
            response += "1. **3-3-3 호흡법**: 3초 들이쉬고, 3초 멈추고, 3초 내쉬기\n"
            response += "2. **5-4-3-2-1 기법**: \n"
            response += "   - 보이는 것 5가지\n"
            response += "   - 들리는 것 4가지\n"
            response += "   - 만져지는 것 3가지\n"
            response += "   - 냄새나는 것 2가지\n"
            response += "   - 맛보는 것 1가지\n"
            response += "3. **바디스캔**: 발끝부터 머리까지 몸의 감각 느껴보기"
            
            return {
                "agent_type": self.agent_type,
                "response": response,
                "knowledge_used": len(knowledge) > 0,
                "specialization": "mindfulness",
                "safety_assessment": safety_assessment,
                "mindfulness_exercises": True
            }
            
        except Exception as e:
            logger.error(f"마음챙김 가이드 쿼리 처리 실패: {e}")
            return {
                "agent_type": self.agent_type,
                "response": "마음챙김 가이드 중 오류가 발생했습니다. 잠시 깊게 숨을 쉬어보세요.",
                "error": str(e)
            }
    
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """마음챙김 가이드 전문 프롬프트 생성"""
        return f"""당신은 마음챙김과 명상 전문 가이드입니다.
        
가이드 원칙:
- 현재 순간에 집중하는 접근
- 판단하지 않는 관찰
- 수용과 인정의 태도
- 점진적이고 친근한 안내
- 일상 생활 통합 강조

현재 감정 상태:
{context.get('emotional_analysis', '정보 없음')}

내담자 메시지: "{user_input}"

평온하고 차분한 에너지로 실용적인 마음챙김 지도를 제공해주세요."""
