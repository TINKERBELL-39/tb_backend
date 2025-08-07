"""
TinkerBell Task Agent v4
공통 모듈을 활용한 업무지원 에이전트
"""

__version__ = "4.0.0"
__author__ = "TinkerBell Team"
__description__ = "공통 모듈 기반 Task Agent - AI 업무 자동화 시스템"

# 공통 모듈 의존성
SHARED_MODULES_REQUIRED = [
    "env_config",
    "llm_utils", 
    "database",
    "db_models",
    "vector_utils",
    "utils"
]

# Task Agent 핵심 컴포넌트
CORE_COMPONENTS = [
    "agent",
    "llm_handler", 
    "rag",
    "automation",
    "models",
    "prompts"
]

# 자동화 서비스
AUTOMATION_SERVICES = [
    "email_service",
    "google_calendar_service", 
    "reminder_service"
]

def get_version_info():
    """버전 정보 반환"""
    return {
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "shared_modules": SHARED_MODULES_REQUIRED,
        "core_components": CORE_COMPONENTS,
        "automation_services": AUTOMATION_SERVICES
    }
