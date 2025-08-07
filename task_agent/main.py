"""
TinkerBell 업무지원 에이전트 v5 - 메인 애플리케이션
리팩토링된 FastAPI 애플리케이션
"""
import certifi
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from contextlib import asynccontextmanager
import httpx
from pydantic import BaseModel, Field

# 텔레메트리 비활성화
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False' 
os.environ['DO_NOT_TRACK'] = '1'

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 로컬 모델 import
from models import (
    UserQuery, AutomationRequest, EmailRequest, 
    InstagramPostRequest, EventCreate, EventResponse, 
    CalendarListResponse, QuickEventCreate, ManualContentRequest, AutomationTaskType
)
from sqlalchemy.orm import Session
from sqlalchemy import text

# 공통 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from shared_modules import (
        create_success_response, 
        create_error_response,
        create_task_response
    )
    from shared_modules.logging_utils import setup_logging
    from shared_modules.database import get_db_dependency
    from shared_modules.db_models import AutomationTask
except ImportError:
    # 공통 모듈이 없는 경우 기본 함수들 정의
    def create_success_response(data, message="Success"):
        return {"success": True, "data": data, "message": message}
    
    def create_error_response(message, error_code="ERROR"):
        return {"success": False, "error": message, "error_code": error_code}
        
    def create_task_response(**kwargs):
        return kwargs
    
    def setup_logging(name, log_file=None):
        return logging.getLogger(name)

# 서비스 레이어 import
from services.task_agent_service import TaskAgentService
from services.automation_service import AutomationService  
from automation_task.email_service import EmailService
from automation_task.instagram_service import InstagramPostingService
from automation_task.google_calendar_service import GoogleCalendarService

# 설정 및 의존성
from config import config
from dependencies import get_services

# 로깅 설정
logger = setup_logging("task", log_file="logs/task.log")

# 글로벌 서비스 컨테이너
services = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global services
    
    # 시작
    logger.info("TinkerBell 업무지원 에이전트 v5 시작")
    
    # 환경 설정 검증
    validation = config.validate()
    if not validation["is_valid"]:
        logger.error(f"환경 설정 오류: {validation['issues']}")
        raise RuntimeError("환경 설정이 올바르지 않습니다.")
    
    # 서비스 컨테이너 초기화
    try:
        services = await get_services()
        logger.info("서비스 컨테이너 초기화 완료")
    except Exception as e:
        logger.error(f"서비스 초기화 실패: {e}")
        raise RuntimeError("서비스 초기화 실패")
    
    yield
    
    # 종료
    logger.info("TinkerBell 업무지원 에이전트 v5 종료")
    if services:
        await services.cleanup()

# FastAPI 앱 생성
app = FastAPI(
    title="TinkerBell 업무지원 에이전트 v5",
    description="리팩토링된 AI 기반 업무지원 시스템",
    version="5.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 의존성 주입 =====

def get_task_agent_service() -> TaskAgentService:
    """TaskAgentService 의존성"""
    if not services:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    return services.task_agent_service

def get_automation_service() -> AutomationService:
    """AutomationService 의존성"""
    if not services:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    return services.automation_service

def get_email_service() -> EmailService:
    """EmailService 의존성"""
    if not services:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    return services.email_service

def get_calendar_service() -> GoogleCalendarService:
    """CalendarService 의존성"""
    if not services:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    return services.calendar_service

def get_instagram_service() -> InstagramPostingService:
    """InstagramService 의존성"""
    if not services:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    return services.instagram_service

# ===== 핵심 API 엔드포인트 =====

@app.post("/agent/query")
async def process_user_query(
    query: UserQuery,
    task_service: TaskAgentService = Depends(get_task_agent_service)
):
    """사용자 쿼리 처리 - 자동화 업무 등록 포함"""
    try:
        # 쿼리 처리 및 자동화 작업 등록
        response = await task_service.process_query(query)
        
        # 표준 응답 형식으로 변환
        response_data = create_task_response(
            conversation_id=response.conversation_id,
            answer=response.response,
            topics=[response.metadata.get('intent', 'general_inquiry')],
            sources=response.sources or "",
            intent=response.metadata.get('intent', 'general_inquiry'),
            urgency=getattr(response, 'urgency', 'medium'),
            actions=response.metadata.get('actions', []),
            automation_created=response.metadata.get('automation_created', False)
        )
        
        return create_success_response(response_data)
        
    except Exception as e:
        logger.error(f"쿼리 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/automation/task")
async def create_automation_task(
    request: AutomationRequest,
    automation_service: AutomationService = Depends(get_automation_service)
):
    """자동화 작업 직접 생성"""
    try:
        response = await automation_service.create_task(request)
        return create_success_response(response.dict())
    except Exception as e:
        logger.error(f"자동화 작업 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/automation/task/{task_id}")
async def get_automation_task_status(
    task_id: int,
    automation_service: AutomationService = Depends(get_automation_service)
):
    """자동화 작업 상태 조회"""
    try:
        status = await automation_service.get_task_status(task_id)
        return create_success_response(status)
    except Exception as e:
        logger.error(f"자동화 작업 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/automation/task/{task_id}")
async def cancel_automation_task(
    task_id: int,
    automation_service: AutomationService = Depends(get_automation_service)
):
    """자동화 작업 취소"""
    try:
        result = await automation_service.cancel_task(task_id)
        if result:
            return create_success_response({"message": "작업이 취소되었습니다."})
        else:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"자동화 작업 취소 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/automation/tasks")
async def get_user_automation_tasks(
    user_id: int = Query(..., description="사용자 ID"),
    status: Optional[str] = Query(None, description="작업 상태 필터"),
    limit: int = Query(50, ge=1, le=100, description="최대 조회 수"),
    automation_service: AutomationService = Depends(get_automation_service)
):
    """사용자 자동화 작업 목록 조회"""
    try:
        tasks = await automation_service.get_user_tasks(user_id, status, limit)
        return create_success_response({"tasks": tasks, "count": len(tasks)})
    except Exception as e:
        logger.error(f"사용자 자동화 작업 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 시스템 API =====

@app.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        if services:
            status = await services.get_health_status()
            return create_success_response(status, "시스템 상태 정상")
        else:
            return create_error_response("서비스가 초기화되지 않았습니다.", "SERVICE_NOT_INITIALIZED")
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return create_error_response(str(e), "HEALTH_CHECK_ERROR")

@app.get("/status")
async def get_system_status():
    """시스템 상태 조회"""
    try:
        base_status = {
            "service": "TinkerBell Task Agent v5",
            "version": "5.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "openai_configured": bool(config.OPENAI_API_KEY),
                "google_configured": bool(config.GOOGLE_API_KEY),
                "mysql_configured": bool(config.MYSQL_URL),
                "chroma_configured": bool(config.CHROMA_PERSIST_DIR)
            },
            "config_validation": config.validate()
        }
        
        if services:
            service_status = await services.get_detailed_status()
            base_status.update(service_status)
            base_status["status"] = "healthy"
        else:
            base_status["status"] = "error"
            base_status["message"] = "서비스가 초기화되지 않았습니다."
        
        return base_status
        
    except Exception as e:
        logger.error(f"시스템 상태 조회 실패: {e}")
        return {
            "service": "TinkerBell Task Agent v5",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ==== Email & Instagram API ====
@app.post("/email/send")
async def send_email(
    req: EmailRequest,
    email_service: EmailService = Depends(get_email_service)
):
    """이메일 발송"""
    try:
        result = await email_service.send_email(
            to_emails=req.to_emails,
            subject=req.subject,
            body=req.body,
            html_body=req.html_body,
            attachments=req.attachments,
            cc_emails=req.cc_emails,
            bcc_emails=req.bcc_emails,
            from_email=req.from_email,
            from_name=req.from_name,
            service=req.service
        )
        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "이메일 발송 실패"))
        return create_success_response(result)
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 간단한 Google API 클라이언트 구현 =====

# 리팩토링된 서비스 클래스들 import
from task_agent.automation_task.google_calendar_service import (
    GoogleCalendarService, GoogleCalendarConfig
)

# 실제 구현체들
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 공통 모듈에서 실제 구현체들 import
from task_agent.automation_task.common.auth_manager import AuthManager
from task_agent.automation_task.common.http_client import HttpClient
from task_agent.automation_task.common.utils import AutomationDateTimeUtils
import urllib.parse

class SimpleGoogleApiClient:
    def __init__(self):
        pass
    
    def build_service(self, service_name: str, version: str, credentials):
        # 올바른 Google API 클라이언트 사용
        from googleapiclient.discovery import build
        return build(service_name, version, credentials=credentials)

# 글로벌 캘린더 서비스 인스턴스
_calendar_service = None

def get_calendar_service() -> GoogleCalendarService:
    """Google Calendar Service 의존성 주입"""
    global _calendar_service
    if _calendar_service is None:
        # 설정 로드
        config = GoogleCalendarConfig({
            "google_calendar": {
                "client_id": os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "your_client_id"),
                "client_secret": os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", "your_client_secret"),
                "redirect_uri": os.getenv("GOOGLE_CALENDAR_REDIRECT_URI", "http://localhost:8080/callback"),
                "token_url": "https://oauth2.googleapis.com/token",
                "default_timezone": os.getenv("GOOGLE_CALENDAR_DEFAULT_TIMEZONE", "Asia/Seoul")
            }
        })
        
        # 의존성들 생성 (auth 파라미터 제거)
        _calendar_service = GoogleCalendarService(
            api=SimpleGoogleApiClient(),
            time_utils=AutomationDateTimeUtils(),
            config=config
        )
    
    return _calendar_service

@app.get("/calendars", response_model=CalendarListResponse)
async def get_calendars(
    user_id: int = Query(..., description="사용자 ID"),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """사용자의 캘린더 목록 조회"""
    try:
        service = calendar_service._get_service(user_id)
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        return CalendarListResponse(
            calendars=calendars,
            count=len(calendars)
        )
    except Exception as e:
        logger.error(f"캘린더 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events", response_model=Dict[str, Any])
async def create_event(
    user_id: int = Query(..., description="사용자 ID"),
    event_data: EventCreate = ...,
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """이벤트 생성"""
    try:
        result = await calendar_service.create_event(
            user_id=user_id,
            event_data=event_data.dict()
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Extract event data and ID from the result
        event_data = result.get("data", {})
        event_id = event_data.get("id") if event_data else None
        
        return {
            "success": True,
            "event_id": event_id,
            "event_data": event_data,
            "message": "이벤트가 성공적으로 생성되었습니다."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이벤트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events")
async def get_events(
    user_id: int = Query(..., description="사용자 ID"),
    start_date: str = Query(..., description="시작 날짜 (YYYY-MM-DD)"),
    end_date: str = Query(..., description="종료 날짜 (YYYY-MM-DD)"),
    calendar_id: str = Query("all", description="캘린더 ID (all: 모든 캘린더, primary: 기본 캘린더, 특정 ID: 해당 캘린더만)"),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """이벤트 목록 조회 - 모든 캘린더 또는 특정 캘린더"""
    try:
        # 날짜 파싱
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        all_events = []
        
        if calendar_id == "all":
            # 모든 캘린더에서 이벤트 가져오기
            try:
                service = calendar_service._get_service(user_id)
                calendars_result = service.calendarList().list().execute()
                calendars = calendars_result.get('items', [])
                
                for calendar in calendars:
                    cal_id = calendar.get('id')
                    cal_name = calendar.get('summary', cal_id)
                    
                    try:
                        # 각 캘린더별로 이벤트 조회
                        result = await calendar_service.get_events(
                            user_id=user_id,
                            start=start_dt,
                            end=end_dt,
                            calendar_id=cal_id
                        )
                        
                        if result["success"]:
                            events = result["data"].get("items", [])
                            # 각 이벤트에 캘린더 정보 추가
                            for event in events:
                                event['calendar_id'] = cal_id
                                event['calendar_name'] = cal_name
                            all_events.extend(events)
                        else:
                            logger.warning(f"캘린더 {cal_name}({cal_id}) 이벤트 조회 실패: {result.get('error')}")
                    except Exception as e:
                        logger.warning(f"캘린더 {cal_name}({cal_id}) 이벤트 조회 중 오류: {e}")
                        continue
                
                # 시작 시간으로 정렬
                all_events.sort(key=lambda x: x.get('start', {}).get('dateTime', x.get('start', {}).get('date', '')))
                
                return {
                    "success": True,
                    "data": {
                        "items": all_events,
                        "total_calendars": len(calendars),
                        "total_events": len(all_events)
                    },
                    "message": f"모든 캘린더에서 {len(all_events)}개의 이벤트를 조회했습니다."
                }
                
            except Exception as e:
                logger.error(f"캘린더 목록 조회 실패: {e}")
                # 캘린더 목록 조회 실패 시 기본 캘린더만 조회
                result = await calendar_service.get_events(
                    user_id=user_id,
                    start=start_dt,
                    end=end_dt,
                    calendar_id="primary"
                )
                
                if not result["success"]:
                    raise HTTPException(status_code=400, detail=result["error"])
                
                return {
                    "success": True,
                    "data": result["data"],
                    "message": "기본 캘린더에서만 이벤트를 조회했습니다. (캘린더 목록 조회 실패)"
                }
        else:
            # 특정 캘린더에서만 이벤트 가져오기 (기존 로직)
            result = await calendar_service.get_events(
                user_id=user_id,
                start=start_dt,
                end=end_dt,
                calendar_id=calendar_id
            )
            
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result["error"])
            
            return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이벤트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 구체적인 경로들을 먼저 정의
@app.get("/events/search")
async def search_events(
    user_id: int = Query(..., description="사용자 ID"),
    query: str = Query(..., description="검색어"),
    calendar_id: str = Query("primary", description="캘린더 ID"),
    max_results: int = Query(25, description="최대 결과 수"),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """이벤트 검색"""
    try:
        # Use the calendar service search_events method instead of direct API call
        result = await calendar_service.search_events(
            user_id=user_id,
            query=query,
            calendar_id=calendar_id,
            max_results=max_results
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        events = result["data"].get('items', [])
        
        return {
            "success": True,
            "events": events,
            "count": len(events),
            "query": query
        }
    except Exception as e:
        logger.error(f"이벤트 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/events/quick")
async def create_quick_event(
    user_id: int = Query(..., description="사용자 ID"),
    quick_event: QuickEventCreate = ...,
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """빠른 이벤트 생성 (자연어 입력)"""
    try:
        service = calendar_service._get_service(user_id)
        
        # Google의 Quick Add 기능 사용
        event = service.events().quickAdd(
            calendarId=quick_event.calendar_id,
            text=quick_event.text
        ).execute()
        
        return {
            "success": True,
            "event_id": event.get('id'),
            "event_link": event.get('htmlLink'),
            "event_data": event
        }
    except Exception as e:
        logger.error(f"빠른 이벤트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/upcoming")
async def get_upcoming_events(
    user_id: int = Query(..., description="사용자 ID"),
    days: int = Query(7, description="조회할 일수"),
    calendar_id: str = Query("primary", description="캘린더 ID"),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service)
):
    """다가오는 이벤트 조회"""
    try:
        from datetime import datetime, timedelta
        start_time = datetime.now()
        end_time = start_time + timedelta(days=days)
        
        result = await calendar_service.get_events(
            user_id=user_id,
            start=start_time,
            end=end_time,
            calendar_id=calendar_id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        events = result["data"].get("items", [])
        
        return {
            "success": True,
            "events": events,
            "count": len(events),
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "days": days
        }
    except Exception as e:
        logger.error(f"다가오는 이벤트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== google task =====
# 기존 import 섹션에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))
from shared_modules.queries import get_user_tokens
from shared_modules.database import get_session_context
GOOGLE_TASKS_BASE = os.getenv("GOOGLE_TASKS_BASE", "https://tasks.googleapis.com/tasks/v1")

@app.post("/google/tasks/lists")
async def create_tasklist(
    title: str,
    user_id: int = Query(..., description="사용자 ID")
):
    """Google Tasks에 새로운 작업 목록(Tasklist) 생성"""
    try:
        with get_session_context() as db:
            token_data = get_user_tokens(db, user_id)
            if not token_data or not token_data.get('access_token'):
                return JSONResponse({"error": "Google 로그인 필요"}, status_code=401)

            url = f"{GOOGLE_TASKS_BASE}/users/@me/lists"
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            payload = {"title": title}

            async with httpx.AsyncClient(verify=False, trust_env=False) as client:
                res = await client.post(url, headers=headers, json=payload)
            return res.json()
    except Exception as e:
        logger.error(f"Google Tasks 목록 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/google/tasks")
async def list_tasks(user_id: int = Query(..., description="사용자 ID")):
    """Google Tasks 목록 조회"""
    try:
        with get_session_context() as db:
            token_data = get_user_tokens(db, user_id)
            if not token_data or not token_data.get('access_token'):
                return JSONResponse({"error": "Google 로그인 필요"}, status_code=401)

            url = f"{GOOGLE_TASKS_BASE}/users/@me/lists"
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            async with httpx.AsyncClient(verify=False, trust_env=False) as client:
                res = await client.get(url, headers=headers)
                
            # Check if Google API returned an error
            if res.status_code != 200:
                logger.error(f"Google API 오류: {res.status_code} - {res.text}")
                raise HTTPException(status_code=res.status_code, detail=f"Google API 오류: {res.text}")
                
            return res.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Tasks 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/google/tasks")
async def create_task(
    tasklist_id: str,
    title: str,
    user_id: int = Query(..., description="사용자 ID"),
    notes: str = None,
    due: str = None  # ISO 8601 형식: YYYY-MM-DDTHH:MM:SSZ
):
    """Google Tasks에 작업(Task) 등록 (시간 설정 지원)"""
    try:
        with get_session_context() as db:
            token_data = get_user_tokens(db, user_id)
            if not token_data or not token_data.get('access_token'):
                return JSONResponse({"error": "Google 로그인 필요"}, status_code=401)

            url = f"{GOOGLE_TASKS_BASE}/lists/{tasklist_id}/tasks"
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}

            payload = {"title": title}
            if notes:
                payload["notes"] = notes
            if due:
                payload["due"] = due  # e.g., "2025-07-28T09:00:00Z" (UTC 시간)

            async with httpx.AsyncClient(verify=False, trust_env=False) as client:
                res = await client.post(url, headers=headers, json=payload)
            return res.json()
    except Exception as e:
        logger.error(f"Google Tasks 작업 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/google/tasks/{tasklist_id}")
async def get_tasks_from_list(tasklist_id: str, user_id: int = Query(..., description="사용자 ID")):
    """특정 작업 목록의 작업들 조회"""
    try:
        with get_session_context() as db:
            token_data = get_user_tokens(db, user_id)
            if not token_data or not token_data.get('access_token'):
                return JSONResponse({"error": "Google 로그인 필요"}, status_code=401)

            url = f"{GOOGLE_TASKS_BASE}/lists/{tasklist_id}/tasks"
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            async with httpx.AsyncClient(verify=False, trust_env=False) as client:
                res = await client.get(url, headers=headers)
                
            if res.status_code != 200:
                logger.error(f"Google API 오류: {res.status_code} - {res.text}")
                raise HTTPException(status_code=res.status_code, detail=f"Google API 오류: {res.text}")
                
            return res.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Tasks 작업 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 에러 핸들러 =====

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.detail, f"HTTP_{exc.status_code}")
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """일반 예외 처리"""
    logger.error(f"처리되지 않은 예외: {exc}")
    return JSONResponse(
        status_code=500,
        content=create_error_response("내부 서버 오류가 발생했습니다.", "INTERNAL_ERROR")
    )

# ===== 에러 핸들러 =====
# ===== 에러 핸들러 =====

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.detail, f"HTTP_{exc.status_code}")
    )
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.detail, f"HTTP_{exc.status_code}")
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """일반 예외 처리"""
    logger.error(f"처리되지 않은 예외: {exc}")
    return JSONResponse(
        status_code=500,
        content=create_error_response("내부 서버 오류가 발생했습니다.", "INTERNAL_ERROR")
    )

from services.instagram import router as insta_router
app.include_router(insta_router, tags=["Instagram"])


class ContentSaveRequest(BaseModel):
    user_id: int
    title: str
    content: str
    task_type: str      # 예: sns_publish_instagram
    platform: str       # 예: instagram / blog
    scheduled_at: Optional[datetime] = None

@app.post("/workspace/automation/manual")
async def save_manual_content(
    req: ManualContentRequest,
    automation_service: AutomationService = Depends(get_automation_service)
):
    """
    수동 작성 콘텐츠 저장 API
    """
    try:
        logger.info(f"📨 [Manual] 저장 요청: {req.task_type=} {req.task_data=}")

        # AutomationRequest 객체 생성
        automation_request = AutomationRequest(
            user_id=req.user_id,
            task_type=AutomationTaskType(req.task_type),  # enum으로 변환
            title=req.title,
            task_data={
                "platform": req.platform,
                "full_content": req.content,
                **req.task_data
            },
            scheduled_at=req.scheduled_at
        )
        
        # AutomationService를 통해 작업 생성
        response = await automation_service.create_task(automation_request)
        
        return {
            "success": True,
            "message": "수동 콘텐츠가 성공적으로 저장되었습니다.",
            "task_id": response.task_id,
            "status": response.status.value,
            "automation_message": response.message
        }

    except Exception as e:
        logger.error(f"❌ 수동 콘텐츠 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="수동 콘텐츠 저장 중 오류 발생")

@app.get("/workspace/automation")
def get_user_automation_tasks(user_id: int = Query(...), db: Session = Depends(get_db_dependency)):
    try:
        tasks = db.query(AutomationTask).filter(
            AutomationTask.user_id == user_id,
            AutomationTask.task_type.in_([
                "sns_publish_instagram",
                "sns_publish_blog"
            ])
        ).order_by(AutomationTask.created_at.desc()).all()

        return {
            "success": True,
            "data": {
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "task_type": task.task_type,
                        "task_data": task.task_data,
                        "status": task.status,
                        "created_at": task.created_at,
                    }
                    for task in tasks
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Also fix the router function around line 774
@app.delete("/workspace/automation/{task_id}")
def delete_automation_task(task_id: int, db: Session = Depends(get_db_dependency)):
    task = db.query(AutomationTask).filter(AutomationTask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Automation task not found")

    db.delete(task)
    db.commit()
    return {"success": True, "message": f"Task {task_id} deleted"}

# 관리자 템플릿 조회
@app.get("/api/email/templates")
def get_email_templates(user_id: int = Query(...), db: Session = Depends(get_db_dependency)):
    try:
        rows = db.execute(
            text("""
                SELECT * FROM template_message
                WHERE user_id = :user_id OR user_id = 3
                ORDER BY created_at DESC
            """),
            {"user_id": user_id}
        ).fetchall()

        templates = [dict(row._mapping) for row in rows]
        return {"success": True, "templates": templates}
    except Exception as e:
        return {"success": False, "error": str(e)}

class EmailTemplateCreateRequest(BaseModel):
    user_id: int
    title: str
    content: str
    template_type: str  # 예: "user_made"
    channel_type: Optional[str] = "email"
    content_type: Optional[str] = "default"

@app.post("/api/email/templates")
def create_email_template(req: EmailTemplateCreateRequest, db: Session = Depends(get_db_dependency)):
    try:
        db.execute(
            text("""  # ← 이 부분 감싸기!
                INSERT INTO template_message 
                (user_id, title, content, template_type, channel_type, content_type, created_at)
                VALUES (:user_id, :title, :content, :template_type, :channel_type, :content_type, NOW())
            """),
            {
                "user_id": req.user_id,
                "title": req.title,
                "content": req.content,
                "template_type": req.template_type,
                "channel_type": req.channel_type,
                "content_type": req.content_type,
            }
        )
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    )
