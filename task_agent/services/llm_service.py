"""
LLM 서비스
LLM 핸들러를 래핑하는 서비스 레이어
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class LLMService:
    """LLM 서비스 - 비즈니스 로직과 LLM 처리 분리"""
    
    def __init__(self, llm_handler):
        """LLM 서비스 초기화"""
        self.llm_handler = llm_handler
        logger.info("LLMService 초기화 완료")

    async def analyze_intent(self, message: str, persona: str, 
                           conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """의도 분석"""
        try:
            return await self.llm_handler.analyze_intent(message, persona, conversation_history)
        except Exception as e:
            logger.error(f"의도 분석 실패: {e}")
            return {"intent": "general_inquiry", "confidence": 0.5, "keywords": []}

    async def analyze_automation_intent(self, message: str, 
                                      conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """자동화 의도 분석"""
        try:
            automation_type = await self.llm_handler.classify_automation_intent(message)
            return {
                "is_automation": bool(automation_type),
                "automation_type": automation_type,
                "confidence": 0.8 if automation_type else 0.2
            }
        except Exception as e:
            logger.error(f"자동화 의도 분석 실패: {e}")
            return {"is_automation": False, "automation_type": None, "confidence": 0.0}

    async def extract_automation_info(self, message: str, automation_type: str,
                                    conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """자동화 정보 추출"""
        try:
            extraction_type = self._map_automation_to_extraction(automation_type)
            return await self.llm_handler.extract_information(
                message, extraction_type, conversation_history
            )
        except Exception as e:
            logger.error(f"자동화 정보 추출 실패: {e}")
            return {}

    async def generate_response(self, message: str, persona: str, intent: str,
                              context: str, conversation_history: List[Dict] = None) -> str:
        """응답 생성"""
        try:
            return await self.llm_handler.generate_response(
                message, persona, intent, context, conversation_history
            )
        except Exception as e:
            logger.error(f"응답 생성 실패: {e}")
            return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

    def _map_automation_to_extraction(self, automation_type: str) -> str:
        """자동화 타입을 추출 타입으로 매핑"""
        mapping = {
            "calendar_sync": "schedule",
            "send_email": "email",
            "todo_list": "todo_list"
        }
        return mapping.get(automation_type, "general_info")

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        try:
            return {
                "service": "LLMService",
                "version": "5.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "llm_handler": self.llm_handler.get_status() if hasattr(self.llm_handler, 'get_status') else {"status": "unknown"}
            }
        except Exception as e:
            return {"service": "LLMService", "status": "error", "error": str(e)}

    async def cleanup(self):
        """서비스 정리"""
        try:
            if hasattr(self.llm_handler, 'cleanup'):
                await self.llm_handler.cleanup()
            logger.info("LLMService 정리 완료")
        except Exception as e:
            logger.error(f"LLMService 정리 실패: {e}")
