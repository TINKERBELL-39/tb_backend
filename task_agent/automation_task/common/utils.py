"""
자동화 작업 공통 유틸리티 함수들 v2
공통 모듈의 utils를 활용하여 유틸리티 제공
"""

import sys
import os
import re
import json
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import logging

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared_modules"))

# 공통 모듈에서 유틸리티 함수들 가져오기
from utils import (
    validate_email,
    truncate_text,
    get_current_timestamp,
    ensure_directory_exists,
    create_success_response,
    create_error_response
)

logger = logging.getLogger(__name__)

class AutomationValidationUtils:
    """자동화 작업을 위한 데이터 검증 유틸리티"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """이메일 주소 형식 검증 (공통 모듈 활용)"""
        return validate_email(email)
    
    @staticmethod
    def is_valid_phone(phone: str, country_code: str = "KR") -> bool:
        """전화번호 형식 검증"""
        # 한국 전화번호 패턴
        if country_code.upper() == "KR":
            # 010-1234-5678, 02-123-4567, +82-10-1234-5678 등
            patterns = [
                r'^010-\d{4}-\d{4}$',
                r'^0\d{1,2}-\d{3,4}-\d{4}$',
                r'^\+82-10-\d{4}-\d{4}$',
                r'^\+82-\d{1,2}-\d{3,4}-\d{4}$',
                r'^010\d{8}$',  # 하이픈 없는 형태
                r'^\+8210\d{8}$'
            ]
            return any(re.match(pattern, phone) for pattern in patterns)
        
        # 국제 전화번호 기본 패턴
        pattern = r'^\+\d{1,3}-?\d{1,14}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """URL 형식 검증"""
        pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        return re.match(pattern, url) is not None
    
    @staticmethod
    def is_valid_slack_channel(channel: str) -> bool:
        """Slack 채널명 형식 검증"""
        # Slack 채널은 #으로 시작하거나 @로 시작 (DM)
        pattern = r'^[#@][a-zA-Z0-9_-]+$'
        return re.match(pattern, channel) is not None
    
    @staticmethod
    def is_valid_teams_webhook(webhook_url: str) -> bool:
        """Teams 웹훅 URL 형식 검증"""
        # Microsoft Teams 웹훅 URL 패턴
        return (webhook_url.startswith('https://') and 
                'office.com' in webhook_url and 
                'webhookb2' in webhook_url)
    
    @staticmethod
    def sanitize_input(text: str, max_length: Optional[int] = None, 
                      remove_html: bool = True) -> str:
        """입력 텍스트 정리 (공통 모듈 기반 확장)"""
        if not text:
            return ""
        
        # 기본 정리
        text = text.strip()
        
        # HTML 태그 제거 (기본적인 XSS 방지)
        if remove_html:
            text = re.sub(r'<[^>]+>', '', text)
        
        # 특수 문자 정리 (이메일/메시지 내용용)
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        
        # 길이 제한 (공통 모듈 함수 활용)
        if max_length:
            text = truncate_text(text, max_length)
        
        return text
    
    @staticmethod
    def validate_automation_data(task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """자동화 작업 데이터 검증"""
        errors = []
        warnings = []
        
        if task_type == "send_email":
            # 이메일 발송 데이터 검증
            if not task_data.get("to_emails"):
                errors.append("수신자 이메일이 필요합니다")
            else:
                invalid_emails = [
                    email for email in task_data["to_emails"] 
                    if not AutomationValidationUtils.is_valid_email(email)
                ]
                if invalid_emails:
                    errors.append(f"유효하지 않은 이메일 주소: {', '.join(invalid_emails)}")
            
            if not task_data.get("subject"):
                errors.append("이메일 제목이 필요합니다")
            
            if not task_data.get("body"):
                errors.append("이메일 내용이 필요합니다")
                
        elif task_type == "send_message":
            # 메시지 발송 데이터 검증
            if not task_data.get("platform"):
                errors.append("메시지 플랫폼이 필요합니다")
            
            if not task_data.get("content"):
                errors.append("메시지 내용이 필요합니다")
            
            platform = task_data.get("platform", "").lower()
            if platform == "slack":
                if not task_data.get("channel"):
                    errors.append("Slack 채널이 필요합니다")
                elif not AutomationValidationUtils.is_valid_slack_channel(task_data["channel"]):
                    warnings.append("Slack 채널명 형식을 확인해주세요")
                    
            elif platform == "teams":
                if not task_data.get("webhook_url"):
                    errors.append("Teams 웹훅 URL이 필요합니다")
                elif not AutomationValidationUtils.is_valid_teams_webhook(task_data["webhook_url"]):
                    warnings.append("Teams 웹훅 URL 형식을 확인해주세요")
                    
        elif task_type == "calendar_sync":
            # 캘린더 일정 데이터 검증
            if not task_data.get("title"):
                errors.append("일정 제목이 필요합니다")
            
            if not task_data.get("start_time"):
                errors.append("시작 시간이 필요합니다")
            else:
                # 시간 형식 검증
                start_time = task_data["start_time"]
                if isinstance(start_time, str):
                    try:
                        AutomationDateTimeUtils.parse_datetime(start_time)
                    except:
                        errors.append("시작 시간 형식이 올바르지 않습니다")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


class AutomationDateTimeUtils:
    """자동화 작업을 위한 날짜/시간 처리 유틸리티"""
    
    @staticmethod
    def parse_datetime(date_string: str) -> Optional[datetime]:
        """다양한 형식의 날짜 문자열을 datetime으로 변환"""
        if not date_string:
            return None
            
        # If it's already a datetime object, return it
        if isinstance(date_string, datetime):
            return date_string
            
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",  # Added microseconds support
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y년 %m월 %d일 %H시 %M분",
            "%Y년 %m월 %d일"
        ]
        
        # Try ISO format parsing first
        try:
            # Handle ISO format with timezone
            if 'T' in date_string:
                return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        logger.warning(f"날짜 파싱 실패: {date_string}")
        return None
    
    @staticmethod
    def format_datetime_korean(dt: datetime) -> str:
        """한국어 형식으로 날짜시간 포맷"""
        return dt.strftime("%Y년 %m월 %d일 %H시 %M분")
    
    @staticmethod
    def format_datetime_iso(dt: datetime) -> str:
        """ISO 형식으로 날짜시간 포맷"""
        return dt.isoformat()
    
    @staticmethod
    def add_time_delta(dt: datetime, **kwargs) -> datetime:
        """datetime에 시간 간격 추가"""
        return dt + timedelta(**kwargs)
    
    @staticmethod
    def is_business_hour(dt: datetime, start_hour: int = 9, end_hour: int = 18) -> bool:
        """업무 시간 여부 확인"""
        weekday = dt.weekday()  # 0=월요일, 6=일요일
        hour = dt.hour
        
        # 주말 제외
        if weekday >= 5:  # 토요일, 일요일
            return False
        
        # 업무 시간 확인
        return start_hour <= hour < end_hour
    
    @staticmethod
    def get_next_business_day(dt: datetime = None) -> datetime:
        """다음 영업일 반환"""
        if dt is None:
            dt = datetime.now()
        
        # 다음 날부터 시작
        next_day = dt + timedelta(days=1)
        
        # 주말이 아닐 때까지 반복
        while next_day.weekday() >= 5:  # 토요일, 일요일
            next_day += timedelta(days=1)
        
        # 업무 시간으로 설정 (오전 9시)
        return next_day.replace(hour=9, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def calculate_delay_until(target_time: datetime) -> float:
        """지정된 시간까지의 지연 시간 계산 (초 단위)"""
        now = datetime.now()
        if target_time <= now:
            return 0
        
        delta = target_time - now
        return delta.total_seconds()


class AutomationSecurityUtils:
    """자동화 작업을 위한 보안 유틸리티"""
    
    @staticmethod
    def generate_task_token(task_id: int, user_id: int) -> str:
        """작업용 토큰 생성"""
        data = f"{task_id}:{user_id}:{get_current_timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
        """민감한 데이터 마스킹"""
        if len(data) <= visible_chars:
            return mask_char * len(data)
        
        if "@" in data:  # 이메일인 경우
            username, domain = data.split("@", 1)
            masked_username = username[:2] + mask_char * (len(username) - 2)
            return f"{masked_username}@{domain}"
        
        visible_part = data[:visible_chars]
        masked_part = mask_char * (len(data) - visible_chars)
        return visible_part + masked_part
    
    @staticmethod
    def validate_webhook_signature(payload: str, signature: str, secret: str) -> bool:
        """웹훅 서명 검증"""
        try:
            import hmac
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"웹훅 서명 검증 실패: {e}")
            return False


class AutomationDataUtils:
    """자동화 작업을 위한 데이터 처리 유틸리티"""
    
    @staticmethod
    def safe_json_parse(json_string: str, default: Any = None) -> Any:
        """안전한 JSON 파싱"""
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return default
    
    @staticmethod
    def format_message_template(template: str, variables: Dict[str, Any]) -> str:
        """메시지 템플릿 포맷팅"""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"템플릿 변수 누락: {e}")
            return template
        except Exception as e:
            logger.error(f"템플릿 포맷팅 실패: {e}")
            return template
    
    @staticmethod
    def extract_mentions(text: str, platform: str = "slack") -> List[str]:
        """텍스트에서 멘션 추출"""
        mentions = []
        
        if platform.lower() == "slack":
            # Slack 멘션 패턴: @username, <@U1234567>
            patterns = [
                r'@([a-zA-Z0-9._-]+)',
                r'<@([UW][A-Z0-9]+)>'
            ]
        elif platform.lower() == "teams":
            # Teams 멘션 패턴: @username
            patterns = [r'@([a-zA-Z0-9._-]+)']
        else:
            # 일반적인 멘션 패턴
            patterns = [r'@([a-zA-Z0-9._-]+)']
        
        for pattern in patterns:
            mentions.extend(re.findall(pattern, text))
        
        return list(set(mentions))  # 중복 제거
    
    @staticmethod
    def clean_html_content(html_content: str) -> str:
        """HTML 내용에서 텍스트만 추출"""
        # HTML 태그 제거
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # HTML 엔티티 디코딩
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#x27;': "'",
            '&#x2F;': '/',
            '&nbsp;': ' '
        }
        
        for entity, char in html_entities.items():
            clean_text = clean_text.replace(entity, char)
        
        return clean_text.strip()
    
    @staticmethod
    def build_webhook_payload(event_type: str, data: Dict[str, Any], 
                            timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """웹훅 페이로드 구성"""
        if timestamp is None:
            timestamp = datetime.now()
        
        return {
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "data": data,
            "version": "1.0"
        }


class AutomationResponseUtils:
    """자동화 작업을 위한 응답 처리 유틸리티"""
    
    @staticmethod
    def create_task_response(task_id: int, status: str, message: str, 
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """작업 응답 생성 (공통 모듈 기반)"""
        response_data = {
            "task_id": task_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if data:
            response_data.update(data)
        
        if status in ["success", "completed"]:
            return create_success_response(data=response_data, message=message)
        else:
            return create_error_response(message, f"TASK_{status.upper()}")
    
    @staticmethod
    def create_notification_response(notification_type: str, success: bool, 
                                   message: str, recipient: str = None) -> Dict[str, Any]:
        """알림 응답 생성"""
        response_data = {
            "notification_type": notification_type,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if recipient:
            response_data["recipient"] = AutomationSecurityUtils.mask_sensitive_data(recipient)
        
        if success:
            return create_success_response(data=response_data, message=message)
        else:
            return create_error_response(message, f"NOTIFICATION_{notification_type.upper()}_FAILED")


# 편의 함수들
def validate_task_data(task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """작업 데이터 검증 (편의 함수)"""
    return AutomationValidationUtils.validate_automation_data(task_type, task_data)

def format_korean_datetime(dt: datetime) -> str:
    """한국어 날짜시간 포맷 (편의 함수)"""
    return AutomationDateTimeUtils.format_datetime_korean(dt)

def mask_email(email: str) -> str:
    """이메일 마스킹 (편의 함수)"""
    return AutomationSecurityUtils.mask_sensitive_data(email)

def safe_template_format(template: str, **kwargs) -> str:
    """안전한 템플릿 포맷팅 (편의 함수)"""
    return AutomationDataUtils.format_message_template(template, kwargs)

# 기존 코드와의 호환성을 위한 별칭들
ValidationUtils = AutomationValidationUtils
DateTimeUtils = AutomationDateTimeUtils
SecurityUtils = AutomationSecurityUtils
DataUtils = AutomationDataUtils
RetryUtils = AutomationDataUtils  # 필요시 별도 구현
LogUtils = AutomationDataUtils    # 필요시 별도 구현
