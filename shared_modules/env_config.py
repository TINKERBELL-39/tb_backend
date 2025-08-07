"""
환경 설정 공통 모듈
각 에이전트에서 공통으로 사용하는 환경 변수 및 설정 관리
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class EnvironmentConfig:
    """환경 설정 관리 클래스"""
    
    def __init__(self, env_path: str = None):
        """
        환경 설정 초기화
        
        Args:
            env_path: .env 파일 경로 (기본값: ../unified_agent_system/.env)
        """
        if env_path is None:
            env_path = os.path.join(os.path.dirname(__file__), "../unified_agent_system/.env")
        
        # .env 파일 로드
        load_dotenv(dotenv_path=env_path)
        
        # 환경 변수 로드
        self._load_environment_variables()
    
    def _load_environment_variables(self):
        """환경 변수 로드"""
        # MySQL 설정
        self.MYSQL_HOST = os.getenv("MYSQL_HOST")
        self.MYSQL_PORT = self._get_int_env("MYSQL_PORT", 3306)
        self.MYSQL_USER = os.getenv("MYSQL_USER")
        self.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
        self.MYSQL_DB = os.getenv("MYSQL_DB")
        self.MYSQL_URL = os.getenv("MYSQL_URL")
        
        # API 키
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        # Naver API 설정
        self.NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
        self.NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
        
        # 벡터 데이터베이스 설정
        self.CHROMA_DIR = os.getenv("CHROMA_DIR", "/Users/comet39/SKN_PJT/SKN11-FINAL-5Team/unified_agent_system/vector_db")
        self.CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/Users/comet39/SKN_PJT/SKN11-FINAL-5Team/unified_agent_system/vector_db")
        
        # SMTP 설정
        self.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT = self._get_int_env("SMTP_PORT", 587)
        self.SMTP_USER = os.getenv("SMTP_USER")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
        self.SMTP_USE_TLS = self._get_bool_env("SMTP_USE_TLS", True)
        
        # SendGrid 설정
        self.SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        self.SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
        self.SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "TinkerBell AI")
        
        # AWS 설정
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL")
        
        # LLM 설정
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.MAX_TOKENS = self._get_int_env("MAX_TOKENS", 1500)
        self.TEMPERATURE = self._get_float_env("TEMPERATURE", 0.7)
        
        # 서버 설정
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = self._get_int_env("PORT", 8080)
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # 기타 설정
        self.APP_NAME = os.getenv("APP_NAME", "Solo Preneur Helper")
        self.DEBUG = self._get_bool_env("DEBUG", False)
        self.CACHE_TTL = self._get_int_env("CACHE_TTL", 1800)
    
    def _get_int_env(self, key: str, default: int) -> int:
        """정수형 환경 변수 가져오기"""
        try:
            value = os.getenv(key)
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _get_float_env(self, key: str, default: float) -> float:
        """실수형 환경 변수 가져오기"""
        try:
            value = os.getenv(key)
            return float(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """불린형 환경 변수 가져오기"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def get_mysql_url(self) -> str:
        """MySQL 연결 URL 생성"""
        if self.MYSQL_URL:
            return self.MYSQL_URL
        
        if all([self.MYSQL_HOST, self.MYSQL_USER, self.MYSQL_PASSWORD, self.MYSQL_DB]):
            return (
                f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@"
                f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            )
        
        return None
    
    def get_mysql_connector_url(self) -> str:
        """MySQL Connector 연결 URL 생성"""
        if all([self.MYSQL_HOST, self.MYSQL_USER, self.MYSQL_PASSWORD, self.MYSQL_DB]):
            return (
                f"mysql+mysqlconnector://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@"
                f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            )
        
        return None
    
    def validate_config(self) -> Dict[str, Any]:
        """환경 설정 검증"""
        issues = []
        warnings = []
        
        # 필수 API 키 검증
        if not self.OPENAI_API_KEY and not self.GOOGLE_API_KEY:
            issues.append("OpenAI 또는 Google API 키가 필요합니다")
            
        # Naver API 설정 검증
        if not self.NAVER_CLIENT_ID or not self.NAVER_CLIENT_SECRET:
            warnings.append("Naver API 설정이 불완전합니다")
        
        # 데이터베이스 설정 검증
        if not self.get_mysql_url():
            warnings.append("MySQL 데이터베이스 설정이 불완전합니다")
        
        # SMTP 설정 검증
        if not self.SMTP_USER or not self.SMTP_PASSWORD:
            warnings.append("SMTP 설정이 불완전합니다")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "config_summary": {
                "openai_available": bool(self.OPENAI_API_KEY),
                "google_available": bool(self.GOOGLE_API_KEY),
                "naver_available": bool(self.NAVER_CLIENT_ID and self.NAVER_CLIENT_SECRET),
                "mysql_available": bool(self.get_mysql_url()),
                "smtp_available": bool(self.SMTP_USER and self.SMTP_PASSWORD),
                "chroma_dir": self.CHROMA_DIR
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 반환 (민감한 정보 제외)"""
        return {
            "mysql_host": self.MYSQL_HOST,
            "mysql_port": self.MYSQL_PORT,
            "mysql_db": self.MYSQL_DB,
            "openai_available": bool(self.OPENAI_API_KEY),
            "google_available": bool(self.GOOGLE_API_KEY),
            "naver_available": bool(self.NAVER_CLIENT_ID and self.NAVER_CLIENT_SECRET),
            "chroma_dir": self.CHROMA_DIR,
            "smtp_host": self.SMTP_HOST,
            "smtp_port": self.SMTP_PORT,
            "default_model": self.DEFAULT_MODEL,
            "embedding_model": self.EMBEDDING_MODEL,
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.TEMPERATURE,
            "host": self.HOST,
            "port": self.PORT,
            "log_level": self.LOG_LEVEL,
            "app_name": self.APP_NAME,
            "debug": self.DEBUG
        }


# 전역 설정 인스턴스
_global_config = None

def get_config(env_path: str = None) -> EnvironmentConfig:
    """
    전역 설정 인스턴스 반환 (싱글톤)
    
    Args:
        env_path: .env 파일 경로
    
    Returns:
        EnvironmentConfig: 환경 설정 인스턴스
    """
    global _global_config
    if _global_config is None:
        _global_config = EnvironmentConfig(env_path)
    return _global_config

def reload_config(env_path: str = None) -> EnvironmentConfig:
    """
    설정 재로드
    
    Args:
        env_path: .env 파일 경로
    
    Returns:
        EnvironmentConfig: 새로운 환경 설정 인스턴스
    """
    global _global_config
    _global_config = EnvironmentConfig(env_path)
    return _global_config

# 편의 함수들
def get_mysql_url() -> Optional[str]:
    """MySQL URL 반환"""
    return get_config().get_mysql_url()

def get_mysql_connector_url() -> Optional[str]:
    """MySQL Connector URL 반환"""
    return get_config().get_mysql_connector_url()

def get_openai_api_key() -> Optional[str]:
    """OpenAI API 키 반환"""
    return get_config().OPENAI_API_KEY

def get_google_api_key() -> Optional[str]:
    """Google API 키 반환"""
    return get_config().GOOGLE_API_KEY

def get_chroma_dir() -> str:
    """ChromaDB 디렉토리 반환"""
    return get_config().CHROMA_DIR
