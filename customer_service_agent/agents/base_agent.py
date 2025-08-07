"""
Customer Service Base Agent
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from shared_modules import get_llm_manager, get_vector_manager

logger = logging.getLogger(__name__)

class BaseCustomerServiceAgent(ABC):
    """고객 서비스 에이전트 기본 클래스"""
    
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.llm_manager = get_llm_manager()
        self.vector_manager = get_vector_manager()
        
    @abstractmethod
    def process_query(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """쿼리 처리 (하위 클래스에서 구현)"""
        pass
    
    @abstractmethod
    def get_specialized_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """전문화된 프롬프트 생성 (하위 클래스에서 구현)"""
        pass
    
    def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """응답 생성"""
        try:
            messages = [
                {"role": "system", "content": f"당신은 {self.agent_type} 전문가입니다."},
                {"role": "user", "content": prompt}
            ]
            
            return self.llm_manager.generate_response_sync(messages)
            
        except Exception as e:
            logger.error(f"{self.agent_type} 응답 생성 실패: {e}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다."
    
    def search_knowledge(self, query: str, collection_name: str = "customer-service-knowledge") -> List[str]:
        """지식 검색"""
        try:
            search_results = self.vector_manager.search_documents(
                query=query,
                collection_name=collection_name,
                k=3
            )
            
            return [doc.page_content for doc in search_results]
            
        except Exception as e:
            logger.error(f"지식 검색 실패: {e}")
            return []
