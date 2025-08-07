"""
자동화 서비스
자동화 매니저를 래핑하는 서비스 레이어
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from models import AutomationRequest, AutomationResponse

logger = logging.getLogger(__name__)

class AutomationService:
    """자동화 서비스 - 비즈니스 로직과 데이터 접근 분리"""
    
    def __init__(self, automation_manager):
        """자동화 서비스 초기화"""
        self.automation_manager = automation_manager
        logger.info("AutomationService 초기화 완료")

    async def create_task(self, request: AutomationRequest) -> AutomationResponse:
        """자동화 작업 생성"""
        try:
            # 자동화 매니저를 통해 작업 생성
            response = await self.automation_manager.create_automation_task(request)
            return response
        except Exception as e:
            logger.error(f"자동화 작업 생성 실패: {e}")
            raise

    async def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """작업 상태 조회"""
        try:
            status = await self.automation_manager.get_task_status(task_id)
            # 상태 정보 보강
            if "error" not in status:
                status["human_readable_status"] = self._get_human_readable_status(status.get("status"))
            return status
        except Exception as e:
            logger.error(f"작업 상태 조회 실패: {e}")
            return {"error": str(e)}

    def _get_human_readable_status(self, status: str) -> str:
        """사람이 읽기 쉬운 상태 문자열"""
        status_map = {
            "pending": "대기 중",
            "scheduled": "예약됨", 
            "processing": "실행 중",
            "success": "완료",
            "failed": "실패",
            "cancelled": "취소됨"
        }
        return status_map.get(status, status)

    async def cancel_task(self, task_id: int) -> bool:
        """작업 취소"""
        try:
            result = await self.automation_manager.cancel_task(task_id)
            return result
        except Exception as e:
            logger.error(f"작업 취소 실패: {e}")
            return False

    async def get_user_tasks(self, user_id: int, status: Optional[str] = None, 
                           limit: int = 50) -> List[Dict[str, Any]]:
        """사용자 작업 목록 조회"""
        try:
            tasks = await self.automation_manager.get_user_tasks(user_id, status, limit)
            return tasks
        except Exception as e:
            logger.error(f"사용자 작업 목록 조회 실패: {e}")
            return []

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        try:
            manager_stats = await self.automation_manager.get_system_stats()
            return {
                "service": "AutomationService",
                "version": "5.0.0", 
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "automation_manager": manager_stats
            }
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return {
                "service": "AutomationService",
                "version": "5.0.0",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def cleanup(self):
        """서비스 정리"""
        try:
            await self.automation_manager.cleanup()
            logger.info("AutomationService 정리 완료")
        except Exception as e:
            logger.error(f"AutomationService 정리 실패: {e}")
