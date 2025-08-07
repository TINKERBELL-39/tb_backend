"""
설정 관리 공통 모듈 v2
공통 모듈의 env_config를 활용하여 설정 관리
"""

import sys
import os
import json
from typing import Dict, Any, Optional, Union
import logging

import os
import sys

# Add project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from shared_modules.env_config import get_config as env_get_config, EnvironmentConfig
from shared_modules.utils import load_json_file, save_json_file

logger = logging.getLogger(__name__)


class AutomationConfigManager:
    """자동화 작업을 위한 설정 관리 클래스 (공통 모듈 기반)"""
    
    def __init__(self, config_file: Optional[str] = None):
        # 공통 환경 설정 사용 (명시적으로 env_get_config 사용)
        self.env_config = env_get_config()
        
        # 자동화 전용 설정 파일
        self.config_file = config_file or os.path.join(
            os.path.dirname(__file__), 
            "automation_config.json"
        )
        self._local_config = {}
        self._load_local_config()
    
    def _load_local_config(self):
        """로컬 설정 파일 로드"""
        try:
            self._local_config = load_json_file(self.config_file, default={})
            if self._local_config:
                logger.info(f"자동화 설정 파일 로드 완료: {self.config_file}")
            else:
                logger.info(f"자동화 설정 파일이 없거나 비어있음: {self.config_file}")
        except Exception as e:
            logger.error(f"자동화 설정 파일 로드 실패: {e}")
            self._local_config = {}
    
    def get(self, key: str, default: Any = None, use_env: bool = True) -> Any:
        """설정 값 가져오기"""
        # 1. 로컬 설정에서 확인
        keys = key.split('.')
        value = self._local_config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            pass
        
        # 2. 환경 설정에서 확인 (공통 모듈 활용)
        if use_env:
            env_key = key.upper().replace('.', '_')
            env_value = os.getenv(env_key)
            if env_value is not None:
                return self._convert_type(env_value, default)
        
        return default
    
    def _convert_type(self, value: str, default: Any) -> Any:
        """문자열 값을 기본값 타입에 맞게 변환"""
        if default is None:
            return value
        
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        elif isinstance(default, list):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.split(',')
        elif isinstance(default, dict):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        else:
            return value
    
    def set(self, key: str, value: Any, save_to_file: bool = True):
        """설정 값 저장"""
        keys = key.split('.')
        config = self._local_config
        
        # 중첩 딕셔너리 생성
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        
        if save_to_file:
            self._save_local_config()
    
    def _save_local_config(self):
        """로컬 설정 파일 저장"""
        try:
            success = save_json_file(self._local_config, self.config_file)
            if success:
                logger.info(f"자동화 설정 파일 저장 완료: {self.config_file}")
            else:
                logger.error(f"자동화 설정 파일 저장 실패: {self.config_file}")
        except Exception as e:
            logger.error(f"자동화 설정 파일 저장 실패: {e}")
    
    def reload(self):
        """설정 파일 다시 로드"""
        self._load_local_config()
    
    def get_all(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return self._local_config.copy()
    
    # 자주 사용하는 설정들을 위한 편의 메서드들 (공통 모듈 활용)
    
    def get_database_config(self) -> Dict[str, Any]:
        """데이터베이스 설정 가져오기"""
        return {
            "url": self.env_config.get_mysql_url(),
            "host": self.env_config.MYSQL_HOST,
            "port": self.env_config.MYSQL_PORT,
            "name": self.env_config.MYSQL_DB,
            "user": self.env_config.MYSQL_USER,
            "password": self.env_config.MYSQL_PASSWORD
        }
        
    def get_email_config(self, service: str = None) -> Dict[str, Any]:
        """이메일 설정 가져오기"""
        base_config = {
            "service": self.get("email.service", "smtp"),
            "from_email": self.env_config.SMTP_USER or self.get("email.from_email"),
            "from_name": self.get("email.from_name", "TinkerBell 자동화 시스템")
        }
        
        service = service or base_config["service"]
        
        if service.lower() == "smtp":
            base_config.update({
                "smtp_host": self.env_config.SMTP_HOST,
                "smtp_port": self.env_config.SMTP_PORT,
                "smtp_user": self.env_config.SMTP_USER,
                "smtp_password": self.env_config.SMTP_PASSWORD,
                "smtp_use_tls": self.env_config.SMTP_USE_TLS
            })
        elif service.lower() == "sendgrid":
            base_config.update({
                "api_key": self.env_config.SENDGRID_API_KEY,
                "from_email": self.env_config.SENDGRID_FROM_EMAIL,
                "from_name": self.env_config.SENDGRID_FROM_NAME
            })
        elif service.lower() == "aws_ses":
            base_config.update({
                "aws_access_key": self.env_config.AWS_ACCESS_KEY_ID,
                "aws_secret_key": self.env_config.AWS_SECRET_ACCESS_KEY,
                "aws_region": self.env_config.AWS_DEFAULT_REGION,
                "from_email": self.env_config.SES_FROM_EMAIL
            })
        
        return base_config
    
    def get_sms_config(self, service: str = None) -> Dict[str, Any]:
        """SMS 설정 가져오기"""
        base_config = {
            "service": self.get("sms.service", "aws_sns")
        }
        
        service = service or base_config["service"]
        
        if service.lower() == "aws_sns":
            base_config.update({
                "aws_access_key": self.env_config.AWS_ACCESS_KEY_ID,
                "aws_secret_key": self.env_config.AWS_SECRET_ACCESS_KEY,
                "aws_region": self.env_config.AWS_DEFAULT_REGION
            })
        elif service.lower() == "twilio":
            base_config.update({
                "account_sid": self.get("sms.twilio.account_sid"),
                "auth_token": self.get("sms.twilio.auth_token"),
                "from_number": self.get("sms.twilio.from_number")
            })
        
        return base_config
    
    def get_oauth_config(self, platform: str) -> Dict[str, Any]:
        """OAuth 설정 가져오기"""
        return {
            "client_id": self.get(f"oauth.{platform}.client_id"),
            "client_secret": self.get(f"oauth.{platform}.client_secret"),
            "redirect_uri": self.get(f"oauth.{platform}.redirect_uri"),
            "scopes": self.get(f"oauth.{platform}.scopes", [])
        }
    
    def get_slack_config(self) -> Dict[str, Any]:
        """Slack 설정 가져오기"""
        return {
            "bot_token": self.get("slack.bot_token"),
            "app_token": self.get("slack.app_token"),
            "signing_secret": self.get("slack.signing_secret"),
            "webhook_url": self.get("slack.webhook_url")
        }
    
    def get_teams_config(self) -> Dict[str, Any]:
        """Teams 설정 가져오기"""
        return {
            "webhook_url": self.get("teams.webhook_url"),
            "tenant_id": self.get("teams.tenant_id"),
            "client_id": self.get("teams.client_id"),
            "client_secret": self.get("teams.client_secret")
        }
    
    def get_automation_settings(self) -> Dict[str, Any]:
        """자동화 설정 가져오기"""
        return {
            "max_concurrent_tasks": self.get("automation.max_concurrent_tasks", 10),
            "task_timeout": self.get("automation.task_timeout", 300),  # 5분
            "retry_attempts": self.get("automation.retry_attempts", 3),
            "retry_delay": self.get("automation.retry_delay", 5),
            "notification_enabled": self.get("automation.notification_enabled", True),
            "log_level": self.get("automation.log_level", "INFO")
        }
    
    def get_security_settings(self) -> Dict[str, Any]:
        """보안 설정 가져오기"""
        return {
            "api_rate_limit": self.get("security.api_rate_limit", 100),
            "token_expiry": self.get("security.token_expiry", 3600),
            "allowed_origins": self.get("security.allowed_origins", []),
            "require_authentication": self.get("security.require_authentication", True)
        }


# 전역 인스턴스
_automation_config_manager = None

def get_automation_config_manager(config_file: Optional[str] = None) -> AutomationConfigManager:
    """AutomationConfigManager 싱글톤 인스턴스 반환"""
    global _automation_config_manager
    if _automation_config_manager is None:
        _automation_config_manager = AutomationConfigManager(config_file)
    return _automation_config_manager

def get_automation_config(key: str, default: Any = None, use_env: bool = True) -> Any:
    """자동화 설정 값 가져오기 (편의 함수)"""
    return get_automation_config_manager().get(key, default, use_env)

# 기존 코드와의 호환성을 위한 별칭
ConfigManager = AutomationConfigManager
get_config_manager = get_automation_config_manager
# get_config 별칭 제거 - shared_modules.env_config.get_config와 충돌 방지
