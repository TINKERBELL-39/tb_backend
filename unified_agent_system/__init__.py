"""
통합 에이전트 시스템

이 시스템은 5개의 전문 에이전트를 통합하여 사용자의 질의를 적절한 에이전트로 라우팅합니다.

지원하는 에이전트:
- BusinessPlanningAgent: 비즈니스 플래닝 및 창업 상담
- CustomerServiceAgent: 고객 서비스 및 관계 관리  
- MarketingAgent: 마케팅 전략 및 실행
- MentalAgent: 멘탈 헬스 및 심리 상담
- TaskAgent: 업무 자동화 및 생산성 도구
"""

__version__ = "1.0.0"
__author__ = "SKN11-FINAL-5Team"

from core.workflow import UnifiedAgentWorkflow
from core.models import UnifiedRequest, UnifiedResponse, AgentType

__all__ = [
    "UnifiedAgentWorkflow",
    "UnifiedRequest", 
    "UnifiedResponse",
    "AgentType"
]
