"""
캘린더 자동화 실행기 v2
실제 main.py의 Google Calendar API를 호출하는 실행기
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import os
import ssl

logger = logging.getLogger(__name__)

class CalendarExecutor:
    """캘린더 자동화 실행기 - 실제 API 호출"""
    
    def __init__(self):
        """캘린더 실행기 초기화"""
        self.supported_providers = ["google", "outlook", "apple"]
        self.default_timezone = "Asia/Seoul"
        self.api_base_url = os.getenv("TASK_AGENT_API_URL", "https://localhost:8005")
        
        logger.info("CalendarExecutor v2 초기화 완료 (실제 API 호출)")

    async def execute(self, task_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """일정 등록 실행 - 실제 API 호출"""
        try:
            logger.info(f"일정 등록 실행 시작 - 사용자: {user_id}")
            
            # 필수 데이터 검증
            validation_result = self._validate_task_data(task_data)
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "message": f"데이터 검증 실패: {', '.join(validation_result['errors'])}",
                    "details": validation_result
                }
            
            # 일정 데이터 추출 및 정규화
            event_data = await self._normalize_event_data(task_data)
            
            # 실제 Google Calendar API 호출
            result = await self._call_calendar_api(event_data, user_id)
            
            if result["success"]:
                logger.info(f"일정 등록 성공 - 이벤트 ID: {result.get('event_id')}")
                return {
                    "success": True,
                    "message": f"'{event_data['title']}' 일정이 성공적으로 등록되었습니다",
                    "details": {
                        "event_id": result.get("event_id"),
                        "title": event_data["title"],
                        "start_time": event_data["start_time"],
                        "end_time": event_data.get("end_time"),
                        "calendar_link": result.get("calendar_link"),
                        "provider": "google"
                    }
                }
            else:
                logger.error(f"일정 등록 실패: {result.get('error')}")
                return {
                    "success": False,
                    "message": f"일정 등록 실패: {result.get('error')}",
                    "details": result
                }
                
        except Exception as e:
            logger.error(f"캘린더 실행기 오류: {e}")
            return {
                "success": False,
                "message": f"일정 등록 중 오류 발생: {str(e)}",
                "details": {"error": str(e)}
            }

    async def _call_calendar_api(self, event_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """실제 main.py의 Calendar API 호출"""
        try:
            # EventCreate 형태로 데이터 변환
            api_event_data = {
                "title": event_data["title"],
                "description": event_data.get("description", ""),
                "location": event_data.get("location", ""),
                "start_time": event_data["start_time"].isoformat() if isinstance(event_data["start_time"], datetime) else event_data["start_time"],
                "end_time": event_data["end_time"].isoformat() if isinstance(event_data["end_time"], datetime) else event_data["end_time"],
                "timezone": self.default_timezone,
                "all_day": event_data.get("all_day", False),
                "calendar_id": event_data.get("calendar_id", "primary"),
                "reminders": event_data.get("reminders", [{"method": "popup", "minutes": 15}])
            }
            
            # 참석자 추가
            if event_data.get("attendees"):
                attendees_list = []
                for attendee in event_data["attendees"]:
                    if isinstance(attendee, str):
                        attendees_list.append({"email": attendee})
                    elif isinstance(attendee, dict):
                        attendees_list.append(attendee)
                api_event_data["attendees"] = attendees_list
            
            # SSL 검증을 비활성화한 커넥터 생성
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            # HTTP 클라이언트로 API 호출
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{self.api_base_url}/events"
                params = {"user_id": user_id}
                
                logger.info(f"Calendar API 호출: {url} with data: {api_event_data}")
                
                async with session.post(
                    url,
                    json=api_event_data,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "event_id": result.get("event_id"),
                            "calendar_link": result.get("event_data", {}).get("htmlLink"),
                            "api_response": result
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Calendar API 호출 실패: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API 호출 실패 (HTTP {response.status}): {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("Calendar API 호출 타임아웃")
            return {"success": False, "error": "API 호출 시간 초과"}
        except aiohttp.ClientError as e:
            logger.error(f"Calendar API 클라이언트 오류: {e}")
            return {"success": False, "error": f"네트워크 오류: {str(e)}"}
        except Exception as e:
            logger.error(f"Calendar API 호출 예외: {e}")
            return {"success": False, "error": f"API 호출 실패: {str(e)}"}

    def _validate_task_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """일정 작업 데이터 검증"""
        errors = []
        warnings = []
        
        # 필수 필드 검증
        if not task_data.get("title"):
            errors.append("일정 제목이 필요합니다")
        
        if not task_data.get("start_time"):
            errors.append("시작 시간이 필요합니다")
        else:
            # 시간 형식 검증
            start_time = self._parse_datetime(task_data["start_time"])
            if not start_time:
                errors.append("잘못된 시작 시간 형식입니다")
            elif start_time < datetime.now():
                warnings.append("과거 시간으로 일정이 설정됩니다")
        
        # 종료 시간 검증 (선택적)
        if task_data.get("end_time"):
            end_time = self._parse_datetime(task_data["end_time"])
            start_time = self._parse_datetime(task_data["start_time"])
            
            if not end_time:
                warnings.append("잘못된 종료 시간 형식 - 기본값 사용")
            elif start_time and end_time <= start_time:
                errors.append("종료 시간은 시작 시간보다 늦어야 합니다")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """문자열을 datetime 객체로 변환"""
        try:
            # ISO 형식 시도
            if 'T' in datetime_str:
                return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            
            # 다양한 형식 시도
            try:
                from dateutil.parser import parse
                return parse(datetime_str)
            except ImportError:
                # dateutil이 없는 경우 기본 파싱
                return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            logger.warning(f"날짜 파싱 실패: {datetime_str}, 오류: {e}")
            return None

    async def _normalize_event_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """이벤트 데이터 정규화"""
        try:
            normalized = {
                "title": (task_data.get("title") or "").strip(),
                "description": (task_data.get("description") or "").strip(),
                "location": (task_data.get("location") or "").strip(),
                "attendees": task_data.get("attendees", []),
                "reminder_minutes": task_data.get("reminder_minutes", 15),
                "all_day": task_data.get("all_day", False),
                "calendar_id": task_data.get("calendar_id", "primary")
            }
            
            # 시간 정규화
            start_time = self._parse_datetime(task_data["start_time"])
            if start_time:
                normalized["start_time"] = start_time
            
            # 종료 시간 설정
            if task_data.get("end_time"):
                end_time = self._parse_datetime(task_data["end_time"])
                if end_time:
                    normalized["end_time"] = end_time
            
            # 종료 시간이 없으면 1시간 후로 설정
            if "end_time" not in normalized and "start_time" in normalized:
                if normalized.get("all_day"):
                    # 종일 이벤트는 같은 날짜
                    normalized["end_time"] = normalized["start_time"]
                else:
                    # 1시간 후로 설정
                    normalized["end_time"] = normalized["start_time"] + timedelta(hours=1)
            
            # 리마인더 설정
            if task_data.get("reminders"):
                normalized["reminders"] = task_data["reminders"]
            else:
                normalized["reminders"] = [{"method": "popup", "minutes": normalized["reminder_minutes"]}]
            
            return normalized
            
        except Exception as e:
            logger.error(f"이벤트 데이터 정규화 실패: {e}")
            raise

    def is_available(self) -> bool:
        """실행기 사용 가능 여부"""
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """캘린더 API 연결 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/health"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "캘린더 API 연결이 정상입니다",
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
            logger.info("CalendarExecutor v2 정리 완료")
        except Exception as e:
            logger.error(f"CalendarExecutor v2 정리 실패: {e}")
