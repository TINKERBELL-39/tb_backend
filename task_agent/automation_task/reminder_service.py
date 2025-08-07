"""
리마인더 서비스 - 공용 모듈 사용 버전
"""

from typing import Dict, List, Any, Optional
import logging

from .common import get_notification_manager, get_config_manager, ValidationUtils

logger = logging.getLogger(__name__)


class ReminderService:
    """리마인더 서비스 클래스 (공용 NotificationManager 사용)"""
    
    def __init__(self):
        self.notification_manager = get_notification_manager()
        self.config_manager = get_config_manager()
    
    async def send_reminder(self, user_id: int, message: str, 
                           channels: List[str] = None, urgency: str = "medium",
                           task_id: Optional[str] = None, 
                           additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """통합 리마인더 발송"""
        try:
            # 기본 채널 설정
            if not channels:
                channels = ["app", "email"]  # 기본값: 앱 알림 + 이메일
            
            # 추가 데이터 설정
            reminder_data = additional_data or {}
            if task_id:
                reminder_data["task_id"] = task_id
                reminder_data["subject"] = f"📋 업무 리마인더 - {task_id}"
            else:
                reminder_data["subject"] = "📋 업무 리마인더"
            
            # 통합 알림 발송
            result = await self.notification_manager.send_notification(
                user_id=user_id,
                message=message,
                channels=channels,
                urgency=urgency,
                additional_data=reminder_data
            )
            
            if result.get("success"):
                logger.info(f"리마인더 발송 성공: User {user_id} - {result.get('success_count')}/{result.get('total_channels')}개 채널")
            else:
                logger.warning(f"리마인더 발송 실패: User {user_id} - 모든 채널 실패")
            
            return result
            
        except Exception as e:
            logger.error(f"리마인더 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_app_notification(self, user_id: int, message: str, 
                                   urgency: str = "medium", 
                                   task_id: Optional[str] = None) -> Dict[str, Any]:
        """앱 내 알림 발송"""
        additional_data = {}
        if task_id:
            additional_data["task_id"] = task_id
        
        return await self.notification_manager.send_app_notification(
            user_id=user_id,
            message=message,
            urgency=urgency,
            additional_data=additional_data
        )
    
    async def send_email_reminder(self, user_id: int, message: str, 
                                 task_id: Optional[str] = None,
                                 custom_subject: Optional[str] = None) -> Dict[str, Any]:
        """이메일 리마인더 발송"""
        additional_data = {
            "subject": custom_subject or f"📋 업무 리마인더{f' - {task_id}' if task_id else ''}"
        }
        if task_id:
            additional_data["task_id"] = task_id
        
        return await self.notification_manager.send_email_notification(
            user_id=user_id,
            message=message,
            additional_data=additional_data
        )
    
    async def send_sms_reminder(self, user_id: int, message: str) -> Dict[str, Any]:
        """SMS 리마인더 발송"""
        return await self.notification_manager.send_sms_notification(
            user_id=user_id,
            message=message
        )
    
    async def send_slack_message(self, message: str, channel: Optional[str] = None, 
                                recipients: List[str] = None) -> Dict[str, Any]:
        """Slack 메시지 발송"""
        additional_data = {}
        if channel:
            additional_data["channel"] = channel
        if recipients:
            additional_data["recipients"] = recipients
        
        return await self.notification_manager.send_slack_notification(
            message=message,
            additional_data=additional_data
        )
    
    async def send_teams_message(self, message: str, channel: Optional[str] = None, 
                                webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Microsoft Teams 메시지 발송"""
        additional_data = {}
        if channel:
            additional_data["channel"] = channel
        if webhook_url:
            additional_data["webhook_url"] = webhook_url
        
        return await self.notification_manager.send_teams_notification(
            message=message,
            additional_data=additional_data
        )
    
    async def send_scheduled_reminder(self, user_id: int, message: str,
                                     schedule_time: str, channels: List[str] = None,
                                     task_id: Optional[str] = None) -> Dict[str, Any]:
        """예약된 리마인더 발송 (즉시 실행용)"""
        # 실제 스케줄링은 별도 시스템에서 처리하고, 
        # 여기서는 즉시 발송하는 것으로 구현
        logger.info(f"예약 리마인더 발송: {schedule_time}")
        
        return await self.send_reminder(
            user_id=user_id,
            message=message,
            channels=channels,
            task_id=task_id
        )
    
    async def send_urgent_reminder(self, user_id: int, message: str,
                                  task_id: Optional[str] = None) -> Dict[str, Any]:
        """긴급 리마인더 발송 (모든 채널 사용)"""
        return await self.send_reminder(
            user_id=user_id,
            message=message,
            channels=["app", "email", "sms"],  # 모든 주요 채널 사용
            urgency="high",
            task_id=task_id
        )
    
    async def send_daily_summary(self, user_id: int, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """일일 요약 리마인더 발송"""
        try:
            # 요약 메시지 생성
            pending_tasks = summary_data.get("pending_tasks", 0)
            completed_tasks = summary_data.get("completed_tasks", 0)
            overdue_tasks = summary_data.get("overdue_tasks", 0)
            
            message = f"""📊 일일 업무 요약
            
완료된 작업: {completed_tasks}개
진행 중인 작업: {pending_tasks}개
지연된 작업: {overdue_tasks}개

오늘도 수고하셨습니다! 🎉"""
            
            return await self.send_reminder(
                user_id=user_id,
                message=message,
                channels=["app", "email"],
                urgency="low",
                additional_data={
                    "subject": "📊 일일 업무 요약",
                    "summary_data": summary_data
                }
            )
            
        except Exception as e:
            logger.error(f"일일 요약 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_deadline_alert(self, user_id: int, task_title: str, 
                                 deadline: str, time_remaining: str,
                                 task_id: Optional[str] = None) -> Dict[str, Any]:
        """마감일 알림 발송"""
        try:
            message = f"""⏰ 마감일 알림
            
작업: {task_title}
마감일: {deadline}
남은 시간: {time_remaining}

서둘러 완료해주세요!"""
            
            # 남은 시간에 따라 긴급도 조정
            urgency = "high" if "시간" in time_remaining else "medium"
            channels = ["app", "email", "sms"] if urgency == "high" else ["app", "email"]
            
            return await self.send_reminder(
                user_id=user_id,
                message=message,
                channels=channels,
                urgency=urgency,
                task_id=task_id,
                additional_data={
                    "subject": f"⏰ 마감일 알림 - {task_title}",
                    "deadline": deadline,
                    "time_remaining": time_remaining
                }
            )
            
        except Exception as e:
            logger.error(f"마감일 알림 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    # ===== 알림 설정 관리 =====
    
    async def update_notification_settings(self, user_id: int, settings: Dict[str, bool]) -> bool:
        """사용자 알림 설정 업데이트"""
        return await self.notification_manager.update_notification_settings(user_id, settings)
    
    async def get_notification_settings(self, user_id: int) -> Dict[str, bool]:
        """사용자 알림 설정 조회"""
        return await self.notification_manager.get_notification_settings(user_id)
    
    async def get_notification_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """사용자 알림 이력 조회"""
        return await self.notification_manager.get_notification_history(user_id, limit)
    
    async def test_notification_channels(self, user_id: int) -> Dict[str, Any]:
        """알림 채널 테스트"""
        test_message = "🔔 알림 테스트 메시지입니다."
        
        return await self.send_reminder(
            user_id=user_id,
            message=test_message,
            channels=["app", "email"],  # SMS는 제외 (비용 고려)
            urgency="low",
            additional_data={"subject": "🔔 알림 테스트"}
        )


# 전역 인스턴스를 위한 팩토리 함수
_global_reminder_service = None

def get_reminder_service() -> ReminderService:
    """ReminderService 싱글톤 인스턴스 반환"""
    global _global_reminder_service
    if _global_reminder_service is None:
        _global_reminder_service = ReminderService()
    return _global_reminder_service


# ===== 하위 호환성을 위한 함수들 =====

async def send_app_notification(user_id: int, message: str, urgency: str = "medium"):
    """하위 호환성을 위한 앱 알림 함수"""
    service = get_reminder_service()
    return await service.send_app_notification(user_id, message, urgency)

async def send_email_reminder(user_id: int, message: str, task_id: Optional[str] = None):
    """하위 호환성을 위한 이메일 리마인더 함수"""
    service = get_reminder_service()
    return await service.send_email_reminder(user_id, message, task_id)

async def send_sms_reminder(user_id: int, message: str):
    """하위 호환성을 위한 SMS 리마인더 함수"""
    service = get_reminder_service()
    return await service.send_sms_reminder(user_id, message)

async def send_slack_message(message: str, channel: Optional[str], recipients: List[str]):
    """하위 호환성을 위한 Slack 메시지 함수"""
    service = get_reminder_service()
    return await service.send_slack_message(message, channel, recipients)

async def send_teams_message(message: str, channel: Optional[str], webhook_url: Optional[str] = None):
    """하위 호환성을 위한 Teams 메시지 함수"""
    service = get_reminder_service()
    return await service.send_teams_message(message, channel, webhook_url)

async def update_notification_settings(user_id: int, settings: Dict[str, bool]) -> bool:
    """하위 호환성을 위한 알림 설정 업데이트 함수"""
    service = get_reminder_service()
    return await service.update_notification_settings(user_id, settings)

async def get_notification_settings(user_id: int) -> Dict[str, bool]:
    """하위 호환성을 위한 알림 설정 조회 함수"""
    service = get_reminder_service()
    return await service.get_notification_settings(user_id)


# ===== 사용 예시 =====

async def example_usage():
    """ReminderService 사용 예시"""
    
    # 1. 서비스 인스턴스 생성
    reminder_service = get_reminder_service()
    
    # 2. 기본 리마인더 발송
    result = await reminder_service.send_reminder(
        user_id=123,
        message="오늘 마감인 프로젝트 보고서를 작성해주세요.",
        channels=["app", "email"],
        urgency="medium",
        task_id="TASK-456"
    )
    
    if result["success"]:
        print(f"리마인더 발송 성공: {result['success_count']}/{result['total_channels']}개 채널")
    else:
        print(f"리마인더 발송 실패: {result.get('error')}")
    
    # 3. 긴급 리마인더 발송
    urgent_result = await reminder_service.send_urgent_reminder(
        user_id=123,
        message="1시간 후 마감인 작업이 있습니다!",
        task_id="TASK-789"
    )
    
    # 4. 마감일 알림 발송
    deadline_result = await reminder_service.send_deadline_alert(
        user_id=123,
        task_title="월간 보고서 작성",
        deadline="2024-01-31 18:00",
        time_remaining="2시간 30분",
        task_id="TASK-101"
    )
    
    # 5. 일일 요약 발송
    summary_result = await reminder_service.send_daily_summary(
        user_id=123,
        summary_data={
            "completed_tasks": 5,
            "pending_tasks": 3,
            "overdue_tasks": 1
        }
    )
    
    # 6. 알림 설정 관리
    settings = await reminder_service.get_notification_settings(123)
    print(f"현재 알림 설정: {settings}")
    
    # 7. 알림 채널 테스트
    test_result = await reminder_service.test_notification_channels(123)
    print(f"채널 테스트 결과: {test_result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
