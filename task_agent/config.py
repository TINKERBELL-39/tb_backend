"""
Task Agent 설정 관리 v4
공통 모듈의 env_config를 활용하여 설정 관리
"""

import sys
import os

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))

from env_config import get_config, EnvironmentConfig

class TaskAgentConfig:
    """Task Agent 전용 설정 클래스"""
    
    def __init__(self):
        """설정 초기화"""
        # 공통 설정 로드
        self.base_config = get_config()
        
        # Task Agent 전용 설정
        self.setup_task_agent_config()
    
    def setup_task_agent_config(self):
        """Task Agent 전용 설정"""
        # 기본 설정 상속
        self.OPENAI_API_KEY = self.base_config.OPENAI_API_KEY
        self.GOOGLE_API_KEY = self.base_config.GOOGLE_API_KEY
        self.MYSQL_URL = self.base_config.get_mysql_url()
        self.CHROMA_PERSIST_DIR = self.base_config.CHROMA_PERSIST_DIR
        
        # LLM 설정
        self.DEFAULT_MODEL = self.base_config.DEFAULT_MODEL
        self.EMBEDDING_MODEL = self.base_config.EMBEDDING_MODEL
        self.MAX_TOKENS = self.base_config.MAX_TOKENS
        self.TEMPERATURE = self.base_config.TEMPERATURE
        
        # RAG 설정 (Task Agent 전용)
        self.CHUNK_SIZE = 500
        self.MAX_SEARCH_RESULTS = 5
        
        # 서버 설정
        self.HOST = self.base_config.HOST
        self.PORT = 8005  # Task Agent 전용 포트
        self.LOG_LEVEL = self.base_config.LOG_LEVEL
        
        # 캐시 설정
        self.CACHE_TTL = self.base_config.CACHE_TTL
    
    def validate(self) -> dict:
        """환경 설정 검증"""
        # 공통 모듈의 검증 기능 활용
        base_validation = self.base_config.validate_config()
        
        # Task Agent 전용 검증 추가
        task_issues = []
        task_warnings = []
        
        if not self.CHROMA_PERSIST_DIR:
            task_warnings.append("ChromaDB 디렉토리가 설정되지 않았습니다")
        
        # 검증 결과 병합
        all_issues = base_validation.get("issues", []) + task_issues
        all_warnings = base_validation.get("warnings", []) + task_warnings
        
        return {
            "is_valid": len(all_issues) == 0,
            "issues": all_issues,
            "warnings": all_warnings,
            "task_agent_port": self.PORT
        }
    
    def get_config_dict(self) -> dict:
        """설정을 딕셔너리로 반환"""
        base_dict = self.base_config.to_dict()
        task_dict = {
            "task_agent_port": self.PORT,
            "chunk_size": self.CHUNK_SIZE,
            "max_search_results": self.MAX_SEARCH_RESULTS
        }
        
        return {**base_dict, **task_dict}

# 전역 설정 인스턴스
config = TaskAgentConfig()

# 하위 호환성을 위한 별칭들
Config = TaskAgentConfig
