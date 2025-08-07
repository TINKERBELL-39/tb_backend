"""
이메일 자동화 실행기 v2
실제 main.py의 Email API를 호출하는 실행기
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, List
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class EmailExecutor:
    """이메일 자동화 실행기 - 실제 API 호출"""
    
    def __init__(self):
        """이메일 실행기 초기화"""
        self.api_base_url = os.getenv("TASK_AGENT_API_URL", "https://localhost:8005")
        logger.info("EmailExecutor v2 초기화 완료 (실제 API 호출)")

    async def execute(self, task_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """이메일 발송 실행 - 실제 API 호출"""
        try:
            logger.info(f"이메일 발송 실행 시작 - 사용자: {user_id}")
            
            # 필수 데이터 검증
            validation_result = self._validate_task_data(task_data)
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "message": f"데이터 검증 실패: {', '.join(validation_result['errors'])}",
                    "details": validation_result
                }
            
            # 이메일 데이터 정규화
            email_data = self._normalize_email_data(task_data)
            
            # 실제 Email API 호출
            result = await self._call_email_api(email_data, user_id)
            
            if result["success"]:
                logger.info(f"이메일 발송 성공: {len(email_data['to_emails'])}명")
                return {
                    "success": True,
                    "message": f"{len(email_data['to_emails'])}명에게 이메일이 성공적으로 발송되었습니다",
                    "details": {
                        "recipients": len(email_data['to_emails']),
                        "subject": email_data['subject'],
                        "sent_at": datetime.now().isoformat(),
                        "email_id": result.get("email_id")
                    }
                }
            else:
                logger.error(f"이메일 발송 실패: {result.get('error')}")
                return {
                    "success": False,
                    "message": f"이메일 발송 실패: {result.get('error')}",
                    "details": result
                }
                
        except Exception as e:
            logger.error(f"이메일 실행기 오류: {e}")
            return {
                "success": False,
                "message": f"이메일 발송 중 오류 발생: {str(e)}",
                "details": {"error": str(e)}
            }

    async def _call_email_api(self, email_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """실제 main.py의 Email API 호출"""
        try:
            # EmailRequest 형태로 데이터 변환
            api_email_data = {
                "to_emails": email_data["to_emails"],
                "subject": email_data["subject"],
                "body": email_data["body"],
                "html_body": email_data.get("html_body"),
                "attachments": email_data.get("attachments"),
                "cc_emails": email_data.get("cc_emails"),
                "bcc_emails": email_data.get("bcc_emails"),
                "from_email": email_data.get("from_email"),
                "from_name": email_data.get("from_name"),
                "service": email_data.get("service")
            }
            
            # None 값 제거
            api_email_data = {k: v for k, v in api_email_data.items() if v is not None}
            
            # HTTP 클라이언트로 API 호출
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/email/send"
                
                logger.info(f"Email API 호출: {url} with data: {api_email_data}")
                
                async with session.post(
                    url,
                    json=api_email_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "email_id": result.get("data", {}).get("message_id"),
                            "api_response": result
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Email API 호출 실패: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API 호출 실패 (HTTP {response.status}): {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("Email API 호출 타임아웃")
            return {"success": False, "error": "API 호출 시간 초과"}
        except aiohttp.ClientError as e:
            logger.error(f"Email API 클라이언트 오류: {e}")
            return {"success": False, "error": f"네트워크 오류: {str(e)}"}
        except Exception as e:
            logger.error(f"Email API 호출 예외: {e}")
            return {"success": False, "error": f"API 호출 실패: {str(e)}"}

    def _validate_task_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """이메일 작업 데이터 검증"""
        errors = []
        warnings = []
        
        # 필수 필드 검증
        to_emails = task_data.get("to_emails", [])
        if not to_emails:
            errors.append("받는 사람 이메일이 필요합니다")
        elif not isinstance(to_emails, list):
            errors.append("받는 사람은 이메일 목록이어야 합니다")
        else:
            # 이메일 형식 검증
            for email in to_emails:
                if not self._is_valid_email(email):
                    errors.append(f"잘못된 이메일 형식: {email}")
        
        if not task_data.get("subject"):
            errors.append("이메일 제목이 필요합니다")
        
        if not task_data.get("body"):
            errors.append("이메일 내용이 필요합니다")
        
        # 선택적 필드 검증
        cc_emails = task_data.get("cc_emails", [])
        if cc_emails:
            for email in cc_emails:
                if not self._is_valid_email(email):
                    warnings.append(f"잘못된 참조 이메일 형식: {email}")
        
        bcc_emails = task_data.get("bcc_emails", [])
        if bcc_emails:
            for email in bcc_emails:
                if not self._is_valid_email(email):
                    warnings.append(f"잘못된 숨은참조 이메일 형식: {email}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _is_valid_email(self, email: str) -> bool:
        """이메일 형식 검증"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _normalize_email_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """이메일 데이터 정규화"""
        try:
            normalized = {
                "to_emails": task_data.get("to_emails", []),
                "subject": task_data.get("subject", "").strip(),
                "body": task_data.get("body", "").strip(),
                "html_body": task_data.get("html_body"),
                "attachments": task_data.get("attachments"),
                "cc_emails": task_data.get("cc_emails"),
                "bcc_emails": task_data.get("bcc_emails"),
                "from_email": task_data.get("from_email"),
                "from_name": task_data.get("from_name"),
                "service": task_data.get("service", "default")
            }
            
            # 빈 문자열을 None으로 변환
            for key in ["html_body", "from_email", "from_name"]:
                if normalized[key] == "":
                    normalized[key] = None
            
            # 빈 리스트를 None으로 변환
            for key in ["attachments", "cc_emails", "bcc_emails"]:
                if normalized[key] == []:
                    normalized[key] = None
            
            return normalized
            
        except Exception as e:
            logger.error(f"이메일 데이터 정규화 실패: {e}")
            raise

    def is_available(self) -> bool:
        """실행기 사용 가능 여부"""
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """이메일 API 연결 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/health"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "이메일 API 연결이 정상입니다",
                            "api_url": self.api_base_url
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"API 응답 오류: HTTP {response.status}"
                        }
                        
        except Exception as e:
            return {"success": False, "error": f"연결 테스트 실패: {str(e)}"}

    async def cleanup(self):
        """실행기 정리"""
        try:
            logger.info("EmailExecutor v2 정리 완료")
        except Exception as e:
            logger.error(f"EmailExecutor v2 정리 실패: {e}")
