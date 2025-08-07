"""
Task Agent 자동화 공통 모듈 v2
공통 모듈(shared_modules)을 활용한 자동화 작업 지원
"""

# 공통 모듈 기반 컴포넌트들
from .config_manager import AutomationConfigManager, get_automation_config_manager, get_automation_config
from .db_helper import AutomationDatabaseHelper, get_automation_db_helper, get_user_email, get_automation_task, update_task_status
from .utils import (
    AutomationValidationUtils, AutomationDateTimeUtils, AutomationSecurityUtils, 
    AutomationDataUtils, AutomationResponseUtils,
    validate_task_data, format_korean_datetime, mask_email, safe_template_format
)

# 기존 모듈들 (하위 호환성)
from .auth_manager import AuthManager, get_auth_manager
from .http_client import HttpClient, OAuthHttpClient, get_http_client, get_oauth_http_client
from .email_manager import EmailManager, get_email_manager
from .notification_manager import NotificationManager, get_notification_manager

__version__ = "2.0.0"
__description__ = "공통 모듈 기반 자동화 공통 컴포넌트"

__all__ = [
    # 공통 모듈 기반 - 새로운 컴포넌트
    "AutomationConfigManager", "get_automation_config_manager", "get_automation_config",
    "AutomationDatabaseHelper", "get_automation_db_helper", "get_user_email", "get_automation_task", "update_task_status",
    "AutomationValidationUtils", "AutomationDateTimeUtils", "AutomationSecurityUtils", 
    "AutomationDataUtils", "AutomationResponseUtils",
    "validate_task_data", "format_korean_datetime", "mask_email", "safe_template_format",
    
    # 기존 컴포넌트들 (하위 호환성)
    "AuthManager", "get_auth_manager",
    "HttpClient", "OAuthHttpClient", "get_http_client", "get_oauth_http_client", 
    "EmailManager", "get_email_manager",
    "NotificationManager", "get_notification_manager"
]

# 하위 호환성을 위한 별칭들
ConfigManager = AutomationConfigManager
get_config_manager = get_automation_config_manager
# get_config 별칭 제거 - shared_modules.env_config.get_config와 충돌 방지

DatabaseHelper = AutomationDatabaseHelper
get_db_helper = get_automation_db_helper

ValidationUtils = AutomationValidationUtils
DateTimeUtils = AutomationDateTimeUtils
SecurityUtils = AutomationSecurityUtils
DataUtils = AutomationDataUtils

def get_version_info():
    """버전 정보 반환"""
    return {
        "version": __version__,
        "description": __description__,
        "shared_modules_integration": True,
        "components": len(__all__)
    }
