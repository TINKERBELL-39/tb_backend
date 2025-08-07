"""
알림 관리 공통 모듈
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

from .http_client import get_http_client
from .email_manager import get_email_manager
from .config_manager import get_config_manager
from .db_helper import get_db_helper

logger = logging.getLogger(__name__)


class NotificationManager:
    """알림 발송을 위한 통합 관리 클래스"""
    
    def __init__(self):
        self.http_client = get_http_client()
        self.email_manager = get_email_manager()
        self.config_manager = get_config_manager()
        self.db_helper = get_db_helper()
    
    async def send_notification(self, user_id: int, message: str, 
                               channels: List[str] = None, urgency: str = "medium",
                               additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """통합 알림 발송"""
        if not channels:
            channels = ["app"]  # 기본값: 앱 알림
        
        results = {}
        success_count = 0
        
        # 사용자 알림 설정 확인
        notification_settings = await self.db_helper.get_notification_settings(user_id)
        
        for channel in channels:
            try:
                if channel == "app" and notification_settings.get("app_notification", True):
                    result = await self.send_app_notification(user_id, message, urgency, additional_data)
                elif channel == "email" and notification_settings.get("email_notification", True):
                    result = await self.send_email_notification(user_id, message, additional_data)
                elif channel == "sms" and notification_settings.get("sms_notification", True):
                    result = await self.send_sms_notification(user_id, message)
                elif channel == "slack":
                    result = await self.send_slack_notification(message, additional_data)
                elif channel == "teams":
                    result = await self.send_teams_notification(message, additional_data)
                else:
                    result = {"success": False, "reason": "disabled_or_unsupported"}
                
                results[channel] = result
                if result.get("success"):
                    success_count += 1
                
                # 알림 로그 저장
                await self.db_helper.save_notification_log(
                    user_id, channel, message, result.get("success", False),
                    result.get("error") or result.get("reason")
                )
                
            except Exception as e:
                logger.error(f"알림 발송 실패 ({channel}): {e}")
                results[channel] = {"success": False, "error": str(e)}
                await self.db_helper.save_notification_log(
                    user_id, channel, message, False, str(e)
                )
        
        return {
            "success": success_count > 0,
            "total_channels": len(channels),
            "success_count": success_count,
            "results": results
        }
    
    async def send_app_notification(self, user_id: int, message: str, 
                                   urgency: str = "medium", 
                                   additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """앱 내 알림 발송"""
        try:
            notification_data = {
                "user_id": user_id,
                "message": message,
                "urgency": urgency,
                "type": "reminder",
                "timestamp": datetime.now().isoformat(),
                "read": False
            }
            
            if additional_data:
                notification_data.update(additional_data)
            
            # 실시간 알림 전송 (WebSocket, Server-Sent Events 등)
            success = await self._send_realtime_notification(user_id, notification_data)
            
            if success:
                logger.info(f"앱 알림 발송 성공: User {user_id} - {message}")
                return {"success": True, "notification_id": notification_data.get("id")}
            else:
                logger.warning(f"앱 알림 발송 실패: User {user_id} - {message}")
                return {"success": False, "reason": "delivery_failed"}
                
        except Exception as e:
            logger.error(f"앱 알림 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_email_notification(self, user_id: int, message: str,
                                     additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """이메일 알림 발송"""
        try:
            # 사용자 이메일 주소 조회
            user_email = await self.db_helper.get_user_email(user_id)
            if not user_email:
                logger.error(f"사용자 {user_id}의 이메일 주소를 찾을 수 없습니다.")
                return {"success": False, "reason": "no_email"}
            
            # 이메일 설정
            email_config = self.config_manager.get_email_config()
            service = email_config.get("service", "smtp")
            
            # 이메일 내용 구성
            subject = additional_data.get("subject", "📋 업무 리마인더")
            task_id = additional_data.get("task_id")
            
            html_body = self.email_manager.create_html_template(
                title=subject,
                content=message,
                additional_info=f"작업 ID: {task_id}" if task_id else None
            )
            
            # 이메일 발송
            result = await self.email_manager.send_email(
                service=service,
                to_emails=[user_email],
                subject=subject,
                body=message,
                html_body=html_body
            )
            
            if result["success"]:
                logger.info(f"이메일 알림 발송 성공: User {user_id} ({user_email}) - {message}")
                return {"success": True, "message_id": result.get("message_id")}
            else:
                logger.error(f"이메일 알림 발송 실패: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"이메일 알림 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_sms_notification(self, user_id: int, message: str) -> Dict[str, Any]:
        """SMS 알림 발송"""
        try:
            # 사용자 전화번호 조회
            phone_number = await self.db_helper.get_user_phone(user_id)
            if not phone_number:
                logger.error(f"사용자 {user_id}의 전화번호를 찾을 수 없습니다.")
                return {"success": False, "reason": "no_phone"}
            
            # SMS 설정
            sms_config = self.config_manager.get_sms_config()
            service = sms_config.get("service", "aws_sns")
            
            # SMS 메시지 길이 제한 (160자)
            if len(message) > 160:
                message = message[:157] + "..."
            
            # SMS 발송
            if service.lower() == "twilio":
                result = await self._send_sms_via_twilio(phone_number, message, sms_config)
            else:  # 기본값: AWS SNS
                result = await self._send_sms_via_aws_sns(phone_number, message, sms_config)
            
            if result["success"]:
                logger.info(f"SMS 알림 발송 성공: User {user_id} ({phone_number}) - {message}")
                return {"success": True, "message_id": result.get("message_id")}
            else:
                logger.error(f"SMS 알림 발송 실패: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"SMS 알림 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_slack_notification(self, message: str, 
                                     additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Slack 알림 발송"""
        try:
            slack_config = self.config_manager.get_slack_config()
            bot_token = slack_config.get("bot_token")
            
            if not bot_token:
                logger.error("Slack bot token이 설정되지 않았습니다.")
                return {"success": False, "reason": "no_token"}
            
            channel = additional_data.get("channel") if additional_data else None
            recipients = additional_data.get("recipients", []) if additional_data else []
            
            slack_url = "https://slack.com/api/chat.postMessage"
            headers = {
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json"
            }
            
            results = []
            
            # 채널에 메시지 발송
            if channel:
                payload = {
                    "channel": channel,
                    "text": message,
                    "as_user": True
                }
                
                result = await self.http_client.post(slack_url, json_data=payload, headers=headers)
                if result.get("success") and result.get("data", {}).get("ok"):
                    results.append({"target": channel, "success": True})
                    logger.info(f"Slack 채널 메시지 발송 성공: {channel}")
                else:
                    error_msg = result.get("data", {}).get("error", result.get("error", "Unknown error"))
                    results.append({"target": channel, "success": False, "error": error_msg})
                    logger.error(f"Slack 채널 메시지 발송 실패: {error_msg}")
            
            # 개별 사용자에게 DM 발송
            for recipient in recipients:
                payload = {
                    "channel": recipient,
                    "text": message,
                    "as_user": True
                }
                
                result = await self.http_client.post(slack_url, json_data=payload, headers=headers)
                if result.get("success") and result.get("data", {}).get("ok"):
                    results.append({"target": recipient, "success": True})
                    logger.info(f"Slack DM 발송 성공: {recipient}")
                else:
                    error_msg = result.get("data", {}).get("error", result.get("error", "Unknown error"))
                    results.append({"target": recipient, "success": False, "error": error_msg})
                    logger.error(f"Slack DM 발송 실패: {error_msg}")
            
            success_count = sum(1 for r in results if r["success"])
            
            return {
                "success": success_count > 0,
                "total_sent": len(results),
                "success_count": success_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Slack 알림 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_teams_notification(self, message: str,
                                     additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Microsoft Teams 알림 발송"""
        try:
            teams_config = self.config_manager.get_teams_config()
            webhook_url = additional_data.get("webhook_url") if additional_data else None
            webhook_url = webhook_url or teams_config.get("webhook_url")
            
            if not webhook_url:
                logger.error("Teams webhook URL이 설정되지 않았습니다.")
                return {"success": False, "reason": "no_webhook"}
            
            # Teams 메시지 카드 형식
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": "리마인더 알림",
                "sections": [{
                    "activityTitle": "📋 업무 리마인더",
                    "activitySubtitle": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "activityImage": None,
                    "facts": [],
                    "markdown": True,
                    "text": message
                }]
            }
            
            headers = {"Content-Type": "application/json"}
            
            result = await self.http_client.post(webhook_url, json_data=payload, headers=headers)
            
            if result.get("success"):
                logger.info("Teams 메시지 발송 성공")
                return {"success": True, "status_code": result.get("status_code")}
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Teams 메시지 발송 실패: {error_msg}")
                return {"success": False, "error": error_msg}
            
        except Exception as e:
            logger.error(f"Teams 알림 발송 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    # 헬퍼 메서드들
    
    async def _send_realtime_notification(self, user_id: int, notification_data: Dict) -> bool:
        """실시간 알림 전송 (WebSocket, Server-Sent Events 등)"""
        try:
            # Redis를 통한 실시간 알림
            if self.redis_helper.redis_client:
                channel = f"user_notifications_{user_id}"
                message = json.dumps(notification_data, default=str)
                
                success = await self.redis_helper.publish(channel, message)
                return success
            
            # Redis가 없는 경우 로컬 처리
            logger.info(f"실시간 알림 시뮬레이션: User {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"실시간 알림 전송 중 오류: {e}")
            return False
    
    async def _send_sms_via_aws_sns(self, phone_number: str, message: str, 
                                   config: Dict[str, Any]) -> Dict[str, Any]:
        """AWS SNS를 통한 SMS 발송"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            aws_region = config.get("aws_region", "us-east-1")
            sns_client = boto3.client(
                'sns',
                aws_access_key_id=config.get("aws_access_key"),
                aws_secret_access_key=config.get("aws_secret_key"),
                region_name=aws_region
            )
            
            response = sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            return {"success": True, "message_id": response['MessageId']}
            
        except ImportError:
            return {"success": False, "error": "boto3 라이브러리가 설치되지 않았습니다"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _send_sms_via_twilio(self, phone_number: str, message: str,
                                  config: Dict[str, Any]) -> Dict[str, Any]:
        """Twilio를 통한 SMS 발송"""
        try:
            account_sid = config.get("account_sid")
            auth_token = config.get("auth_token")
            from_number = config.get("from_number")
            
            if not all([account_sid, auth_token, from_number]):
                return {"success": False, "error": "Twilio 인증 정보가 설정되지 않았습니다"}
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            
            from http_client import OAuthHttpClient
            oauth_client = OAuthHttpClient()
            basic_auth = oauth_client.create_basic_auth_header(account_sid, auth_token)
            
            headers = {
                "Authorization": basic_auth,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                'From': from_number,
                'To': phone_number,
                'Body': message
            }
            
            result = await self.http_client.post(url, data=data, headers=headers)
            
            if result.get("success") and result.get("status_code") == 201:
                message_id = result.get("data", {}).get("sid")
                return {"success": True, "message_id": message_id}
            else:
                error_msg = result.get("error", "Twilio API Error")
                return {"success": False, "error": error_msg}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_notification_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """사용자 알림 이력 조회"""
        try:
            query = """
                SELECT * FROM notification_logs 
                WHERE user_id = :user_id 
                ORDER BY created_at DESC 
                LIMIT :limit
            """
            params = {"user_id": user_id, "limit": limit}
            
            results = await self.db_helper.execute_raw_query(query, params)
            return results or []
            
        except Exception as e:
            logger.error(f"알림 이력 조회 실패: {e}")
            return []
    
    async def update_notification_settings(self, user_id: int, settings: Dict[str, bool]) -> bool:
        """사용자 알림 설정 업데이트"""
        return await self.db_helper.update_notification_settings(user_id, settings)
    
    async def get_notification_settings(self, user_id: int) -> Dict[str, bool]:
        """사용자 알림 설정 조회"""
        return await self.db_helper.get_notification_settings(user_id)


# 전역 인스턴스
_notification_manager = None

def get_notification_manager() -> NotificationManager:
    """NotificationManager 싱글톤 인스턴스 반환"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
