"""
마케팅 에이전트 설정 관리 - LangGraph 기반으로 수정
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    """설정 관리 클래스"""
    
    # 기본 설정
    VERSION = "3.0.0-langraph"
    SERVICE_NAME = "marketing_agent_langraph"
    
    # 서버 설정
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8001))
    
    # OpenAI API 설정
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
    
    # 로깅 설정
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = "logs/marketing_agent.log"
    
    # 프로젝트 경로
    BASE_DIR = Path(__file__).parent
    PROMPTS_DIR = BASE_DIR / "prompts"
    LOGS_DIR = BASE_DIR / "logs"
    
    # LangGraph 설정
    MAX_ITERATIONS = 10
    INTERRUPT_ON_HUMAN_INPUT = True
    
    # 대화 관리 설정
    MAX_CONVERSATION_HISTORY = 10
    SESSION_TIMEOUT = 3600  # 1시간
    
    @classmethod
    def setup_logging(cls) -> logging.Logger:
        """로깅 설정"""
        # 로그 디렉토리 생성
        cls.LOGS_DIR.mkdir(exist_ok=True)
        
        # 로거 설정
        logger = logging.getLogger(cls.SERVICE_NAME)
        logger.setLevel(getattr(logging, cls.LOG_LEVEL))
        
        # 핸들러가 이미 있으면 제거
        if logger.handlers:
            logger.handlers.clear()
        
        # 파일 핸들러
        file_handler = logging.FileHandler(cls.LOG_FILE)
        file_handler.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 포매터
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    @classmethod
    def validate_config(cls) -> bool:
        """설정 검증"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
        if not cls.PROMPTS_DIR.exists():
            raise ValueError(f"프롬프트 디렉토리를 찾을 수 없습니다: {cls.PROMPTS_DIR}")
        
        return True
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """설정을 딕셔너리로 반환"""
        return {
            "version": cls.VERSION,
            "service_name": cls.SERVICE_NAME,
            "host": cls.HOST,
            "port": cls.PORT,
            "model": cls.OPENAI_MODEL,
            "temperature": cls.TEMPERATURE,
            "log_level": cls.LOG_LEVEL,
            "prompts_dir": str(cls.PROMPTS_DIR),
            "max_history": cls.MAX_CONVERSATION_HISTORY,
            "max_iterations": cls.MAX_ITERATIONS
        }

# 전역 설정 인스턴스
config = Config()

# 유틸리티 함수들
def create_response(success: bool = True, data: Any = None, error: str = None, **kwargs) -> Dict[str, Any]:
    """표준 응답 형식 생성"""
    response = {
        "success": success,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        **kwargs
    }
    
    if success and data is not None:
        response["data"] = data
    
    if not success and error:
        response["error"] = error
    
    return response

def get_current_timestamp() -> str:
    """현재 시간 반환"""
    import datetime
    return datetime.datetime.now().isoformat()
