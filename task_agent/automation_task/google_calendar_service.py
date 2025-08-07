from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from shared_modules.queries import get_user_tokens, update_user_tokens
from shared_modules.database import DatabaseManager
# Add these imports if not already present
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Google Calendar API 스코프
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']

class GoogleCalendarConfig:
    """Google Calendar 설정 클래스"""
    def __init__(self, config_dict=None):
        self.config = config_dict or {}
    
    def get(self, key, default=None):
        """설정 값 가져오기"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

class GoogleCalendarService:
    def __init__(self, api, time_utils, config=None):
        self.api = api    # GoogleApiClient
        self.time = time_utils
        self.config = config or GoogleCalendarConfig()
        self.cache = {}
        self.db_manager = DatabaseManager()

    def _get_service(self, user_id: int):
        if user_id not in self.cache:
            # DB에서 토큰 정보 가져오기
            with self.db_manager.get_session() as db:
                token_data = get_user_tokens(db, user_id)
                
            if not token_data or not token_data.get('access_token'):
                raise ValueError(f"No Google Calendar token found for user {user_id}.")
            
            creds = Credentials(
                token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                token_uri=self.config.get("google_calendar.token_url"),
                client_id=self.config.get("google_calendar.client_id"),
                client_secret=self.config.get("google_calendar.client_secret"),
                scopes=SCOPES
            )
            
            # 토큰이 만료되었고 refresh_token이 있으면 갱신
            if not creds.valid and creds.refresh_token:
                creds.refresh(Request())
                # 갱신된 토큰을 DB에 저장
                with self.db_manager.get_session() as db:
                    update_user_tokens(db, user_id, creds.token, creds.refresh_token)
                    
            self.cache[user_id] = self.api.build_service("calendar", "v3", creds)
        return self.cache[user_id]

  

    def _call(self, func, **kwargs):
        """Google Calendar API 호출 래퍼"""
        try:
            # 디버깅용 로그 추가
            logger.info(f"Google Calendar API 호출 파라미터: {kwargs}")
            logger.info(f"호출할 함수: {func}")
            
            # API 호출 전에 함수 객체 확인
            if hasattr(func, '_baseUrl'):
                logger.info(f"Base URL: {func._baseUrl}")
            
            result = func(**kwargs).execute()
            logger.info(f"API 호출 성공")
            return {"success": True, "data": result}
        except HttpError as e:
            status = getattr(e.resp, 'status', 500)
            logger.error(f"Google Calendar API 오류: {e}")
            logger.error(f"요청 URI: {getattr(e, 'uri', 'Unknown')}")
            
            if status == 404:
                # 캘린더가 없으면 빈 리스트 반환
                return {"success": True, "data": {"items": []}}
            return {"success": False, "error": str(e), "code": status}
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            return {"success": False, "error": str(e), "code": 500}

    async def get_events(self, user_id, start, end, calendar_id="primary"):
        service = self._get_service(user_id)
        return self._call(
            service.events().list,  # 반드시 list로 지정
            calendarId=calendar_id,
            timeMin=self.time.format_datetime_iso(start) + "Z",
            timeMax=self.time.format_datetime_iso(end) + "Z",
            singleEvents=True,
            orderBy="startTime"
        )

    async def search_events(self, user_id, query, calendar_id="primary", max_results=25):
        """검색어 기반 이벤트 조회"""
        service = self._get_service(user_id)
        return self._call(
            service.events().list,
            calendarId=calendar_id,
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        )

    async def create_event(self, user_id, event_data):
        return self._call(
            self._get_service(user_id).events().insert,
            calendarId=event_data.get("calendar_id", "primary"),
            body=self._prepare_event(event_data)
        )


    async def update_event(self, user_id, event_id, data, calendar_id="primary"):
        service = self._get_service(user_id)
        existing = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        existing.update(self._prepare_event(data))
        return self._call(service.events().update, calendarId=calendar_id, eventId=event_id, body=existing)

    async def delete_event(self, user_id, event_id, calendar_id="primary"):
        return self._call(self._get_service(user_id).events().delete, calendarId=calendar_id, eventId=event_id)

    def _prepare_event(self, data):
        # Handle the case where parse_datetime returns None
        start = self.time.parse_datetime(data["start_time"])
        if start is None:
            # Fallback: try to parse as ISO format or use current time
            try:
                from datetime import datetime
                if isinstance(data["start_time"], str):
                    # Try parsing as ISO format
                    start = datetime.fromisoformat(data["start_time"].replace('Z', '+00:00'))
                else:
                    start = datetime.now()
            except (ValueError, TypeError):
                start = datetime.now()
        
        end_time = data.get("end_time")
        if end_time:
            end = self.time.parse_datetime(end_time)
            if end is None:
                try:
                    from datetime import datetime
                    if isinstance(end_time, str):
                        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    else:
                        end = self.time.add_time_delta(start, hours=1)
                except (ValueError, TypeError):
                    end = self.time.add_time_delta(start, hours=1)
        else:
            end = self.time.add_time_delta(start, hours=1)
        
        tz = data.get("timezone", self.config.get("google_calendar.default_timezone", "Asia/Seoul"))
        return {
            "summary": data.get("title", "제목 없음"),
            "description": data.get("description", ""),
            "start": {"dateTime": self.time.format_datetime_iso(start), "timeZone": tz},
            "end": {"dateTime": self.time.format_datetime_iso(end), "timeZone": tz},
            "location": data.get("location", ""),
            "reminders": data.get("reminders", {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15}]}),
            "recurrence": data.get("recurrence", [])
        }

    
    # Add the missing connection status methods
    def is_connected(self, user_id: int) -> bool:
        """사용자의 Google Calendar 연결 상태 확인"""
        try:
            with self.db_manager.get_session() as db:
                token_data = get_user_tokens(db, user_id)
                return token_data is not None and token_data.get('access_token') is not None
        except Exception as e:
            logger.error(f"연결 상태 확인 실패: {e}")
            return False
    
    def get_connection_info(self, user_id: int) -> Dict[str, Any]:
        """사용자의 연결 정보 반환"""
        try:
            with self.db_manager.get_session() as db:
                token_data = get_user_tokens(db, user_id)
                if token_data:
                    return {
                        "connected": True,
                        "has_refresh_token": token_data.get('refresh_token') is not None,
                        "last_updated": token_data.get('updated_at')
                    }
                else:
                    return {"connected": False}
        except Exception as e:
            logger.error(f"연결 정보 조회 실패: {e}")
            return {"connected": False, "error": str(e)}
