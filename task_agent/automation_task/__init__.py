"""
Task Agent 자동화 서비스 모듈
"""

__version__ = "1.0.0"

# 자동화 서비스 목록
AUTOMATION_SERVICES = [
    "email_service",
    "google_calendar_service", 
    # "sns_service",
    "reminder_service"
]

# 공통 모듈
COMMON_MODULES = [
    "config_manager",
    "db_helper", 
    "utils",
    "auth_manager",
    "email_manager",
    "http_client",
    "notification_manager"
]

def get_available_services():
    """사용 가능한 자동화 서비스 목록 반환"""
    return AUTOMATION_SERVICES

def get_common_modules():
    """공통 모듈 목록 반환"""
    return COMMON_MODULES
