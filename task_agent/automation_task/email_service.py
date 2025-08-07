"""
이메일 발송 서비스 - 공용 모듈 사용 버전
"""

from typing import Dict, List, Any, Optional
import logging

import os
import sys

# Add project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

# Use relative import for local modules
from .common import get_email_manager, get_config_manager, ValidationUtils

logger = logging.getLogger(__name__)


class EmailService:
    """이메일 발송 서비스 클래스"""
    
    def __init__(self):
        self.email_manager = get_email_manager()
        self.config_manager = get_config_manager()
    
    def is_valid_email(self, email: str) -> bool:
        """이메일 주소 형식 검증"""
        return ValidationUtils.is_valid_email(email)
    
    async def send_email(self, to_emails: List[str], subject: str, body: str,
                        html_body: Optional[str] = None, attachments: List[str] = None,
                        cc_emails: List[str] = None, bcc_emails: List[str] = None,
                        from_email: Optional[str] = None, from_name: Optional[str] = None,
                        service: Optional[str] = None) -> Dict[str, Any]:
        """통합 이메일 발송"""
        try:
            # 서비스 설정 가져오기
            if not service:
                email_config = self.config_manager.get_email_config()
                service = email_config.get("service", "smtp")
            
            # 이메일 발송
            result = await self.email_manager.send_email(
                service=service,
                to_emails=to_emails,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=attachments,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                from_email=from_email,
                from_name=from_name
            )
            
            if result["success"]:
                logger.info(f"이메일 발송 성공 ({service}): {len(to_emails)}명에게 발송")
            else:
                logger.error(f"이메일 발송 실패 ({service}): {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"이메일 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_email_smtp(self, to_emails: List[str], subject: str, body: str,
                             html_body: Optional[str] = None, attachments: List[str] = None,
                             cc_emails: List[str] = None, bcc_emails: List[str] = None,
                             from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """SMTP를 통한 이메일 발송"""
        return await self.send_email(
            to_emails, subject, body, html_body, attachments,
            cc_emails, bcc_emails, from_email, from_name, service="smtp"
        )
    
    async def send_email_sendgrid(self, to_emails: List[str], subject: str, body: str,
                                 html_body: Optional[str] = None, attachments: List[str] = None,
                                 cc_emails: List[str] = None, bcc_emails: List[str] = None,
                                 from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """SendGrid를 통한 이메일 발송"""
        return await self.send_email(
            to_emails, subject, body, html_body, attachments,
            cc_emails, bcc_emails, from_email, from_name, service="sendgrid"
        )
    
    async def send_email_aws_ses(self, to_emails: List[str], subject: str, body: str,
                                html_body: Optional[str] = None, attachments: List[str] = None,
                                cc_emails: List[str] = None, bcc_emails: List[str] = None,
                                from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """AWS SES를 통한 이메일 발송"""
        return await self.send_email(
            to_emails, subject, body, html_body, attachments,
            cc_emails, bcc_emails, from_email, from_name, service="aws_ses"
        )
    
    def create_html_template(self, title: str, content: str, 
                           additional_info: Optional[str] = None) -> str:
        """HTML 이메일 템플릿 생성"""
        return self.email_manager.create_html_template(title, content, additional_info)
    
    async def send_reminder_email(self, to_email: str, reminder_message: str,
                                 task_id: Optional[str] = None, 
                                 custom_subject: Optional[str] = None) -> Dict[str, Any]:
        """리마인더 이메일 발송"""
        try:
            subject = custom_subject or "📋 업무 리마인더"
            
            html_body = self.create_html_template(
                title=subject,
                content=reminder_message,
                additional_info=f"작업 ID: {task_id}" if task_id else None
            )
            
            return await self.send_email(
                to_emails=[to_email],
                subject=subject,
                body=reminder_message,
                html_body=html_body
            )
            
        except Exception as e:
            logger.error(f"리마인더 이메일 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_notification_email(self, to_email: str, notification_title: str,
                                     notification_content: str, 
                                     priority: str = "normal") -> Dict[str, Any]:
        """알림 이메일 발송"""
        try:
            # 우선순위에 따른 제목 설정
            priority_icons = {
                "high": "🚨",
                "medium": "⚠️", 
                "normal": "📢",
                "low": "💬"
            }
            
            icon = priority_icons.get(priority, "📢")
            subject = f"{icon} {notification_title}"
            
            html_body = self.create_html_template(
                title=subject,
                content=notification_content,
                additional_info=f"우선순위: {priority.upper()}"
            )
            
            return await self.send_email(
                to_emails=[to_email],
                subject=subject,
                body=notification_content,
                html_body=html_body
            )
            
        except Exception as e:
            logger.error(f"알림 이메일 발송 실패: {e}")
            return {"success": False, "error": str(e)}


# 전역 인스턴스를 위한 팩토리 함수
_global_email_service = None

def get_email_service() -> EmailService:
    """EmailService 싱글톤 인스턴스 반환"""
    global _global_email_service
    if _global_email_service is None:
        _global_email_service = EmailService()
    return _global_email_service


# 기존 함수 형태 API 유지 (하위 호환성)
async def send_email_smtp(*args, **kwargs):
    """하위 호환성을 위한 SMTP 이메일 발송 함수"""
    service = get_email_service()
    return await service.send_email_smtp(*args, **kwargs)

async def send_email_sendgrid(*args, **kwargs):
    """하위 호환성을 위한 SendGrid 이메일 발송 함수"""
    service = get_email_service()
    return await service.send_email_sendgrid(*args, **kwargs)

async def send_email_aws_ses(*args, **kwargs):
    """하위 호환성을 위한 AWS SES 이메일 발송 함수"""
    service = get_email_service()
    return await service.send_email_aws_ses(*args, **kwargs)

def is_valid_email(email: str) -> bool:
    """하위 호환성을 위한 이메일 검증 함수"""
    return ValidationUtils.is_valid_email(email)


# ===== 사용 예시 =====

async def example_usage():
    """EmailService 사용 예시"""
    
    # 1. 서비스 인스턴스 생성
    email_service = get_email_service()
    
    # 2. 기본 이메일 발송
    result = await email_service.send_email(
        to_emails=["hs981120@naver.com"],
        subject="테스트 이메일",
        body="안녕하세요, 테스트 이메일입니다.",
        html_body="<h1>안녕하세요</h1><p>테스트 이메일입니다.</p>"
    )
    
    if result["success"]:
        print(f"이메일 발송 성공: {result.get('message_id')}")
    else:
        print(f"이메일 발송 실패: {result.get('error')}")
    
    # 3. 리마인더 이메일 발송
    reminder_result = await email_service.send_reminder_email(
        to_email="user@example.com",
        reminder_message="오늘 마감인 작업이 있습니다.",
        task_id="TASK-123"
    )
    
    # 4. 알림 이메일 발송
    notification_result = await email_service.send_notification_email(
        to_email="user@example.com",
        notification_title="시스템 점검 알림",
        notification_content="내일 새벽 2시부터 4시까지 시스템 점검이 예정되어 있습니다.",
        priority="high"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
