"""
통합 에이전트 시스템 설정
"""

import os
from typing import Dict
from dotenv import load_dotenv
from .models import AgentType, AgentConfig, SystemConfig

# 환경변수 로드
load_dotenv()


def get_agent_configs() -> Dict[AgentType, AgentConfig]:
    """각 에이전트 설정을 반환합니다."""
    
    base_url = os.getenv("BASE_URL", "http://localhost")
    
    return {
        AgentType.BUSINESS_PLANNING: AgentConfig(
            name="Business Planning Agent",
            description="비즈니스 플래닝, 창업 준비, 사업 모델 개발 등을 지원하는 에이전트",
            endpoint=f"{base_url}:8001/agent/query",
            keywords=[
                "사업", "창업", "비즈니스", "사업계획", "사업모델", "린캔버스", 
                "시장조사", "경쟁분석", "투자", "펀딩", "자금조달", "MVP",
                "아이디어 검증", "리스크", "성장전략", "사업자등록", "재무계획"
            ],
            confidence_threshold=0.75
        ),
        
        AgentType.CUSTOMER_SERVICE: AgentConfig(
            name="Customer Service Agent", 
            description="고객 서비스, 고객 관계 관리, 고객 만족도 향상을 지원하는 에이전트",
            endpoint=f"{base_url}:8002/agent/query",
            keywords=[
                "고객", "서비스", "상담", "문의", "불만", "피드백", "리뷰",
                "고객만족", "고객유지", "고객분석", "CRM", "CS", "A/S",
                "커뮤니티", "개인정보", "데이터", "세그먼트", "맞춤", "응대"
            ],
            confidence_threshold=0.75
        ),
        
        AgentType.MARKETING: AgentConfig(
            name="Marketing Agent",
            description="마케팅 전략, SNS 마케팅, 광고, 브랜딩 등을 지원하는 에이전트", 
            endpoint=f"{base_url}:8003/agent/query",
            keywords=[
                "마케팅", "광고", "홍보", "브랜딩", "SNS", "소셜미디어",
                "콘텐츠", "블로그", "유튜브", "인스타그램", "페이스북", "트위터",
                "SEO", "검색", "노출", "전환", "퍼포먼스", "ROI", "ROAS",
                "인플루언서", "바이럴", "이메일", "자동화", "캠페인", "브랜드"
            ],
            confidence_threshold=0.75
        ),
        
        AgentType.MENTAL_HEALTH: AgentConfig(
            name="Mental Health Agent",
            description="스트레스 관리, 멘탈 헬스, 심리 상담을 지원하는 에이전트",
            endpoint=f"{base_url}:8004/agent/query", 
            keywords=[
                "스트레스", "우울", "불안", "심리", "멘탈", "정신", "건강",
                "상담", "치료", "힐링", "마음", "감정", "기분", "번아웃",
                "PHQ-9", "심리검사", "진단", "상태", "관리", "휴식", "회복"
            ],
            confidence_threshold=0.8
        ),
        
        AgentType.TASK_AUTOMATION: AgentConfig(
            name="Task Automation Agent",
            description="업무 자동화, 생산성 도구, 일정 관리 등을 지원하는 에이전트",
            endpoint=f"https://localhost:8005/agent/query",
            keywords=[
                "자동화", "업무", "태스크", "일정", "스케줄", "캘린더", "알림",
                "생산성", "효율", "도구", "앱", "시스템", "프로세스", "워크플로우",
                "이메일", "메시지", "발송", "예약", "리마인더", "관리", "최적화"
            ],
            confidence_threshold=0.75
        )
    }


def get_system_config() -> SystemConfig:
    """시스템 설정을 반환합니다."""
    return SystemConfig(
        agents=get_agent_configs(),
        routing_confidence_threshold=float(os.getenv("ROUTING_CONFIDENCE_THRESHOLD", "0.8")),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() == "true",
        max_alternative_responses=int(os.getenv("MAX_ALTERNATIVE_RESPONSES", "2")),
        default_agent=AgentType(os.getenv("DEFAULT_AGENT", "business_planning"))
    )


# LLM 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 서버 설정  
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 타임아웃 설정
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30"))
ROUTING_TIMEOUT = int(os.getenv("ROUTING_TIMEOUT", "10"))
